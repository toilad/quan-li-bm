"""Domain Manager: rows with an empty B → new name under a ticked root domain → verify → write B.
On cPanel the name is a subdomain when the root is on the account, otherwise an addon domain (decided per root, read live).

Rules: only ticked, usable roots are ever used (checked at enqueue AND before every creating step);
B is written only after A record + cPanel subdomain + DNS points to the hosting IP + B still empty at write time.
C is never touched. Everything over official APIs; no browser automation.
"""
import json
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import API_ROOT, settings
from ...integrations import net
from ...integrations import cpanel_api2
from ...integrations.cpanel import CPanel
from ...runtime_config import get as cfg
from ...integrations.errors import Conflict, NotAvailable, Permanent, Transient, wait_or_fail
from ...integrations.google import Sheets
from ...integrations.inet import Inet
from ...jobs import JobContext, enqueue, handler
from . import dns_plan
from ...models import AppSetting, Job, Nick, RootDomain, SheetWrite

DNS_WAIT_HOURS = 12  # a new record normally shows within minutes; past this something is wrong
LABEL_RX = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
LEGAL = re.compile(r"\b(llc|inc|pllc|co|corp|ltd)\b\.?")


def seed(s: Session):
    """Load nick + root data once (non-secret config). Never overwrites the owner's ticks."""
    path = settings().nicks_file or str(API_ROOT / "config" / "nicks.example.json")
    data = json.loads(open(path, encoding="utf-8").read())
    for n in data["nicks"]:
        if not s.get(Nick, n["id"]):
            s.add(Nick(id=n["id"], name=n["name"], ip=n["ip"], hosting=n.get("hosting"), cpanel_host=n["cpanel_host"]))
        s.flush()
        for r in n["roots"]:
            name, dns, exp, apex = r[:4]
            if not s.get(RootDomain, name):
                s.add(RootDomain(name=name, nick_id=n["id"], dns_host=dns, expires=date.fromisoformat(exp),
                                 apex_on_hosting=apex, suspended=len(r) > 4 and r[4] == "suspended", selected=False))


def root_issue(r: RootDomain, nick: Nick) -> str | None:
    if r.suspended:
        return "Miền đang tạm ngưng"
    if r.expires and r.expires < date.today():
        return "Miền đã hết hạn"
    if r.dns_host == "other":
        return "DNS ở nhà cung cấp khác (Cloudflare) — API iNET không ghi được"
    if r.dns_host == "unknown":
        return "Chưa xác định nameserver"
    if not nick.enabled:
        return f"Nick {nick.name} đang tắt"
    return None


def root_busy(s: Session, root: str) -> bool:
    for job in s.scalars(select(Job).where(Job.kind == "domain_create", Job.status.in_(("queued", "running", "failed", "blocked")))):
        if job.payload.get("root") == root and (job.status in ("queued", "running") or job.state.get("dns_created") or job.state.get("host_created")):
            return True
    return False


def cpanel_domains(s: Session, nick_id: str) -> set[str] | None:
    """Domains that the last read-only check found on the nick's cPanel account; None = never checked."""
    row = s.get(AppSetting, f"cpanel_domains:{nick_id}")
    return set(row.value.get("domains", [])) if row else None


