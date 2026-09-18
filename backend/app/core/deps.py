"""依赖注入：owner 会话隔离。

local（桌面/本机）形态所有请求固定 owner_id="local"；
web 形态用 HttpOnly cookie 匿名会话区分用户，无需注册登录。
"""
from fastapi import Request, Response
from uuid import uuid4

from app.core.config import settings


async def get_owner_id(request: Request, response: Response) -> str:
    """从请求解析 owner_id；web 态首次访问自动签发会话 cookie。"""
    if settings.APP_MODE != "web":
        return "local"

    # 优先级：X-Session-Id 头（API 直调）> cookie > 签发新会话
    header_sid = request.headers.get("X-Session-Id", "").strip()
    if header_sid:
        return header_sid[:64]

    cookie_sid = request.cookies.get(settings.SESSION_COOKIE, "").strip()
    if cookie_sid:
        return cookie_sid[:64]

    new_sid = uuid4().hex
    response.set_cookie(
        key=settings.SESSION_COOKIE,
        value=new_sid,
        httponly=True,
        samesite="lax",
        max_age=settings.SESSION_TTL_DAYS * 24 * 3600,
    )
    return new_sid
