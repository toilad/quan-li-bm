"""Login endpoints + the middleware that protects every other /api route.

Public: /api/health, /api/auth/status, /api/auth/login, /api/auth/setup (only while no account exists, and only
from this machine). Everything else needs the session cookie. Unsafe methods from a foreign Origin are refused.
"""
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from wg_core import auth
from wg_core.config import settings
from wg_core.db import session_scope
from wg_core.runtime_config import get as cfg

router = APIRouter()
PUBLIC = {"/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/setup"}
LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


def allowed_origins() -> set[str]:
    out = {o.strip().rstrip("/") for o in settings().cors_origins.split(",") if o.strip()}
    if web := (cfg("PUBLIC_WEB_URL") or "").rstrip("/"):
        out.add(web)
    return out


def _client(request: Request) -> str:
    return request.client.host if request.client else ""


def _secure(request: Request) -> bool:
    return request.url.scheme == "https" or (cfg("PUBLIC_API_URL") or "").startswith("https://")


def _local(request: Request) -> bool:
    """On the machine that runs the app, not through a proxy (a proxy on the same machine would look local)."""
    return _client(request) in LOOPBACK and "x-forwarded-for" not in request.headers and "forwarded" not in request.headers


def _set_cookie(request: Request, response: Response, token: str):
    max_age = auth.LOCAL_MAX_AGE if _local(request) else auth.MAX_AGE
    response.set_cookie(auth.COOKIE, token, max_age=int(max_age.total_seconds()), httponly=True,
                        samesite="lax", secure=_secure(request), path="/")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or not path.startswith("/api/"):
            return await call_next(request)
        origin = (request.headers.get("origin") or "").rstrip("/")
        if request.method not in ("GET", "HEAD") and origin and origin not in allowed_origins():
            return JSONResponse(status_code=403, content={"status": "forbidden", "message": "Nguồn yêu cầu không được phép"})
        if path in PUBLIC:
            return await call_next(request)
        with session_scope() as s:
            user = auth.session_user(s, request.cookies.get(auth.COOKIE))
            name = user.username if user else None
        if not name:
            return JSONResponse(status_code=401, content={"status": "unauthenticated", "message": "Cần đăng nhập"})
        request.state.user = name
        return await call_next(request)


class Credentials(BaseModel):
    username: str
    password: str


@router.get("/api/auth/status")
def status(request: Request):
    with session_scope() as s:
        user = auth.session_user(s, request.cookies.get(auth.COOKIE))
        exist = auth.users_exist(s)
        name = user.username if user else None
    return {"authenticated": bool(name), "user": name, "setup_needed": not exist,
            "setup_allowed": not exist and _client(request) in LOOPBACK and "x-forwarded-for" not in request.headers}


@router.post("/api/auth/login")
def login(body: Credentials, request: Request, response: Response):
    ip = _client(request)
    if wait := auth.throttle.blocked(ip):
        raise HTTPException(429, f"Sai mật khẩu quá nhiều lần — thử lại sau {wait // 60 + 1} phút")
    with session_scope() as s:
        token = auth.login(s, body.username, body.password, ip, local=_local(request))
    if not token:
        auth.throttle.fail(ip)
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    auth.throttle.reset(ip)
    _set_cookie(request, response, token)
    return {"ok": True, "user": body.username.strip().lower()}


@router.post("/api/auth/setup")
def setup(body: Credentials, request: Request, response: Response):
    """First account only, only from this machine (not through a proxy). On a server use scripts/create_user.py."""
    if _client(request) not in LOOPBACK or "x-forwarded-for" in request.headers:
        raise HTTPException(403, "Chỉ tạo tài khoản đầu tiên ngay trên máy chạy app — trên server dùng scripts/create_user.py")
    with session_scope() as s:
        if auth.users_exist(s):
            raise HTTPException(409, "Đã có tài khoản — đăng nhập")
        try:
            auth.create_user(s, body.username, body.password)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        token = auth.login(s, body.username, body.password, _client(request), local=_local(request))
    _set_cookie(request, response, token)
    return {"ok": True, "user": body.username.strip().lower()}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response):
    with session_scope() as s:
        auth.logout(s, request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


class NewPassword(BaseModel):
    current: str
    new: str


@router.post("/api/auth/password")
def change_password(body: NewPassword, request: Request, response: Response):
    with session_scope() as s:
        user = auth.session_user(s, request.cookies.get(auth.COOKIE))
        if not user or not auth.verify_password(body.current, user.pw_hash):
            raise HTTPException(401, "Mật khẩu hiện tại không đúng")
        try:
            auth.set_password(s, user, body.new)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        token = auth.login(s, user.username, body.new, _client(request), local=_local(request))
    _set_cookie(request, response, token)
    return {"ok": True}