def check_nick(s: Session, nick_id: str) -> dict:
    """Read-only: which roots exist on the cPanel account and in the nick's iNET account."""
    from datetime import datetime, timezone

    from ...integrations.errors import IntegrationError

    nick = s.get(Nick, nick_id)
    if not nick:
        raise Permanent("Không có nick này")
    out: dict = {"nick": nick.name}
    try:
        inv = CPanel(nick.id, nick.cpanel_host).inventory()
        names, aliases = inv.pop("names"), set(inv.pop("aliases"))
        s.merge(AppSetting(key=f"cpanel_domains:{nick.id}", value={"domains": names, "main": inv["main"], "at": datetime.now(timezone.utc).isoformat()}))
        roots = [r.name for r in s.scalars(select(RootDomain).where(RootDomain.nick_id == nick.id))]
        # how a new name under each root gets created on this account — read per root, not assumed per nick
        modes = {r: ("subdomain" if r in names else "dừng: là alias" if r in aliases else "addon") for r in roots}
        out["cpanel"] = {"ok": True, **inv, "subdomains": inv["subdomain"], "modes": modes,
                         "on_hosting": [r for r in roots if r in names], "missing": [r for r in roots if r not in names],
                         "note": (f"Miền chính {inv['main']}: {inv['addon']} addon, {inv['subdomain']} subdomain, {inv['parked']} alias. "
                                  f"Tạo mới: {sum(m == 'subdomain' for m in modes.values())} miền gốc theo kiểu subdomain, "
                                  f"{sum(m == 'addon' for m in modes.values())} theo kiểu addon domain")}
        try:
            out["cpanel"]["version"] = CPanel(nick.id, nick.cpanel_host).version()
        except IntegrationError as e:
            out["cpanel"]["version"] = f"không đọc được ({e})"
    except IntegrationError as e:
        out["cpanel"] = {"ok": False, "error": str(e)}
    try:
        inet_names = sorted({(d.get("name") or "").lower() for d in Inet(nick.id).list_domains() if d.get("name")})
        s.merge(AppSetting(key=f"inet_domains:{nick.id}", value={"domains": inet_names, "at": datetime.now(timezone.utc).isoformat()}))
        roots = [r.name for r in s.scalars(select(RootDomain).where(RootDomain.nick_id == nick.id))]
        missing = [r for r in roots if r not in inet_names]
        out["inet"] = {"ok": True, "domains": len(inet_names), "missing": missing,
                       "note": f"{len(inet_names)} miền trong tài khoản" + (f", không thấy {', '.join(missing)}" if missing else ", có đủ các miền gốc")}
    except IntegrationError as e:
        out["inet"] = {"ok": False, "error": str(e)}
    return out


def set_selected(s: Session, names: list[str], on: bool) -> dict:
    changed, refused = [], {}
    for name in names:
        r = s.get(RootDomain, name)
        if not r:
            refused[name] = "Không có trong danh sách"
            continue
        if on and (why := root_issue(r, s.get(Nick, r.nick_id))):
            refused[name] = why
        elif not on and root_busy(s, name):
            refused[name] = "Đang có tác vụ trên miền này — bỏ chọn sau khi xong"
        else:
            r.selected = on
            changed.append(name)
    return {"changed": changed, "refused": refused}


BR_SUFFIX = re.compile(r"[\s,.-]+(ltda|eireli|epp|me|s/?a)\.?\s*$")  # Brazilian legal forms, only at the end


def slug(company: str) -> str:
    """Legacy _slug_for_subdomain: drop legal suffixes and symbols; accents are folded ("ç" → "c"), not dropped.
    Same rule as subdomainSlug() in the web app. (Naming rule still to be confirmed by the owner.)"""
    from ..pdf.fields import strip_accents

    name = BR_SUFFIX.sub("", strip_accents(company.lower()))
    return re.sub(r"[^a-z0-9]", "", LEGAL.sub("", name))


def label_for(cells: dict) -> str:
    """The label the Sheet already uses: column E (729 of the 760 existing domains on 2026-10-18 are exactly E, legal
    suffix kept — e.g. vegalavanderialtda). Falls back to slug(A) when E is empty or not a valid DNS label."""
    e = (cells.get("E") or "").strip().lower()
    return e if LABEL_RX.match(e) else slug(cells.get("A") or "")


def _company_keys(cells: dict) -> list[tuple[str, str]]:
    keys = [("A", re.sub(r"\s+", " ", (cells.get("A") or "").strip().casefold()))]
    if digits := re.sub(r"\D", "", cells.get("J") or ""):
        keys.append(("J", digits))
    return [k for k in keys if k[1]]


