"""상품 관리 (PRD-01 등록, PRD-02 수정/삭제, PRD-04 거래 상태 변경) + 거래 (TRD-04 예약자 지정, TRD-05 거래 완료)

단위업무 번호는 업무기능도 기준. ①② 문단 번호는 업무기술서 본문(괄호 안 번호)을 가리킨다.
"""

import mimetypes
import os
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..auth import current_member, is_admin, optional_member
from ..db import execute, fetch_all, fetch_one, get_db

router = APIRouter(prefix="/products", tags=["products"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
CONDITIONS = ("새상품", "거의새것", "사용감있음", "하자있음")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
MAX_PRICE = 4_294_967_295  # price INT UNSIGNED 최댓값

# 배포 환경에서는 S3_BUCKET 을 설정해 이미지를 S3 에 올린다. 없으면 로컬 uploads 폴더에 저장
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", f"https://{S3_BUCKET}.s3.amazonaws.com")
if S3_BUCKET:
    import boto3

    _s3 = boto3.client("s3")


class BuyerIn(BaseModel):
    buyer_no: int


def _check_images(files: list[UploadFile]) -> None:
    # ===== [기존 구현 - 비활성] 파일 확장자만 검사 =====
    # # 업로드 폴더는 그대로 웹에 노출되므로 이미지 확장자만 받는다 (.html 등 차단)
    # for f in files:
    #     if f.filename and Path(f.filename).suffix.lower() not in IMAGE_EXTS:
    #         raise HTTPException(422, f"이미지 파일만 올릴 수 있습니다. ({', '.join(IMAGE_EXTS)})")
    # ===== [수정 구현 - 활성] =====
    # 확장자와 MIME뿐 아니라 실제 디코딩 가능한 이미지인지 검사한다.
    formats = {
        ".jpg": ("JPEG", "image/jpeg"),
        ".jpeg": ("JPEG", "image/jpeg"),
        ".png": ("PNG", "image/png"),
        ".gif": ("GIF", "image/gif"),
        ".webp": ("WEBP", "image/webp"),
    }
    max_bytes = 15 * 1024 * 1024
    max_pixels = 30_000_000
    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        expected = formats.get(ext)
        if expected is None:
            raise HTTPException(422, f"이미지 파일만 올릴 수 있습니다. ({', '.join(IMAGE_EXTS)})")
        expected_format, expected_mime = expected
        if f.content_type != expected_mime:
            raise HTTPException(422, "이미지 파일의 MIME 타입이 확장자와 다릅니다.")

        try:
            f.file.seek(0, os.SEEK_END)
            size = f.file.tell()
            f.file.seek(0)
            if size == 0:
                raise HTTPException(422, "빈 이미지 파일은 업로드할 수 없습니다.")
            if size > max_bytes:
                raise HTTPException(413, "이미지 크기는 15MiB 이하여야 합니다.")
            with Image.open(f.file) as image:
                if image.format != expected_format:
                    raise HTTPException(422, "확장자와 실제 이미지 형식이 다릅니다.")
                if image.width * image.height > max_pixels:
                    raise HTTPException(413, "이미지 해상도가 너무 높습니다.")
                image.verify()
            # 헤더만 맞고 픽셀 데이터가 손상된 파일도 거부한다.
            f.file.seek(0)
            with Image.open(f.file) as image:
                image.load()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
            raise HTTPException(422, "정상적인 이미지 파일이 아닙니다.") from exc
        finally:
            # _save_images가 동일 스트림에서 원본을 읽으므로 위치 복원.
            f.file.seek(0)


def _save_images(conn, product_no: int, files: list[UploadFile]) -> None:
    for order, f in enumerate(f for f in files if f.filename):
        name = f"{uuid.uuid4().hex}{Path(f.filename).suffix.lower()}"
        if S3_BUCKET:
            key = f"products/{name}"
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=f.file.read(), ContentType=content_type)
            path = f"{S3_PUBLIC_URL}/{key}"
        else:
            (UPLOAD_DIR / name).write_bytes(f.file.read())
            path = f"/uploads/{name}"
        execute(
            conn,
            "INSERT INTO product_image (product_no, image_path, image_order) VALUES (%s,%s,%s)",
            (product_no, path, order),
        )


def _validate(title: str, price: int, item_condition: str) -> None:
    if not title.strip():
        raise HTTPException(422, "상품명을 입력하세요.")
    if len(title) > 100:
        raise HTTPException(422, "상품명은 100자 이하여야 합니다.")
    if not 0 <= price <= MAX_PRICE:
        raise HTTPException(422, "판매가격은 0원 이상, 약 42억 원 이하여야 합니다.")
    if item_condition not in CONDITIONS:
        raise HTTPException(422, f"물품상태는 {CONDITIONS} 중 하나여야 합니다.")


def _get_product(conn, product_no: int, lock: bool = False) -> dict:
    p = fetch_one(
        conn, f"SELECT * FROM product WHERE product_no=%s{' FOR UPDATE' if lock else ''}", (product_no,)
    )
    if p is None:
        raise HTTPException(404, "상품이 없습니다.")
    return p


def _own_product(conn, product_no: int, member: dict) -> dict:
    p = _get_product(conn, product_no, lock=True)
    if p["seller_no"] != member["member_no"]:
        raise HTTPException(403, "본인이 등록한 상품만 처리할 수 있습니다.")
    if p["post_status"] != "정상":
        raise HTTPException(409, f"게시글 상태가 '{p['post_status']}'입니다.")
    return p


def close_other_chats(conn, product_no: int, keep_buyer_no: int | None) -> None:
    """최종 구매자(keep_buyer_no) 방만 남기고 그 상품의 채팅방을 비활성으로."""
    execute(
        conn,
        "UPDATE chat_room SET room_status='비활성' WHERE product_no=%s AND NOT (buyer_no <=> %s)",
        (product_no, keep_buyer_no),
    )


@router.get("")
def list_products(q: str | None = None, trade_status: str | None = None, conn=Depends(get_db)):
    # PRD-02 ⑧ / ADM-02 ⑦ 삭제·블라인드 게시글은 목록에서 제외
    # 이용정지·탈퇴 판매자의 글도 제외 (채팅을 열 수 없는 상품이 목록에 남지 않도록)
    sql = """SELECT p.product_no, p.title, p.price, p.trade_status, p.trade_area, p.registered_at,
                    m.nickname AS seller_nickname,
                    (SELECT image_path FROM product_image i
                      WHERE i.product_no=p.product_no ORDER BY image_order LIMIT 1) AS thumbnail
               FROM product p JOIN member m ON m.member_no = p.seller_no
              WHERE p.post_status='정상' AND m.account_status='정상'"""
    params: list = []
    if q:
        sql += " AND (p.title LIKE %s OR p.description LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if trade_status:
        sql += " AND p.trade_status=%s"
        params.append(trade_status)
    return fetch_all(conn, sql + " ORDER BY p.registered_at DESC LIMIT 100", params)


@router.get("/mine")
def my_products(member=Depends(current_member), conn=Depends(get_db)):
    return fetch_all(
        conn,
        """SELECT product_no, title, price, trade_status, post_status, registered_at
             FROM product WHERE seller_no=%s AND post_status<>'삭제' ORDER BY registered_at DESC""",
        (member["member_no"],),
    )


@router.get("/purchased")
def my_purchases(member=Depends(current_member), conn=Depends(get_db)):
    return fetch_all(
        conn,
        """SELECT p.product_no, p.title, p.price, p.completed_at, m.nickname AS seller_nickname
             FROM product p JOIN member m ON m.member_no=p.seller_no
            WHERE p.buyer_no=%s ORDER BY p.completed_at DESC""",
        (member["member_no"],),
    )


@router.get("/{product_no}")
def product_detail(product_no: int, viewer=Depends(optional_member), conn=Depends(get_db)):
    p = fetch_one(
        conn,
        """SELECT p.*, s.nickname AS seller_nickname, r.nickname AS reserver_nickname,
                  b.nickname AS buyer_nickname
             FROM product p
             JOIN member s ON s.member_no=p.seller_no
             LEFT JOIN member r ON r.member_no=p.reserver_no
             LEFT JOIN member b ON b.member_no=p.buyer_no
            WHERE p.product_no=%s""",
        (product_no,),
    )
    if p is None:
        raise HTTPException(404, "상품이 없습니다.")
    is_owner = viewer is not None and viewer["member_no"] == p["seller_no"]
    if p["post_status"] != "정상" and not (is_owner or is_admin(viewer)):
        raise HTTPException(404, "조회할 수 없는 게시글입니다.")
    p["images"] = fetch_all(
        conn,
        "SELECT image_no, image_path, image_order FROM product_image WHERE product_no=%s ORDER BY image_order",
        (product_no,),
    )
    return p


@router.post("", status_code=201)
def create_product(
    title: str = Form(...),
    description: str = Form(...),
    price: int = Form(...),
    item_condition: str = Form(...),
    trade_area: str | None = Form(None),
    price_offer_yn: bool = Form(False),
    images: list[UploadFile] = File(default=[]),
    member=Depends(current_member),
    conn=Depends(get_db),
):
    _validate(title, price, item_condition)
    _check_images(images)
    product_no = execute(
        conn,
        """INSERT INTO product (seller_no, title, description, price, item_condition, trade_area, price_offer_yn)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (member["member_no"], title, description, price, item_condition, trade_area or None, price_offer_yn),
    )
    _save_images(conn, product_no, images)
    return {"product_no": product_no}


@router.put("/{product_no}")
def update_product(
    product_no: int,
    title: str = Form(...),
    description: str = Form(...),
    price: int = Form(...),
    item_condition: str = Form(...),
    trade_area: str | None = Form(None),
    price_offer_yn: bool = Form(False),
    images: list[UploadFile] = File(default=[]),
    member=Depends(current_member),
    conn=Depends(get_db),
):
    p = _own_product(conn, product_no, member)
    if p["trade_status"] == "판매완료":  # PRD-02 ⑤
        raise HTTPException(409, "판매완료 상품은 수정할 수 없습니다.")
    _validate(title, price, item_condition)
    _check_images(images)
    execute(
        conn,
        """UPDATE product SET title=%s, description=%s, price=%s, item_condition=%s,
                  trade_area=%s, price_offer_yn=%s WHERE product_no=%s""",
        (title, description, price, item_condition, trade_area or None, price_offer_yn, product_no),
    )
    if any(f.filename for f in images):  # 새 이미지를 올리면 전체 교체
        execute(conn, "DELETE FROM product_image WHERE product_no=%s", (product_no,))
        _save_images(conn, product_no, images)
    return {"ok": True}


@router.delete("/{product_no}")
def delete_product(product_no: int, member=Depends(current_member), conn=Depends(get_db)):
    p = _own_product(conn, product_no, member)
    if p["trade_status"] == "예약중":  # PRD-02 ⑥ 거래 진행 상태 확인
        raise HTTPException(409, "예약중인 상품은 예약을 해제한 뒤 삭제하세요.")
    execute(
        conn, "UPDATE product SET post_status='삭제', deleted_at=NOW() WHERE product_no=%s", (product_no,)
    )
    close_other_chats(conn, product_no, p["buyer_no"])  # 판매완료 글이면 최종 구매자 방은 유지
    return {"ok": True}


def _require_chat_buyer(conn, product_no: int, buyer_no: int) -> dict:
    row = fetch_one(
        conn,
        """SELECT m.account_status FROM chat_room r JOIN member m ON m.member_no=r.buyer_no
            WHERE r.product_no=%s AND r.buyer_no=%s""",
        (product_no, buyer_no),
    )
    if row is None:
        raise HTTPException(422, "해당 상품 채팅방에 참여한 구매자만 지정할 수 있습니다.")
    return row


@router.post("/{product_no}/reserve")
def reserve(product_no: int, body: BuyerIn, member=Depends(current_member), conn=Depends(get_db)):
    """TRD-04 예약자 지정 (기술서 TRD-03): 판매중 → 예약중"""
    p = _own_product(conn, product_no, member)
    if p["trade_status"] != "판매중":
        raise HTTPException(409, "판매중인 상품만 예약자를 지정할 수 있습니다.")
    buyer = _require_chat_buyer(conn, product_no, body.buyer_no)
    if buyer["account_status"] != "정상":
        raise HTTPException(409, f"구매자 계정이 '{buyer['account_status']}' 상태라 예약자로 지정할 수 없습니다.")
    execute(
        conn,
        """UPDATE product SET trade_status='예약중', reserver_no=%s, trade_status_at=NOW()
            WHERE product_no=%s""",
        (body.buyer_no, product_no),
    )
    return {"ok": True}


@router.post("/{product_no}/unreserve")
def unreserve(product_no: int, member=Depends(current_member), conn=Depends(get_db)):
    """TRD-04 예약 해제 (기술서 TRD-03 ⑥⑦): 예약중 → 판매중"""
    p = _own_product(conn, product_no, member)
    if p["trade_status"] != "예약중":
        raise HTTPException(409, "예약중인 상품이 아닙니다.")
    execute(
        conn,
        """UPDATE product SET trade_status='판매중', reserver_no=NULL, trade_status_at=NOW()
            WHERE product_no=%s""",
        (product_no,),
    )
    return {"ok": True}


@router.post("/{product_no}/complete")
def complete(product_no: int, body: BuyerIn, member=Depends(current_member), conn=Depends(get_db)):
    """TRD-05 거래 완료 (기술서 TRD-04): 판매완료, 최종 구매자 외 채팅방 비활성"""
    p = _own_product(conn, product_no, member)
    if p["trade_status"] == "판매완료":
        raise HTTPException(409, "이미 거래 완료된 상품입니다.")
    # 기술서 TRD-04 ④ 예약중이면 예약자와만 완료. 다른 사람과 거래하려면 예약을 먼저 해제한다.
    if p["trade_status"] == "예약중" and body.buyer_no != p["reserver_no"]:
        raise HTTPException(409, "예약중인 상품은 예약자와만 거래를 완료할 수 있습니다. 다른 구매자와 거래하려면 예약을 먼저 해제하세요.")
    _require_chat_buyer(conn, product_no, body.buyer_no)
    execute(
        conn,
        """UPDATE product SET trade_status='판매완료', buyer_no=%s, reserver_no=NULL,
                  completed_at=NOW(), trade_status_at=NOW() WHERE product_no=%s""",
        (body.buyer_no, product_no),
    )
    close_other_chats(conn, product_no, body.buyer_no)
    return {"ok": True}
