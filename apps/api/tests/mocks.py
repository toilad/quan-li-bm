"""respx routes for the external services, with in-memory state so tests can assert what was written."""
import json
import re

import httpx
import respx


class FakeSheet:
    """Sheet rows start at 3. cells: {row: {col: value}}."""

    def __init__(self, rows: dict[int, dict] | None = None):
        self.rows = rows or {}
        self.appends, self.writes = [], []
        self.links: dict[str, str] = {}

    def values(self, start: int = 3):
        if not self.rows:
            return []
        last = max(self.rows)
        return [[self.rows.get(r, {}).get(c, "") for c in "ABCDEFGHIJKL"] for r in range(start, last + 1)]

    def install(self, mock: respx.MockRouter, fail_append: int = 0, ghost_append: int = 0):
        """fail_append: n appends refused (503). ghost_append: n appends WRITTEN but answered 503 (lost reply)."""
        state = {"fail": fail_append, "ghost": ghost_append}
        base = "https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET/values/"

        def get(request):
            rng = httpx.URL(str(request.url)).path.split("/values/")[1].replace("%21", "!").replace("%27", "'").replace("%3A", ":")
            m = re.search(r"!([A-L])(\d+)$", rng)
            if m and ":" not in rng:
                return httpx.Response(200, json={"values": [[self.rows.get(int(m.group(2)), {}).get(m.group(1), "")]]})
            one = re.search(r"!A(\d+):K(\d+)$", rng)
            if one and one.group(1) == one.group(2):  # a single row A–K
                cells = self.rows.get(int(one.group(1)), {})
                vals = [cells.get(c, "") for c in "ABCDEFGHIJK"]
                return httpx.Response(200, json={"values": [vals] if any(vals) else []})
            open_rng = re.search(r"!A(\d+):[KL]$", rng)  # "A2:L", "A3:K": rows from that one down, like Google
            return httpx.Response(200, json={"values": self.values(int(open_rng.group(1)) if open_rng else 3)})

        def put(request):
            rng = httpx.URL(str(request.url)).path.split("/values/")[1].replace("%21", "!").replace("%3A", ":")
            one = re.search(r"!A(\d+):K(\d+)$", rng)
            if one:  # a whole new row A–K (append_row writes the first empty row)
                if state["fail"]:
                    state["fail"] -= 1
                    return httpx.Response(503, json={"error": {"message": "backend error"}})
                vals = json.loads(request.content)["values"][0]
                self.rows[int(one.group(1))] = dict(zip("ABCDEFGHIJK", vals))
                self.appends.append(vals)
                if state["ghost"]:
                    state["ghost"] -= 1
                    return httpx.Response(503, json={"error": {"message": "backend error"}})
                return httpx.Response(200, json={"updatedRange": f"'Phoi US'!A{one.group(1)}:K{one.group(1)}"})
            m = re.search(r"!([A-L])(\d+)$", rng)
            val = json.loads(request.content)["values"][0][0]
            self.rows.setdefault(int(m.group(2)), {})[m.group(1)] = val
            self.writes.append((f"{m.group(1)}{m.group(2)}", val))
            return httpx.Response(200, json={"updatedCells": 1})

        def append(request):
            if state["fail"]:
                state["fail"] -= 1
                return httpx.Response(503, json={"error": {"message": "backend error"}})
            vals = json.loads(request.content)["values"][0]
            row = max(list(self.rows) + [2]) + 1
            self.rows[row] = dict(zip("ABCDEFGHIJK", vals))
            self.appends.append(vals)
            if state["ghost"]:
                state["ghost"] -= 1
                return httpx.Response(503, json={"error": {"message": "backend error"}})
            return httpx.Response(200, json={"updates": {"updatedRange": f"'Phoi US'!A{row}:K{row}"}})

        def batch(request):  # updateCells with a link (K = "Xem phôi")
            for req in json.loads(request.content)["requests"]:
                u = req["updateCells"]
                r, c = u["range"]["startRowIndex"] + 1, "ABCDEFGHIJKL"[u["range"]["startColumnIndex"]]
                v = u["rows"][0]["values"][0]
                text, link = v["userEnteredValue"]["stringValue"], v["textFormatRuns"][0]["format"]["link"]["uri"]
                self.rows.setdefault(r, {})[c] = text
                self.links[f"{c}{r}"] = link
                self.writes.append((f"{c}{r}", f"{text} → {link}"))
            return httpx.Response(200, json={"replies": [{}]})

        mock.post("https://oauth2.googleapis.com/token").respond(200, json={"access_token": "tok", "expires_in": 3600})
        mock.get("https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET").respond(
            200, json={"sheets": [{"properties": {"sheetId": 7, "title": "Phoi US"}}]})
        mock.post("https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET:batchUpdate").mock(side_effect=batch)
        mock.get(url__startswith=base).mock(side_effect=get)
        mock.put(url__startswith=base).mock(side_effect=put)
        mock.post(url__regex=r".*/values/.*:append.*").mock(side_effect=append)


