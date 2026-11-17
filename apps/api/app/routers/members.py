"""회원 관리 (MEM-01 회원가입/탈퇴, MEM-02 로그인/로그아웃)"""

from datetime import date, datetime, timedelta

import pymysql
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from ..auth import current_member, hash_password, issue_token, verify_password
from ..db import execute, fetch_all, fetch_one, get_db

router = APIRouter(tags=["members"])

MAX_LOGIN_FAIL = 5  # MEM-02 ⑦
LOCK_MINUTES = 10


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    nickname: str = Field(min_length=2, max_length=30)
    phone: str = Field(pattern=r"^01[0-9]-?\d{3,4}-?\d{4}$")
    birth_date: date | None = None
    address: str | None = Field(None, max_length=200)
    email: EmailStr
    password: str = Field(min_length=4, max_length=100)


class LoginIn(BaseModel):
    nickname: str
    password: str


def _duplicate_message(e: pymysql.err.IntegrityError) -> str:
    msg = str(e)
    for key, label in (("nickname", "닉네임"), ("phone", "전화번호"), ("email", "이메일")):
        if f"uk_member_{key}" in msg:
            return f"이미 사용 중인 {label}입니다."
    return "중복된 정보가 있습니다."


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, conn=Depends(get_db)):
    digits = body.phone.replace("-", "")
    phone = f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"  # sample_data 와 같은 010-0000-0000 형식
    params = (
        body.name, body.nickname, phone, body.birth_date,
        body.address, body.email, hash_password(body.password),
    )
    # 회의록 11/10: 탈퇴 회원은 같은 row 를 '정상'으로 되돌려 재사용 (이메일로 식별)
    withdrawn = fetch_one(
        conn, "SELECT member_no FROM member WHERE email = %s AND account_status = '탈퇴'", (body.email,)
    )
    try:
        if withdrawn:
            execute(
                conn,
                """UPDATE member SET name=%s, nickname=%s, phone=%s, birth_date=%s, address=%s,
                          email=%s, password_hash=%s, account_status='정상', withdrawn_at=NULL,
                          joined_at=NOW(), login_fail_count=0, login_locked_until=NULL
                    WHERE member_no=%s""",
                (*params, withdrawn["member_no"]),
            )
            member_no = withdrawn["member_no"]
        else:
            member_no = execute(
                conn,
                """INSERT INTO member (name, nickname, phone, birth_date, address, email, password_hash)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                params,
            )
    except pymysql.err.IntegrityError as e:
        raise HTTPException(409, _duplicate_message(e))
    return {"member_no": member_no, "rejoined": bool(withdrawn)}


def _release_expired_suspension(conn, member_no: int) -> None:
    """일시정지 기간이 끝났고 다른 유효 정지가 없으면 '정상'으로 복구 (ADM-01 ⑪)."""
    active = fetch_one(
        conn,
        """SELECT 1 FROM member_sanction
            WHERE member_no=%s AND released_at IS NULL AND sanction_type IN ('일시정지','영구정지')
              AND (end_at IS NULL OR end_at > NOW()) LIMIT 1""",
        (member_no,),
    )
    if not active:
        execute(conn, "UPDATE member SET account_status='정상' WHERE member_no=%s", (member_no,))


@router.post("/auth/login")
def login(body: LoginIn, request: Request, conn=Depends(get_db)):
    m = fetch_one(conn, "SELECT * FROM member WHERE nickname=%s FOR UPDATE", (body.nickname,))
    if m is None:
        raise HTTPException(401, "닉네임 또는 패스워드가 일치하지 않습니다.")

    ip = request.client.host if request.client else "unknown"
    device = (request.headers.get("user-agent") or "")[:255]

    def record(result: int):
        execute(
            conn,
            "INSERT INTO login_history (member_no, ip_address, device_info, login_result) VALUES (%s,%s,%s,%s)",
            (m["member_no"], ip, device, result),
        )

    def fail(status: int, message: str):
        # 실패 이력·실패 횟수는 남겨야 하므로 예외(rollback) 전에 먼저 commit
        record(0)
        conn.commit()
        raise HTTPException(status, message)

    now = datetime.now()
    if m["login_locked_until"] and m["login_locked_until"] > now:
        fail(423, f"로그인 {MAX_LOGIN_FAIL}회 실패로 {m['login_locked_until']:%H:%M}까지 제한됩니다.")

    if not verify_password(body.password, m["password_hash"]):
        fails = m["login_fail_count"] + 1
        locked = now + timedelta(minutes=LOCK_MINUTES) if fails >= MAX_LOGIN_FAIL else None
        execute(
            conn,
            "UPDATE member SET login_fail_count=%s, login_locked_until=%s WHERE member_no=%s",
            (0 if locked else fails, locked, m["member_no"]),
        )
        fail(401, "닉네임 또는 패스워드가 일치하지 않습니다.")

    if m["account_status"] == "이용정지":
        _release_expired_suspension(conn, m["member_no"])
        m = fetch_one(conn, "SELECT * FROM member WHERE member_no=%s", (m["member_no"],))
    if m["account_status"] != "정상":
        fail(403, f"계정 상태가 '{m['account_status']}'이라 로그인할 수 없습니다.")

    execute(
        conn,
        "UPDATE member SET login_fail_count=0, login_locked_until=NULL WHERE member_no=%s",
        (m["member_no"],),
    )
    record(1)
    return {
        "token": issue_token(m["member_no"]),
        "member": {"member_no": m["member_no"], "nickname": m["nickname"], "role": m["role"]},
    }


@router.get("/me")
def me(member=Depends(current_member), conn=Depends(get_db)):
    return fetch_one(
        conn,
        """SELECT member_no, role, name, nickname, phone, birth_date, address, email,
                  joined_at, account_status
             FROM member WHERE member_no=%s""",
        (member["member_no"],),
    )


@router.get("/me/logins")
def my_logins(member=Depends(current_member), conn=Depends(get_db)):
    return fetch_all(
        conn,
        "SELECT login_at, ip_address, device_info, login_result FROM login_history "
        "WHERE member_no=%s ORDER BY login_at DESC LIMIT 20",
        (member["member_no"],),
    )


@router.post("/me/withdraw")
def withdraw(member=Depends(current_member), conn=Depends(get_db)):
    if member["role"] == "root":
        raise HTTPException(400, "루트 계정은 탈퇴할 수 없습니다.")
    # MEM-01 ⑦ 판매중·예약중 상품이 있으면 탈퇴 불가
    selling = fetch_one(
        conn,
        """SELECT COUNT(*) AS cnt FROM product
            WHERE seller_no=%s AND post_status<>'삭제' AND trade_status IN ('판매중','예약중')""",
        (member["member_no"],),
    )
    if selling["cnt"]:
        raise HTTPException(409, f"판매중/예약중 상품 {selling['cnt']}개를 먼저 거래 완료하거나 삭제하세요.")
    execute(
        conn,
        "UPDATE member SET account_status='탈퇴', withdrawn_at=NOW() WHERE member_no=%s",
        (member["member_no"],),
    )
    return {"ok": True}


@router.get("/members/{member_no}")
def member_profile(member_no: int, conn=Depends(get_db)):
    m = fetch_one(
        conn,
        "SELECT member_no, nickname, joined_at, account_status FROM member WHERE member_no=%s",
        (member_no,),
    )
    if m is None:
        raise HTTPException(404, "회원이 없습니다.")
    m["products"] = fetch_all(
        conn,
        """SELECT product_no, title, price, trade_status, registered_at FROM product
            WHERE seller_no=%s AND post_status='정상' ORDER BY registered_at DESC""",
        (member_no,),
    )
    return m