def domains_by_company(rows) -> dict:
    """(A name | J registration number) → [(row, B)] for every row that already has a domain in B."""
    out: dict = {}
    for r in rows:
        if b := r.cells["B"].strip():
            for k in _company_keys(r.cells):
                out.setdefault(k, []).append((r.row, b))
    return out


def already_has_domain(index: dict, cells: dict) -> str | None:
    for k in _company_keys(cells):
        if hits := index.get(k):
            row, b = hits[0]
            return f"Doanh nghiệp này đã có miền {b} ở dòng {row} ({'cùng tên A' if k[0] == 'A' else 'cùng số J'}) — không tạo thêm"
    return None


def scan(s: Session) -> dict:
    rows = Sheets().read_rows()
    has = domains_by_company(rows)
    out, excluded = [], []
    for r in rows:
        c = r.cells
        if c["B"].strip():
            continue
        if not c["A"].strip():
            excluded.append({"row": r.row, "reason": "Thiếu tên doanh nghiệp (A)"})
            continue
        if why := already_has_domain(has, c):
            excluded.append({"row": r.row, "reason": why})
            continue
        flags = []
        if not c["K"].strip():
            flags.append("Chưa có link K")
        if not c["E"].strip():
            flags.append("Thiếu cột E")
        out.append({"row": r.row, "A": c["A"], "D": c["D"], "E": c["E"], "F": c["F"], "G": c["G"], "H": c["H"], "I": c["I"],
                    "J": c["J"], "K": c["K"], "flags": flags, "label": label_for(c)})
    existing_b = sorted({r.cells["B"].strip().lower() for r in rows if r.cells["B"].strip()})
    return {"total": len(rows), "with_b": len(existing_b), "rows": out, "excluded": excluded, "existing_b": existing_b,
            "tab": Sheets().tab}


def validate_items(s: Session, items: list[dict]) -> tuple[list[dict], dict]:
    """items: [{row, company, root, label, …}] — the UI is never trusted: only ticked, usable roots, valid labels."""
    ok, refused = [], {}
    taken = set()
    for it in items:
        label, root = (it.get("label") or "").lower(), it.get("root") or ""
        r = s.get(RootDomain, root)
        why = None
        if not r:
            why = "Chưa gán miền gốc"
        elif not r.selected:
            why = f"Miền gốc {root} chưa được tích chọn"
        else:
            why = root_issue(r, s.get(Nick, r.nick_id))
        if not why and not LABEL_RX.match(label):
            why = "Tên miền phụ chỉ gồm a–z, 0–9, “-”, tối đa 63 ký tự"
        fqdn = f"{label}.{root}"
        if not why and fqdn in taken:
            why = "Trùng với dòng khác trong lượt này"
        if why:
            refused[it.get("row")] = why
            continue
        taken.add(fqdn)
        ok.append({**it, "row": it["row"], "company": it.get("company", ""), "root": root, "label": label, "fqdn": fqdn, "nick_id": r.nick_id})
    return ok, refused


def enqueue_rows(s: Session, items: list[dict]) -> dict:
    """One job per subdomain. Normally fed by a confirmed preview plan (dns_plan.take_plan)."""
    ok, refused = validate_items(s, items)
    queued = []
    for it in ok:
        payload = {k: it[k] for k in ("row", "company", "root", "label", "fqdn", "nick_id")}
        if it.get("domain_id") is not None:
            payload["domain_id"] = it["domain_id"]  # iNET ID seen in the preview — must still match when writing
        job, created = enqueue(s, "domain_create", f"domain:{it['fqdn']}", payload, resource=f"nick:{it['nick_id']}")
        queued.append({"row": it["row"], "job_id": job.id, "created": created})
    return {"queued": queued, "refused": refused}


