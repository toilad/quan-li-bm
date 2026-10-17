"""Create (or reset the password of) a login account. The password is typed here, never passed on the command line.

    python -m scripts.create_user <username>            # new account
    python -m scripts.create_user <username> --reset    # new password for an existing account (ends its sessions)

In Docker:  docker compose exec api python -m scripts.create_user <username>
"""
import getpass
import sys

from sqlalchemy import select

from wg_core import auth, registry
from wg_core.db import session_scope


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    username, reset = argv[0].strip().lower(), "--reset" in argv[1:]
    registry.setup()
    pw = getpass.getpass(f"Mật khẩu cho {username} (tối thiểu {auth.MIN_PASSWORD} ký tự): ")
    if pw != getpass.getpass("Nhập lại: "):
        print("Hai lần nhập không khớp — không thay đổi gì.")
        return 1
    try:
        with session_scope() as s:
            user = s.scalar(select(auth.User).where(auth.User.username == username))
            if reset:
                if not user:
                    print(f"Không có tài khoản {username}.")
                    return 1
                auth.set_password(s, user, pw)
                print(f"Đã đổi mật khẩu cho {username}; mọi phiên đăng nhập cũ đã kết thúc.")
            else:
                auth.create_user(s, username, pw)
                print(f"Đã tạo tài khoản {username}.")
    except ValueError as e:
        print(f"Không thực hiện: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
