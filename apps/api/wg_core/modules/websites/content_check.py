"""Reject AI copy that states anything the Sheet does not support (numbers, awards, clients…)."""
import re

BANNED = [
    r"\baward", r"\bcertified\b", r"\baccredited\b", r"#\s*1\b", r"\bbest\b", r"\bleading\b", r"\bnumber one\b",
    r"\btrusted by\b", r"\bclients? include\b", r"\byears? of experience\b", r"\bsince \d{4}\b", r"\bguarantee",
    r"\btestimonial", r"\brated\b", r"\bfounded in\b", r"\bestablished in\b",
]


def _texts(copy: dict) -> list[str]:
    out = [copy.get("tagline", ""), copy.get("intro", "")] + list(copy.get("about", []))
    for s in copy.get("services", []):
        out += [s.get("title", ""), s.get("description", "")]
    for f in copy.get("faq", []):
        out += [f.get("question", ""), f.get("answer", "")]
    return out


def problems(copy: dict, facts: dict) -> list[str]:
    allowed_numbers = set(re.findall(r"\d+", " ".join(str(v) for v in facts.values())))
    found = []
    for t in _texts(copy):
        for rx in BANNED:
            if m := re.search(rx, t, re.IGNORECASE):
                found.append(f"cụm “{m.group(0)}” (không có căn cứ trong Sheet)")
        for n in re.findall(r"\d+", t):
            if n not in allowed_numbers:
                found.append(f"số “{n}” không có trong Sheet")
    if len(copy.get("services", [])) != 3:
        found.append("cần đúng 3 dịch vụ")
    if not 4 <= len(copy.get("faq", [])) <= 5:
        found.append("cần 4–5 câu hỏi đáp")
    return sorted(set(found))
