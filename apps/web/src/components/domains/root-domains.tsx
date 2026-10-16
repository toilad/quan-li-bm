"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Globe, RefreshCw, CheckSquare, Square, Lock, Ban, HelpCircle, CheckCircle2 } from "lucide-react";
import { EXPIRY_WARN_DAYS, daysLeft, rootIssue, type Nick, type RootDomain } from "@/lib/domain-mock";
import { SimTag } from "./ui";
import { rootBusy, type DomainDispatch, type DomainState } from "./use-domain-queue";

/** Today's date, set only in the browser — the page is prerendered, so day counts must not be a build-time snapshot. */
function useToday() {
  const [today, setToday] = useState<Date | null>(null);
  useEffect(() => setToday(new Date()), []);
  return today;
}

const fmtDate = (iso: string) => iso.split("-").reverse().join("/");

/** Every domain of every nick, each with its own tick box. Only ticked, usable domains are used to create subdomains. */
export function RootDomains({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const today = useToday();
  const sel = new Set(state.selectedRoots);
  const all = state.nicks.flatMap((n) => n.roots.map((r) => ({ r, n })));
  const usable = all.filter(({ r, n }) => !rootIssue(r, n));
  const usableTicked = usable.filter(({ r }) => sel.has(r.name)).length;
  const assigned = (root: string) => state.rows.filter((x) => x.root === root && x.status !== "done" && x.status !== "conflict").length;

  return (
    <section className="panel p-5">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-violet-500/15 text-violet-200">
            <Globe className="size-5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[16px] font-semibold">Miền gốc dùng để tạo miền phụ</h2>
              <SimTag />
            </div>
            <p className="text-[12.5px] text-fg-muted">
              Toàn bộ tên miền của từng nick (bản chép từ portal iNET 16/10/2026 — đọc qua API iNET chưa khả dụng). Tích miền nào thì app chỉ phân bổ công ty vào miền đó.
            </p>
            <p className="mt-0.5 text-[11.5px] text-fg-subtle">Lựa chọn lưu ở database · tải lần cuối {state.lastSync}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={clsx(
              "rounded-full border px-3 py-1 text-[12px] font-semibold",
              usableTicked ? "border-emerald-400/30 text-emerald-300" : "border-rose-400/40 text-rose-300",
            )}
          >
            Đã chọn {usableTicked}/{usable.length} miền dùng được
          </span>
          <Btn onClick={() => dispatch({ type: "pickRoots", roots: usable.map(({ r }) => r.name), on: true })}>
            <CheckSquare className="size-4" /> Chọn tất cả
          </Btn>
          <Btn onClick={() => dispatch({ type: "pickRoots", roots: all.map(({ r }) => r.name), on: false })}>
            <Square className="size-4" /> Bỏ chọn tất cả
          </Btn>
          <Btn onClick={() => dispatch({ type: "sync" })} title="Tải lại danh sách từ backend. Đọc danh sách miền qua API iNET: chưa khả dụng (cấu trúc trả về chưa có trong tài liệu)">
            <RefreshCw className="size-4" /> Tải lại
          </Btn>
        </div>
      </header>

      {!usableTicked && (
        <p className="mb-3 flex items-center gap-2 rounded-xl border border-rose-400/30 bg-rose-500/[0.08] px-3.5 py-2.5 text-[12.5px] text-rose-200">
          <Ban className="size-4 shrink-0" /> Chưa chọn miền gốc nào — không thể bắt đầu tạo miền.
        </p>
      )}

      <div className="space-y-4">
        {state.nicks.map((n) => (
          <NickGroup key={n.id} nick={n} sel={sel} state={state} dispatch={dispatch} today={today} assigned={assigned} />
        ))}
      </div>

      <p className="mt-3 text-[11.5px] text-fg-subtle">
        Miền tạm ngưng, hết hạn hoặc API hiện tại không ghi được DNS thì không tích được. Miền đang có dòng chạy (hoặc đã tạo DNS chưa ghi B) không bỏ chọn được tới khi xong.
        Lựa chọn lưu trong database của app.
      </p>
    </section>
  );
}

function NickGroup({
  nick, sel, state, dispatch, today, assigned,
}: {
  nick: Nick; sel: Set<string>; state: DomainState; dispatch: DomainDispatch; today: Date | null; assigned: (root: string) => number;
}) {
  const usable = nick.roots.filter((r) => !rootIssue(r, nick));
  const ticked = nick.roots.filter((r) => sel.has(r.name)).length;

  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-ink-850/70 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px]">
          <span className="font-semibold">{nick.name}</span>
          <span className="text-fg-subtle">Hosting <span className="font-mono text-fg-muted">{nick.hosting ?? "—"}</span> · IP <span className="font-mono text-fg-muted">{nick.ip}</span></span>
          <span className="text-fg-muted">{ticked}/{nick.roots.length} miền đã chọn</span>
          {!nick.enabled && <span className="text-amber-300">Nick đang tắt</span>}
        </div>
        <div className="flex gap-1.5">
          <Btn small onClick={() => dispatch({ type: "checkNick", id: nick.id })} label={`Kiểm tra hosting của ${nick.name}`} title="Đọc danh sách miền trên cPanel + iNET, không thay đổi gì">
            Kiểm tra hosting (chỉ đọc)
          </Btn>
          <Btn small onClick={() => dispatch({ type: "pickRoots", roots: usable.map((r) => r.name), on: true })} label={`Chọn tất cả miền của ${nick.name}`}>
            Chọn tất cả
          </Btn>
          <Btn small onClick={() => dispatch({ type: "pickRoots", roots: nick.roots.map((r) => r.name), on: false })} label={`Bỏ chọn tất cả miền của ${nick.name}`}>
            Bỏ chọn
          </Btn>
        </div>
      </div>
      <div className="scroll-thin overflow-x-auto">
        <table className="w-full min-w-[1080px] text-left text-[12.5px]">
          <thead>
            <tr className="border-b border-line/70 text-[11px] uppercase tracking-wide text-fg-subtle">
              <th className="w-10 py-2 pl-4" />
              <th className="py-2 font-medium">Miền gốc</th>
              <th className="py-2 font-medium">Nick</th>
              <th className="py-2 font-medium">IP hosting</th>
              <th className="py-2 font-medium">Trạng thái</th>
              <th className="py-2 font-medium">Hết hạn</th>
              <th className="py-2 font-medium">DNS</th>
              <th className="py-2 font-medium">Ghi bản ghi qua API</th>
              <th className="py-2 pr-4 text-right font-medium">Dòng đang gán</th>
            </tr>
          </thead>
          <tbody>
            {nick.roots.map((r) => {
              const issue = rootIssue(r, nick);
              const busy = rootBusy(r.name, state.rows);
              const on = sel.has(r.name);
              const disabled = on ? busy : !!issue;
              const n = assigned(r.name);
              return (
                <tr key={r.name} className={clsx("border-b border-line/50 last:border-0", issue && "bg-rose-500/[0.03]", on && !issue && "bg-brand/[0.05]")}>
                  <td className="py-2 pl-4">
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={disabled}
                      onChange={(e) => dispatch({ type: "pickRoots", roots: [r.name], on: e.target.checked })}
                      aria-label={`Chọn miền ${r.name}`}
                      title={busy && on ? "Đang có dòng chạy trên miền này — bỏ chọn sau khi xong" : issue ?? undefined}
                      className="size-4 accent-[#4f7cff] disabled:opacity-30"
                    />
                  </td>
                  <td className="py-2 pr-3 font-mono">
                    {r.name}
                    {busy && <Lock className="ml-1.5 inline size-3 text-fg-subtle" aria-label="Đang có tác vụ" />}
                  </td>
                  <td className="py-2 pr-3 text-fg-muted">{nick.name}</td>
                  <td className="py-2 pr-3 font-mono text-fg-muted">{nick.ip}</td>
                  <td className="py-2 pr-3"><StateCell r={r} today={today} /></td>
                  <td className="py-2 pr-3"><ExpiryCell iso={r.expires} today={today} /></td>
                  <td className="py-2 pr-3 text-[11.5px]"><DnsCell r={r} /></td>
                  <td className="max-w-[260px] py-2 pr-3 text-[11.5px]"><ApiCell r={r} nick={nick} issue={issue} /></td>
                  <td className={clsx("py-2 pr-4 text-right font-mono", n ? "text-fg" : "text-fg-subtle")}>{n || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StateCell({ r, today }: { r: RootDomain; today: Date | null }) {
  if (r.suspended) return <Tag cls="text-rose-300 border-rose-400/30">Tạm ngưng</Tag>;
  if (today && daysLeft(r.expires, today) < 0) return <Tag cls="text-rose-300 border-rose-400/30">Hết hạn</Tag>;
  return <Tag cls="text-emerald-300 border-emerald-400/25">Hoạt động</Tag>;
}

function ExpiryCell({ iso, today }: { iso: string; today: Date | null }) {
  const d = today ? daysLeft(iso, today) : null;
  return (
    <div>
      <div className="font-mono">{fmtDate(iso)}</div>
      {d !== null && (
        <div className={clsx("text-[11px]", d < 0 ? "text-rose-300" : d <= EXPIRY_WARN_DAYS ? "text-amber-300" : "text-fg-subtle")}>
          {d < 0 ? `quá hạn ${-d} ngày` : `còn ${d} ngày`}
          {d >= 0 && d <= EXPIRY_WARN_DAYS && " — miền phụ mất theo"}
        </div>
      )}
    </div>
  );
}

function DnsCell({ r }: { r: RootDomain }) {
  const ns = { inet: "NS iNET", cpanel: "NS host cPanel", other: "NS Cloudflare", unknown: "NS chưa rõ" }[r.dnsHost];
  return (
    <div>
      <div className={r.dnsHost === "inet" || r.dnsHost === "cpanel" ? "text-fg-muted" : "text-rose-300"}>{ns}</div>
      <div className="text-fg-subtle">{r.apexOnHosting ? "Miền gốc đã trỏ hosting" : "Miền gốc chưa trỏ (không ảnh hưởng miền phụ)"}</div>
      {r.onCpanel === true && <div className="text-emerald-300/90">Có trên cPanel</div>}
      {r.onCpanel === false && <div className="text-rose-300">Chưa có trên cPanel — không tạo được miền phụ</div>}
    </div>
  );
}

function ApiCell({ r, nick, issue }: { r: RootDomain; nick: Nick; issue: string | null }) {
  if (issue)
    return (
      <span className="flex items-start gap-1 text-rose-300">
        <Ban className="mt-px size-3.5 shrink-0" /> {issue}
      </span>
    );
  const api = r.dnsHost === "cpanel" ? "DNS API cPanel" : "API DNS iNET";
  if (nick.api.dns.state === "ok")
    return <span className="flex items-center gap-1 text-emerald-300"><CheckCircle2 className="size-3.5" /> {api}: được</span>;
  return (
    <span className="flex items-start gap-1 text-fg-subtle">
      <HelpCircle className="mt-px size-3.5 shrink-0" />
      <span>
        {api}: hỗ trợ · chưa kiểm tra quyền
        {nick.api.dns.note && <span className="block text-[10.5px]">{nick.api.dns.note}</span>}
      </span>
    </span>
  );
}

function Tag({ children, cls }: { children: React.ReactNode; cls: string }) {
  return <span className={clsx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium", cls)}>{children}</span>;
}

function Btn({ children, onClick, small, label, title }: { children: React.ReactNode; onClick: () => void; small?: boolean; label?: string; title?: string }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={title}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-lg font-semibold hover:bg-white/[0.11]",
        small ? "bg-white/[0.05] px-2.5 py-1 text-[11.5px]" : "bg-white/[0.07] px-3 py-1.5 text-[12.5px]",
      )}
    >
      {children}
    </button>
  );
}

