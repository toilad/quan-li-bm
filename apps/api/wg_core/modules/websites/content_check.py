"""Reject AI copy that states anything the Sheet does not support (numbers, awards, clients…)."""
import re

BANNED = [
    r"\baward", r"\bcertified\b", r"\baccredited\b", r"#\s*1\b", r"\bbest\b", r"\bleading\b", r"\bnumber one\b",
    r"\btrusted by\b", r"\bclients? include\b", r"\byears? of experience\b", r"\bsince \d{4}\b", r"\bguarantee",
    r"\btestimonial", r"\brated\b", r"\bfounded in\b", r"\bestablished in\b",
]


def _texts(copy: dict) -> list[str]:
    out = [v for k, v in copy.items() if isinstance(v, str)]
    for key in ("services", "why_choose_us"):
        for s in copy.get(key, []):
            out += [s.get("title", ""), s.get("description", "")]
    for f in copy.get("faqs", []):
        out += [f.get("q", ""), f.get("a", "")]
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
    if len(copy.get("why_choose_us", [])) != 3:
        found.append("cần đúng 3 lý do “why choose us”")
    if not 4 <= len(copy.get("faqs", [])) <= 8:
        found.append("cần 4–8 câu hỏi đáp")
    if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b|monday|saturday|sunday", " ".join(_texts(copy)), re.IGNORECASE):
        found.append("có giờ làm việc tự đặt (không có trong Sheet)")
    return sorted(set(found))
