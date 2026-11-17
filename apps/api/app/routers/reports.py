"""신고 (TRS-01)"""

from typing import Literal

import pymysql
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import current_member
from ..db import execute, fetch_all, fetch_one, get_db

router = APIRouter(prefix="/reports", tags=["reports"])

REASONS = ("스팸/광고", "사기의심", "욕설/비방", "부적절한게시물", "기타")


class ReportIn(BaseModel):
    target_type: Literal["상품게시글", "회원"]
    target_no: int
    reason_code: Literal[REASONS]  # type: ignore[valid-type]
    content: str = Field(min_length=1, max_length=2000)


@router.get("/reasons")
def reasons():
    return list(REASONS)


@router.post("", status_code=201)
def create_report(body: ReportIn, member=Depends(current_member), conn=Depends(get_db)):
    # TRS-01 ⑧ 실제 존재하는 대상만
    if body.target_type == "회원":
        exists = fetch_one(conn, "SELECT 1 FROM member WHERE member_no=%s", (body.target_no,))
        if body.target_no == member["member_no"]:
            raise HTTPException(400, "자기 자신은 신고할 수 없습니다.")
    else:
        exists = fetch_one(conn, "SELECT 1 FROM product WHERE product_no=%s", (body.target_no,))
    if not exists:
        raise HTTPException(404, "신고 대상이 없습니다.")

    member_no = body.target_no if body.target_type == "회원" else None
    product_no = body.target_no if body.target_type == "상품게시글" else None
    try:
        report_no = execute(
            conn,
            """INSERT INTO report (reporter_no, target_type, target_member_no, target_product_no,
                                   reason_code, content) VALUES (%s,%s,%s,%s,%s,%s)""",
            (member["member_no"], body.target_type, member_no, product_no, body.reason_code, body.content),
        )
    except pymysql.err.IntegrityError:
        raise HTTPException(409, "이미 신고한 대상입니다.")  # TRS-01 ⑦ (uk_report_once)
    return {"report_no": report_no}


@router.get("/mine")
def my_reports(member=Depends(current_member), conn=Depends(get_db)):
    """TRS-01 ⑪ 내가 한 신고의 처리 상태"""
    return fetch_all(
        conn,
        """SELECT report_no, target_type, COALESCE(target_member_no, target_product_no) AS target_no,
                  reason_code, report_status, reported_at
             FROM report WHERE reporter_no=%s ORDER BY reported_at DESC""",
        (member["member_no"],),
    )
