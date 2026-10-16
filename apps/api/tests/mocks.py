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

    def values(self):
        if not self.rows:
            return []
        last = max(self.rows)
        return [[self.rows.get(r, {}).get(c, "") for c in "ABCDEFGHIJKL"] for r in range(3, last + 1)]

    def install(self, mock: respx.MockRouter, fail_append: int = 0):
        state = {"fail": fail_append}
        base = "https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET/values/"

        def get(request):
            rng = httpx.URL(str(request.url)).path.split("/values/")[1]
            m = re.search(r"!([A-L])(\d+)$", rng.replace("%21", "!").replace("%27", "'"))
            if m and ":" not in rng:
                return httpx.Response(200, json={"values": [[self.rows.get(int(m.group(2)), {}).get(m.group(1), "")]]})
            return httpx.Response(200, json={"values": self.values()})

        def put(request):
            rng = httpx.URL(str(request.url)).path.split("/values/")[1].replace("%21", "!")
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
            return httpx.Response(200, json={"updates": {"updatedRange": f"'Phoi US'!A{row}:K{row}"}})

        mock.post("https://oauth2.googleapis.com/token").respond(200, json={"access_token": "tok", "expires_in": 3600})
        mock.get(url__startswith=base).mock(side_effect=get)
        mock.put(url__startswith=base).mock(side_effect=put)
        mock.post(url__regex=r".*/values/.*:append.*").mock(side_effect=append)


def install_drive(mock, md5_of=lambda body: None, calls=None):
    def upload(request):
        if calls is not None:
            calls.append(request)
        body = request.content
        start = body.index(b"%PDF")
        end = body.rindex(b"\r\n--")
        import hashlib

        md5 = md5_of(body) or hashlib.md5(body[start:end]).hexdigest()
        return httpx.Response(200, json={"id": "DRIVE123", "md5Checksum": md5, "webViewLink": "https://drive.google.com/file/d/DRIVE123/view"})

    mock.post(url__startswith="https://www.googleapis.com/upload/drive/v3/files").mock(side_effect=upload)


def install_doh(mock, answers: dict[str, list[str]]):
    def doh(request):
        name = request.url.params["name"]
        ips = answers.get(name, [])
        return httpx.Response(200, json={"Status": 0, "Answer": [{"name": name, "type": 1, "data": ip} for ip in ips]})

    mock.get(url__startswith="https://cloudflare-dns.com/dns-query").mock(side_effect=doh)


def cp_ok(data=None):
    return httpx.Response(200, json={"result": {"status": 1, "data": data, "errors": None}})


def cp_err(msg):
    return httpx.Response(200, json={"result": {"status": 0, "data": None, "errors": [msg]}})


def anthropic_json(payload: dict):
    return httpx.Response(200, json={
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    })
