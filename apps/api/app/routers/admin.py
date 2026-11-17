"""운영 관리 (ADM-01 회원 관리/제재, ADM-02 게시글 관리, ADM-03 신고 관리) + 권한 관리(root)"""

from datetime import datetime
from typing import Literal

import pymysql
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import admin_member
from ..db import execute, fetch_all, fetch_one, get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class SanctionIn(BaseModel):
    sanction_type: Literal["경고", "일시정지", "영구정지"]
    reason: str = Field(min_length=1, max_length=500)
    end_at: datetime | None = None
    report_no: int | None = None


class ReleaseIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RoleIn(BaseModel):
    role: Literal["user", "moderator", "staff"]


class ActionIn(BaseModel):
    action_type: Literal["블라인드", "삭제", "블라인드해제"]
    reason: str = Field(min_length=1, max_length=500)
    report_no: int | None = None


class ProcessIn(BaseModel):
    result: Literal["조치완료", "조치없음", "반려"]
    reason: str = Field(min_length=1, max_length=500)


def _db_error(e: pymysql.err.MySQLError) -> HTTPException:
    """트리거(SIGNAL 45000) 메시지를 그대로 돌려준다."""
    return HTTPException(409, e.args[1] if len(e.args) > 1 else str(e))


# ---------------------------------------------------------------- ADM-01 회원


@router.get("/members")
def search_members(q: str | None = None, status: str | None = None, conn=Depends(get_db), _=Depends(admin_member)):
    sql = """SELECT member_no, role, name, nickname, email, phone, joined_at, account_status
               FROM member WHERE 1=1"""
    params: list = []
    if q:
        sql += " AND (nickname LIKE %s OR email LIKE %s OR name LIKE %s OR member_no = %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%", q if q.isdigit() else -1]
    if status:
        sql += " AND account_status=%s"
        params.append(status)
    return fetch_all(conn, sql + " ORDER BY member_no DESC LIMIT 200", params)


@router.get("/members/{member_no}")
def member_detail(member_no: int, conn=Depends(get_db), _=Depends(admin_member)):
    m = fetch_one(
        conn,
        """SELECT member_no, role, name, nickname, phone, birth_date, address, email, joined_at,
                  account_status, withdrawn_at, login_fail_count, login_locked_until
             FROM member WHERE member_no=%s""",
        (member_no,),
    )
    if m is None:
        raise HTTPException(404, "회원이 없습니다.")
    # ADM-01 ③ 상품 등록 내역, 거래 내역, 신고 접수 내역, 제재 이력
    m["products"] = fetch_all(
        conn,
        "SELECT product_no, title, trade_status, post_status, registered_at FROM product "
        "WHERE seller_no=%s ORDER BY registered_at DESC",
        (member_no,),
    )
    m["purchases"] = fetch_all(
        conn,
        "SELECT product_no, title, price, completed_at FROM product WHERE buyer_no=%s ORDER BY completed_at DESC",
        (member_no,),
    )
    m["reports_received"] = fetch_all(
        conn,
        "SELECT report_no, reason_code, report_status, reported_at FROM report "
        "WHERE target_member_no=%s ORDER BY reported_at DESC",
        (member_no,),
    )
    m["sanctions"] = fetch_all(
        conn,
        """SELECT s.*, a.nickname AS admin_nickname, ra.nickname AS release_admin_nickname
             FROM member_sanction s
             JOIN member a ON a.member_no=s.admin_no
             LEFT JOIN member ra ON ra.member_no=s.release_admin_no
            WHERE s.member_no=%s ORDER BY s.sanctioned_at DESC""",
        (member_no,),
    )
    return m


