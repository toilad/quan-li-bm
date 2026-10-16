"""Backup / restore.

  python -m scripts.backup create            → backups/qlbm-YYYYmmdd-HHMMSS.dump (pg_dump custom format) + data.zip
  python -m scripts.backup restore FILE.dump → pg_restore into an EMPTY database given by RESTORE_DATABASE_URL
                                               (never into the live database; check, then switch over)

Off-site copies (restic → B2/R2, 7 daily / 4 weekly / 12 monthly) run from docker-compose's backup service.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Vietnamese messages on Windows consoles
sys.path.insert(0, str(ROOT))

from wg_core.config import settings  # noqa: E402
from wg_core.db import database_url  # noqa: E402


def _bin(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    local = ROOT / ".venv" / "Lib" / "site-packages" / "pgserver" / "pginstall" / "bin" / f"{name}.exe"
    if local.exists():
        return str(local)
    raise SystemExit(f"Không tìm thấy {name}")


def _plain(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def create() -> Path:
    out = ROOT / "backups"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dump = out / f"qlbm-{stamp}.dump"
    subprocess.run([_bin("pg_dump"), "--format=custom", "--no-owner", f"--file={dump}", _plain(database_url())], check=True)
    data = settings().data_dir
    if data.exists():
        with zipfile.ZipFile(out / f"qlbm-{stamp}-data.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for p in data.rglob("*"):
                # the master key never travels with the encrypted settings it protects
                if p.is_file() and p.name not in ("master.key", "google_token.json"):
                    z.write(p, p.relative_to(data))
    print(f"Đã sao lưu: {dump}")
    return dump


def restore(dump: str):
    target = os.environ.get("RESTORE_DATABASE_URL")
    if not target:
        raise SystemExit("Đặt RESTORE_DATABASE_URL = database TRỐNG để khôi phục (không khôi phục đè lên database đang chạy)")
    subprocess.run([_bin("pg_restore"), "--no-owner", "--exit-on-error", f"--dbname={_plain(target)}", dump], check=True)
    print("Khôi phục xong — kiểm tra dữ liệu rồi mới chuyển ứng dụng sang database này.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "create":
        create()
    elif len(sys.argv) >= 3 and sys.argv[1] == "restore":
        restore(sys.argv[2])
    else:
        print(__doc__)
