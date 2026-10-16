"""What is configured / available — the UI shows this instead of pretending an action worked."""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import env_secret, settings
from .runtime_config import get as cfg
from .models import Nick


def integration_status(s: Session) -> dict:
    st = settings()
    from .integrations.google import auth_mode

    mode = auth_mode()
    auth_missing = [] if mode else ["Kết nối Google (Cài đặt API → OAuth client + Kết nối)"]
    drive_ok = mode == "oauth" or (mode == "service_account" and bool(cfg("DRIVE_FOLDER_ID")))
    google = {
        "mode": mode,
        "sheets": {"configured": bool(mode) and bool(cfg("SHEET_ID")), "missing": auth_missing + ([] if cfg("SHEET_ID") else ["SHEET_ID"])},
        "drive": {"configured": drive_ok, "missing": auth_missing + ([] if drive_ok or not mode else ["DRIVE_FOLDER_ID (Shared Drive) hoặc OAuth"])},
    }
    key = cfg("ANTHROPIC_API_KEY")
    ai = {"configured": bool(key), "model": cfg("AI_MODEL", st.ai_model), "missing": [] if key else ["ANTHROPIC_API_KEY"]}
    nicks = []
    for n in s.scalars(select(Nick).order_by(Nick.id)):
        k = n.id.upper()
        cp_missing = [v for v in (f"CPANEL_USER_{k}", f"CPANEL_TOKEN_{k}") if not env_secret(v)]
        nicks.append({
            "id": n.id, "name": n.name,
            "inet_key": bool(env_secret(f"INET_API_KEY_{k}")),
            "cpanel": {"configured": not cp_missing, "missing": cp_missing},
        })
    return {
        "google": google,
        "ai": ai,
        "nicks": nicks,
        "unavailable": [
            {"what": "Tạo bản ghi A qua API iNET", "why": "Tài liệu iNET chưa có cấu trúc dữ liệu gửi lên cho PATCH /domain/{id}/record"},
            {"what": "Đọc danh sách tên miền qua API iNET", "why": "GET /domain có trong tài liệu nhưng chưa có cấu trúc trả về — cần 1 lần gọi thật (chỉ đọc) để đối chiếu"},
        ],
    }