@router.post("/members/{member_no}/sanctions", status_code=201)
def sanction(member_no: int, body: SanctionIn, conn=Depends(get_db), admin=Depends(admin_member)):
    if body.sanction_type == "일시정지" and body.end_at is None:
        raise HTTPException(422, "일시정지는 종료예정일시가 필요합니다.")
    target = fetch_one(conn, "SELECT account_status FROM member WHERE member_no=%s", (member_no,))
    if target is None:
        raise HTTPException(404, "회원이 없습니다.")
    if target["account_status"] == "탈퇴":
        raise HTTPException(409, "탈퇴한 회원입니다.")
    try:
        sanction_no = execute(
            conn,
            """INSERT INTO member_sanction (member_no, admin_no, report_no, sanction_type, reason, end_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (member_no, admin["member_no"], body.report_no, body.sanction_type, body.reason,
             body.end_at if body.sanction_type == "일시정지" else None),
        )
    except pymysql.err.OperationalError as e:
        raise _db_error(e)
    if body.sanction_type != "경고":  # ADM-01 ⑧⑨
        execute(conn, "UPDATE member SET account_status='이용정지' WHERE member_no=%s", (member_no,))
    return {"sanction_no": sanction_no}


@router.post("/sanctions/{sanction_no}/release")
def release(sanction_no: int, body: ReleaseIn, conn=Depends(get_db), admin=Depends(admin_member)):
    s = fetch_one(conn, "SELECT * FROM member_sanction WHERE sanction_no=%s", (sanction_no,))
    if s is None:
        raise HTTPException(404, "제재가 없습니다.")
    if s["released_at"]:
        raise HTTPException(409, "이미 해제된 제재입니다.")
    execute(
        conn,
        """UPDATE member_sanction SET released_at=NOW(), release_admin_no=%s, release_reason=%s
            WHERE sanction_no=%s""",
        (admin["member_no"], body.reason, sanction_no),
    )
    # ADM-01 ⑪ 다른 유효 정지가 없으면 '정상'
    other = fetch_one(
        conn,
        """SELECT 1 FROM member_sanction
            WHERE member_no=%s AND released_at IS NULL AND sanction_type IN ('일시정지','영구정지')
              AND (end_at IS NULL OR end_at > NOW()) LIMIT 1""",
        (s["member_no"],),
    )
    if not other:
        execute(
            conn,
            "UPDATE member SET account_status='정상' WHERE member_no=%s AND account_status='이용정지'",
            (s["member_no"],),
        )
    return {"ok": True}


@router.patch("/members/{member_no}/role")
def change_role(member_no: int, body: RoleIn, conn=Depends(get_db), admin=Depends(admin_member)):
    """회의록 11/10: 다른 회원의 역할 관리는 루트만"""
    if admin["role"] != "root":
        raise HTTPException(403, "권한 변경은 루트 계정만 할 수 있습니다.")
    try:
        execute(conn, "UPDATE member SET role=%s WHERE member_no=%s", (body.role, member_no))
    except pymysql.err.OperationalError as e:
        raise _db_error(e)  # trg_member_root_no_role_change
    return {"ok": True}


# ---------------------------------------------------------------- ADM-02 게시글


@router.get("/products")
def search_products(q: str | None = None, post_status: str | None = None, conn=Depends(get_db), _=Depends(admin_member)):
    sql = """SELECT p.product_no, p.title, p.price, p.trade_status, p.post_status, p.registered_at,
                    p.seller_no, m.nickname AS seller_nickname,
                    (SELECT COUNT(*) FROM report r WHERE r.target_product_no=p.product_no) AS report_count
               FROM product p JOIN member m ON m.member_no=p.seller_no WHERE 1=1"""
    params: list = []
    if q:
        sql += " AND (p.title LIKE %s OR p.product_no = %s OR p.seller_no = %s)"
        n = q if q.isdigit() else -1
        params += [f"%{q}%", n, n]
    if post_status:
        sql += " AND p.post_status=%s"
        params.append(post_status)
    return fetch_all(conn, sql + " ORDER BY p.registered_at DESC LIMIT 200", params)


@router.get("/products/{product_no}/actions")
def product_actions(product_no: int, conn=Depends(get_db), _=Depends(admin_member)):
    return fetch_all(
        conn,
        """SELECT a.*, m.nickname AS admin_nickname FROM product_action a
             JOIN member m ON m.member_no=a.admin_no WHERE a.product_no=%s ORDER BY a.action_at DESC""",
        (product_no,),
    )


@router.post("/products/{product_no}/actions", status_code=201)
def product_action(product_no: int, body: ActionIn, conn=Depends(get_db), admin=Depends(admin_member)):
    p = fetch_one(conn, "SELECT post_status FROM product WHERE product_no=%s FOR UPDATE", (product_no,))
    if p is None:
        raise HTTPException(404, "상품이 없습니다.")
    allowed = {"블라인드": ("정상",), "삭제": ("정상", "블라인드"), "블라인드해제": ("블라인드",)}
    if p["post_status"] not in allowed[body.action_type]:
        raise HTTPException(409, f"'{p['post_status']}' 상태에서는 {body.action_type} 할 수 없습니다.")
    try:
        action_no = execute(
            conn,
            """INSERT INTO product_action (product_no, admin_no, report_no, action_type, reason)
               VALUES (%s,%s,%s,%s,%s)""",
            (product_no, admin["member_no"], body.report_no, body.action_type, body.reason),
        )
    except pymysql.err.OperationalError as e:
        raise _db_error(e)
    if body.action_type == "삭제":
        execute(conn, "UPDATE product SET post_status='삭제', deleted_at=NOW() WHERE product_no=%s", (product_no,))
    else:
        new_status = "블라인드" if body.action_type == "블라인드" else "정상"
        execute(conn, "UPDATE product SET post_status=%s WHERE product_no=%s", (new_status, product_no))
    return {"action_no": action_no}


# ---------------------------------------------------------------- ADM-03 신고


@router.get("/reports")
def search_reports(status: str | None = None, conn=Depends(get_db), _=Depends(admin_member)):
    sql = """SELECT r.report_no, r.target_type, r.target_member_no, r.target_product_no, r.reason_code,
                    r.report_status, r.reported_at, m.nickname AS reporter_nickname
               FROM report r JOIN member m ON m.member_no=r.reporter_no"""
    params: list = []
    if status:
        sql += " WHERE r.report_status=%s"
        params.append(status)
    return fetch_all(conn, sql + " ORDER BY r.reported_at DESC LIMIT 200", params)


@router.get("/reports/{report_no}")
def report_detail(report_no: int, conn=Depends(get_db), _=Depends(admin_member)):
    r = fetch_one(
        conn,
        """SELECT r.*, m.nickname AS reporter_nickname, tm.nickname AS target_member_nickname,
                  tp.title AS target_product_title, tp.post_status AS target_post_status,
                  tp.seller_no AS target_product_seller
             FROM report r
             JOIN member m ON m.member_no=r.reporter_no
             LEFT JOIN member tm ON tm.member_no=r.target_member_no
             LEFT JOIN product tp ON tp.product_no=r.target_product_no
            WHERE r.report_no=%s""",
        (report_no,),
    )
    if r is None:
        raise HTTPException(404, "신고가 없습니다.")
    r["processes"] = fetch_all(
        conn,
        """SELECT p.*, m.nickname AS admin_nickname FROM report_process p
             JOIN member m ON m.member_no=p.admin_no WHERE p.report_no=%s ORDER BY p.processed_at""",
        (report_no,),
    )
    # ADM-03 ⑫ 같은 대상에 대한 다른 신고
    r["related"] = fetch_all(
        conn,
        """SELECT report_no, reason_code, report_status, reported_at FROM report
            WHERE report_no<>%s AND target_type=%s AND target_key=%s ORDER BY reported_at DESC""",
        (report_no, r["target_type"], r["target_key"]),
    )
    return r


@router.post("/reports/{report_no}/review")
def start_review(report_no: int, conn=Depends(get_db), _=Depends(admin_member)):
    """ADM-03 ④ 접수 → 검토중"""
    n = execute(
        conn, "UPDATE report SET report_status='검토중' WHERE report_no=%s AND report_status='접수'", (report_no,)
    )
    if not n:
        raise HTTPException(409, "'접수' 상태의 신고만 검토를 시작할 수 있습니다.")
    return {"ok": True}


@router.post("/reports/{report_no}/process", status_code=201)
def process_report(report_no: int, body: ProcessIn, conn=Depends(get_db), admin=Depends(admin_member)):
    r = fetch_one(conn, "SELECT report_status FROM report WHERE report_no=%s FOR UPDATE", (report_no,))
    if r is None:
        raise HTTPException(404, "신고가 없습니다.")
    if r["report_status"] in ("처리완료", "반려"):
        raise HTTPException(409, "이미 처리된 신고입니다.")
    try:
        process_no = execute(
            conn,
            "INSERT INTO report_process (report_no, admin_no, result, reason) VALUES (%s,%s,%s,%s)",
            (report_no, admin["member_no"], body.result, body.reason),
        )
    except pymysql.err.OperationalError as e:
        raise _db_error(e)
    status = "반려" if body.result == "반려" else "처리완료"
    execute(conn, "UPDATE report SET report_status=%s WHERE report_no=%s", (status, report_no))
    return {"process_no": process_no}