def host_plan(cp: CPanel, root: str, fqdn: str, nick: Nick) -> dict:
    """Read-only, before anything is written: how `fqdn` will be created on this nick's cPanel, and that it does not
    exist and will not take over a folder. Raises Permanent with the reason when it must stop."""
    how = cp.creation_mode(root)
    if not how["mode"]:
        raise Permanent(f"Dừng trước khi tạo: {how['reason']}. B giữ trống.")
    if how["ip"] and how["ip"] != nick.ip:
        raise Permanent(f"IP hosting của {how['parent']} trên cPanel ({how['ip']}) khác IP của {nick.name} ({nick.ip}) — dừng")
    if cp.subdomain(fqdn) or cp.addon(fqdn):
        raise Permanent(f"{fqdn} đã tồn tại trên cPanel — không tạo lại. Đổi tên hoặc miền gốc")
    if how["mode"] == "addon" and cp.subdomain(f"{fqdn}.{how['main']}"):  # addaddondomain would reuse it and its folder
        raise Permanent(f"Đã có subdomain {fqdn}.{how['main']} trên cPanel — addon sẽ dùng lại thư mục cũ, dừng")
    if cp.folder_exists(f"public_html/{fqdn}"):
        raise Permanent(f"Thư mục public_html/{fqdn} đã có trên hosting — không dùng chung thư mục của miền khác, dừng")
    how["say"] = (f"{root} là {'miền chính' if how['kind'] == 'main' else 'addon domain'} trên tài khoản → tạo subdomain (SubDomain::addsubdomain)"
                  if how["mode"] == "subdomain" else
                  f"{root} không nằm trên tài khoản → tạo addon domain gắn vào {how['main']} (AddonDomain::addaddondomain), thư mục public_html/{fqdn}")
    return how


def _gate(s: Session, root: str):
    r = s.get(RootDomain, root)
    if not r or not r.selected:
        raise Permanent(f"Dừng trước khi tạo: miền gốc {root} không còn được tích chọn. B giữ trống.")
    if why := root_issue(r, s.get(Nick, r.nick_id)):
        raise Permanent(f"Dừng trước khi tạo: {root} — {why}. B giữ trống.")
    return r


