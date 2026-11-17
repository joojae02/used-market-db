import hashlib
import hmac
import os
import secrets

from fastapi import Depends, Header, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .db import fetch_one, get_db

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
SESSION_MAX_AGE = 60 * 60  # MEM-02 ⑤ 일정 시간 미사용 시 세션 만료 (데모: 1시간)
ADMIN_ROLES = ("moderator", "staff", "root")

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="session")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return hmac.compare_digest(check.hex(), digest)


def issue_token(member_no: int) -> str:
    return _serializer.dumps({"m": member_no})


def _member_from_token(conn, authorization: str | None) -> dict | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        data = _serializer.loads(authorization[7:], max_age=SESSION_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(401, "세션이 만료되었습니다. 다시 로그인하세요.")
    except BadSignature:
        return None
    return fetch_one(
        conn,
        "SELECT member_no, role, nickname, account_status FROM member WHERE member_no = %s",
        (data["m"],),
    )


def current_member(authorization: str | None = Header(None), conn=Depends(get_db)) -> dict:
    """MEM-02 ⑧ 인증 세션을 가진 '정상' 회원만 통과."""
    member = _member_from_token(conn, authorization)
    if member is None:
        raise HTTPException(401, "로그인이 필요합니다.")
    if member["account_status"] != "정상":
        raise HTTPException(403, f"계정 상태가 '{member['account_status']}'입니다.")
    return member


def optional_member(authorization: str | None = Header(None), conn=Depends(get_db)) -> dict | None:
    try:
        return _member_from_token(conn, authorization)
    except HTTPException:
        return None


def is_admin(member: dict | None) -> bool:
    return bool(member) and member["role"] in ADMIN_ROLES


def admin_member(member: dict = Depends(current_member)) -> dict:
    if not is_admin(member):
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return member
