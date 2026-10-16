"""What is configured / available — the UI shows this instead of pretending an action worked."""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import env_secret, settings
from .models import Nick


def integration_status(s: Session) -> dict:
    st = settings()
    sa_ok = bool(st.google_service_account_file) and Path(st.google_service_account_file).exists()
    google = {
        "sheets": {"configured": sa_ok and bool(st.sheet_id), "missing": [m for m, ok in (("GOOGLE_SERVICE_ACCOUNT_FILE", sa_ok), ("SHEET_ID", bool(st.sheet_id))) if not ok]},
        "drive": {"configured": sa_ok and bool(st.drive_folder_id), "missing": [m for m, ok in (("GOOGLE_SERVICE_ACCOUNT_FILE", sa_ok), ("DRIVE_FOLDER_ID", bool(st.drive_folder_id))) if not ok]},
    }
    ai = {"configured": bool(st.anthropic_api_key), "model": st.ai_model, "missing": [] if st.anthropic_api_key else ["ANTHROPIC_API_KEY"]}
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