def install_drive(mock, md5_of=lambda body: None, calls=None, existing: dict | None = None):
    """existing: {md5: file} already on Drive (found via appProperties qlbm_md5)."""
    existing = existing if existing is not None else {}

    def search(request):
        q = request.url.params["q"]
        md5 = re.search(r"value='([0-9a-f]+)'", q).group(1)
        return httpx.Response(200, json={"files": [existing[md5]] if md5 in existing else []})

    mock.get(url__startswith="https://www.googleapis.com/drive/v3/files").mock(side_effect=search)

    def upload(request):
        if calls is not None:
            calls.append(request)
        body = request.content
        start = body.index(b"%PDF")
        end = body.rindex(b"\r\n--")
        import hashlib

        md5 = md5_of(body) or hashlib.md5(body[start:end]).hexdigest()
        meta = json.loads(body.split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0])
        assert meta["appProperties"]["qlbm_md5"]  # every upload is tagged so it can be found again
        existing[meta["appProperties"]["qlbm_md5"]] = {"id": "DRIVE123", "md5Checksum": md5, "webViewLink": "https://drive.google.com/file/d/DRIVE123/view"}
        return httpx.Response(200, json={"id": "DRIVE123", "md5Checksum": md5, "webViewLink": "https://drive.google.com/file/d/DRIVE123/view"})

    mock.post(url__startswith="https://www.googleapis.com/upload/drive/v3/files").mock(side_effect=upload)


def install_doh(mock, answers: dict[str, list[str]]):
    def doh(request):
        name = request.url.params["name"]
        ips = answers.get(name, [])
        return httpx.Response(200, json={"Status": 0, "Answer": [{"name": name, "type": 1, "data": ip} for ip in ips]})

    from wg_core.integrations import net

    net.system_resolve = lambda name: list(answers.get(name, []))  # same answers as the fake DoH
    mock.get(url__startswith="https://cloudflare-dns.com/dns-query").mock(side_effect=doh)
    mock.get(url__startswith="https://dns.google/resolve").mock(side_effect=doh)


def cp_ok(data=None):
    return httpx.Response(200, json={"status": 1, "data": data, "errors": None})


def cp_err(msg):
    return httpx.Response(200, json={"status": 0, "data": None, "errors": [msg]})


def anthropic_json(payload: dict):
    return httpx.Response(200, json={
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    })


INET = "https://developers.inet.vn/api/gateway/v1"


def wrap(data, endpoint):
    """The iNET gateway envelope, as answered live (tests/fixtures/inet_live_samples.json)."""
    return httpx.Response(200, json={"success": True, "data": data, "meta": {
        "endpoint": endpoint, "latency_ms": 5, "timestamp": "2026-10-18T15:35:00.000Z", "request_id": "00000000-0000-0000-0000-000000000000"}})


class FakeInet:
    """In-memory iNET account following the documented shapes. PATCH applies each recordList item as one
    operation (ACTION_ADD / ACTION_DELETE). `drop_on_add` simulates a server that loses other records."""

    def __init__(self, domains: dict[str, dict] | None = None, drop_on_add: bool = False):
        # {name: {"id": int, "ns": [...], "records": [{id, name, type, data, ttl}]}}
        self.domains = domains or {}
        self.patches, self.drop_on_add, self._next = [], drop_on_add, 9000

    def install(self, mock):
        by_id = lambda i: next(d for d in self.domains.values() if d["id"] == i)  # noqa: E731

        def list_(request):
            name = request.url.params.get("name")
            items = [{"id": d["id"], "name": n, "status": "active"} for n, d in self.domains.items() if not name or n == name]
            return wrap({"content": items, "totalPages": 1, "totalElements": len(items), "size": 100, "number": 0}, "/v1/domain")

        def detail(request):
            i = int(request.url.path.rstrip("/").split("/")[-1])
            d = by_id(i)
            return wrap({"id": i, "nsList": [{"id": k, "hostname": h} for k, h in enumerate(d["ns"])]}, f"/v1/domain/{i}")

        def records(request):
            i = int(request.url.path.split("/")[-2])
            return wrap({"id": i, "recordList": by_id(i)["records"]}, f"/v1/domain/{i}/record")

        def patch(request):
            i = int(request.url.path.split("/")[-2])
            d, body = by_id(i), json.loads(request.content)
            self.patches.append(body)
            for it in body["recordList"]:
                if it["action"] == "ACTION_ADD":
                    self._next += 1
                    if self.drop_on_add:
                        d["records"] = d["records"][1:]
                    d["records"].append({"id": self._next, "name": it["name"], "type": it["type"], "data": it["data"], "ttl": int(it["ttl"])})
                elif it["action"] == "ACTION_DELETE":
                    d["records"] = [r for r in d["records"] if r["id"] != it["id"]]
            return wrap({"id": i, "status": "active", "recordList": d["records"]}, f"/v1/domain/{i}/record")

        mock.get(url__regex=rf"^{re.escape(INET)}/domain(\?.*)?$").mock(side_effect=list_)
        mock.get(url__regex=rf"^{re.escape(INET)}/domain/\d+$").mock(side_effect=detail)
        mock.get(url__regex=rf"^{re.escape(INET)}/domain/\d+/record$").mock(side_effect=records)
        return mock.patch(url__regex=rf"^{re.escape(INET)}/domain/\d+/record$").mock(side_effect=patch)


def cp_account(mock, cp, main="levantoan.000web.com", addon=("huxma.life", "sustainlife.io.vn"), parked=(), subs=(), dirs=()):
    """One cPanel account as DomainInfo::list_domains sees it, plus the folders in public_html (Fileman::list_files
    types=dir). Defaults: huxma.life is an addon domain of nick 1, so names under it are created as subdomains."""
    import re as _re

    mock.get(f"{cp}/DomainInfo/list_domains").mock(return_value=cp_ok({
        "main_domain": main, "addon_domains": list(addon), "sub_domains": list(subs), "parked_domains": list(parked)}))
    mock.get(url__regex=rf"^{_re.escape(cp)}/Fileman/list_files\?.*types=dir").mock(
        return_value=cp_ok([{"file": d, "type": "dir"} for d in dirs]))