@handler("domain_create")
def _create(ctx: JobContext):
    s, p, st = ctx.session, ctx.job.payload, ctx.state
    nick = s.get(Nick, p["nick_id"])
    fqdn, cell = p["fqdn"], f"B{p['row']}"
    sheets = Sheets()

    if not st.get("dns_created"):
        ctx.step("Kiểm tra trước khi tạo")
        root = _gate(s, p["root"])
        if sheets.read_cell(cell).strip():
            raise Conflict(f"Ô {cell} đã có dữ liệu — không tạo miền, không ghi đè")
        cp = CPanel(nick.id, nick.cpanel_host)
        how = host_plan(cp, p["root"], fqdn, nick)
        ctx.checkpoint(host_mode=how["mode"], host_main=how.get("main"))
        ctx.log(f"cPanel: {how['say']}", "ok")
        existing = net.resolve_a(fqdn)
        if existing and set(existing) != {nick.ip}:
            raise Permanent(f"{fqdn} đã có bản ghi A ({', '.join(existing)}) — không ghi đè")
        if existing:  # e.g. added by an earlier attempt that stopped before saving its progress
            ctx.log(f"DNS công khai: {fqdn} đã trỏ {nick.ip} — iNET sẽ được kiểm tra, chỉ thêm nếu chưa có", "warn")
        ctx.log(f"Không trùng: Sheet, cPanel, DNS · {fqdn} → {nick.name} ({nick.ip})", "ok")

        ctx.step("Tạo bản ghi A")
        if why := dns_plan.gate(dns_plan.get_switch(s), [fqdn]):
            raise NotAvailable("Ghi DNS thật", why)
        if root.dns_host != "inet":
            raise NotAvailable("DNS", f"{p['root']} không dùng DNS iNET — chưa có API nhà cung cấp DNS này")
        rec = Inet(nick.id, log=ctx.log).create_a_record(p["root"], p["label"], nick.ip, expect_domain_id=p.get("domain_id"))
        ctx.checkpoint(dns_created=True, dns_record=rec)
        ctx.log(f"Bản ghi A {fqdn} → {nick.ip}: " + ("đã có sẵn, không gửi lại" if rec["result"] == "exists" else "đã thêm trên iNET"), "ok")

    if not st.get("host_created"):
        ctx.step("Tạo miền trên cPanel")
        _gate(s, p["root"])
        cp = CPanel(nick.id, nick.cpanel_host)
        want = f"public_html/{fqdn}"
        if st.get("host_mode") == "addon":
            # an earlier attempt whose answer was lost may have created it (the pre-check found none before it)
            if found := cp.addon(fqdn):
                ctx.log(f"cPanel: addon {fqdn} đã có từ lượt trước → không tạo lại", "warn")
            else:
                api = cpanel_api2.choose(cp, cfg(f"CPANEL_ADDON_API_{nick.id.upper()}") or "auto")
                used = cpanel_api2.add_addon(cp, fqdn, want, api)
                found = cp.addon(fqdn)  # confirm with the read API whatever the create call answered
                if not found:
                    raise Permanent(f"{used} không báo lỗi nhưng cPanel không liệt kê {fqdn} — kiểm tra trên cPanel trước khi chạy lại")
                ctx.log(f"cPanel: đã tạo addon domain {fqdn} ({used})", "ok")
            if (found.get("basedir") or "").strip("/") != want:
                raise Conflict(f"{fqdn} trên cPanel dùng thư mục {found.get('basedir')} (không phải {want}) — không ghi đè, B giữ trống")
        elif cp.subdomain(fqdn):  # created by an earlier attempt whose answer was lost (before it, the pre-check found none)
            ctx.log(f"cPanel: {fqdn} đã có từ lượt trước → không tạo lại", "warn")
        else:
            cp.add_subdomain(p["label"], p["root"], want)
            ctx.log(f"cPanel: đã tạo subdomain {fqdn}", "ok")
        ctx.checkpoint(host_created=True)

    ctx.step("Xác minh DNS trỏ đúng IP")
    ips = net.resolve_a(fqdn)
    if nick.ip not in ips:
        wait_or_fail(st, "dns_wait_since", DNS_WAIT_HOURS, f"DNS {fqdn} chưa trỏ về {nick.ip} (đang: {', '.join(ips) or 'chưa có'})", 300)
    ctx.log(f"DNS {fqdn} → {nick.ip}", "ok")

    ctx.step("Đọc lại ô B rồi ghi")
    company_now = sheets.read_cell(f"A{p['row']}").strip()
    if p.get("company") and company_now.casefold() != p["company"].strip().casefold():
        ctx.checkpoint(outcome="conflict", orphan={"fqdn": fqdn, "row_now": company_now})
        raise Conflict(f"Dòng {p['row']} giờ là “{company_now}”, không còn là “{p['company']}” (Sheet đã đổi thứ tự?) — "
                       f"không ghi B. Miền {fqdn} đã tạo, lưu vào “Tài nguyên chưa gắn”")
    live = sheets.read_cell(cell)
    if live.strip():
        ctx.checkpoint(outcome="conflict", orphan={"fqdn": fqdn, "found_b": live})
        raise Conflict(f"Ô {cell} đã có “{live}” khi ghi — không ghi đè. Miền {fqdn} đã tạo, lưu vào “Tài nguyên chưa gắn”")
    sheets.write_cell(cell, fqdn)
    s.add(SheetWrite(tab=sheets.tab, range=cell, old_value="", new_value=fqdn, job_id=ctx.job.id))
    ctx.checkpoint(written_b=fqdn)
    ctx.log(f"Ghi {cell} = {fqdn} · cột C giữ nguyên", "ok")
    if dns_plan.mark_trial(s, fqdn, ctx.job.id):
        ctx.log(f"Chạy thử thành công trên {fqdn}. Ghi thật sẽ tự khoá lại; anh mở lại thì mới chạy được miền khác (vẫn xem trước và xác nhận)", "ok")
