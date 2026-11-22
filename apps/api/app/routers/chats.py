"""채팅 (TRD-01 채팅방 생성, TRD-02 메시지 송수신)"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import current_member
from ..db import execute, fetch_all, fetch_one, get_db

router = APIRouter(tags=["chats"])

FOLLOW_UP_DAYS = 30  # TRD-05 (기술서 TRD-04 ⑩) 거래 완료 후 1개월간 최종 구매자 방 유지


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def _room_for(conn, room_no: int, member: dict) -> dict:
    room = fetch_one(
        conn,
        """SELECT r.*, p.title, p.trade_status, p.completed_at, p.seller_no AS product_seller,
                  s.nickname AS seller_nickname, b.nickname AS buyer_nickname
             FROM chat_room r
             JOIN product p ON p.product_no=r.product_no
             JOIN member s ON s.member_no=r.seller_no
             JOIN member b ON b.member_no=r.buyer_no
            WHERE r.room_no=%s""",
        (room_no,),
    )
    if room is None or member["member_no"] not in (room["seller_no"], room["buyer_no"]):
        raise HTTPException(404, "채팅방이 없습니다.")  # TRD-02 ② 참여자만
    return room


def _can_send(conn, room: dict) -> bool:
    if room["room_status"] != "활성":
        return False
    if room["trade_status"] == "판매완료":
        row = fetch_one(
            conn, "SELECT %s > NOW() - INTERVAL %s DAY AS ok", (room["completed_at"], FOLLOW_UP_DAYS)
        )
        return bool(row["ok"])
    return True


@router.post("/products/{product_no}/chat")
def open_chat(product_no: int, member=Depends(current_member), conn=Depends(get_db)):
    p = fetch_one(conn, "SELECT * FROM product WHERE product_no=%s", (product_no,))
    if p is None:
        raise HTTPException(404, "상품이 없습니다.")
    if p["seller_no"] == member["member_no"]:  # TRD-01 ⑤
        raise HTTPException(400, "본인 상품에는 채팅을 걸 수 없습니다.")
    # TRD-01 ④ 이미 방이 있으면 기존 방으로 연결
    room = fetch_one(
        conn,
        "SELECT room_no FROM chat_room WHERE product_no=%s AND buyer_no=%s",
        (product_no, member["member_no"]),
    )
    if room:
        return {"room_no": room["room_no"], "created": False}
    # TRD-01 ⑦
    if p["trade_status"] == "판매완료" or p["post_status"] != "정상":
        raise HTTPException(409, "거래가 끝났거나 게시가 중단된 상품입니다.")
    seller = fetch_one(conn, "SELECT account_status FROM member WHERE member_no=%s", (p["seller_no"],))
    if seller["account_status"] != "정상":  # 탈퇴·이용정지 판매자와는 새 거래를 시작하지 않는다
        raise HTTPException(409, f"판매자 계정이 '{seller['account_status']}' 상태라 채팅할 수 없습니다.")
    # ===== [기존 구현 - 비활성] 조회 후 별도 INSERT =====
    # room_no = execute(
    #     conn,
    #     "INSERT INTO chat_room (product_no, seller_no, buyer_no) VALUES (%s,%s,%s)",
    #     (product_no, p["seller_no"], member["member_no"]),
    # )
    # return {"room_no": room_no, "created": True}
    # ===== [수정 구현 - 활성] =====
    # 단일 SQL로 채팅방을 생성하거나 기존 방 ID를 반환한다.
    # 동일 요청 경합 시 UNIQUE 충돌을 HTTP 500으로 노출하지 않는다.
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO chat_room (product_no, seller_no, buyer_no) VALUES (%s,%s,%s)
               ON DUPLICATE KEY UPDATE room_no=LAST_INSERT_ID(room_no)""",
            (product_no, p["seller_no"], member["member_no"]),
        )
        room_no = cur.lastrowid
        created = cur.rowcount == 1
    return {"room_no": room_no, "created": created}


@router.get("/products/{product_no}/chats")
def product_chats(product_no: int, member=Depends(current_member), conn=Depends(get_db)):
    """판매자가 예약자/구매자를 고를 때 쓰는 채팅 참여자 목록"""
    p = fetch_one(conn, "SELECT seller_no FROM product WHERE product_no=%s", (product_no,))
    if p is None or p["seller_no"] != member["member_no"]:
        raise HTTPException(403, "판매자만 조회할 수 있습니다.")
    return fetch_all(
        conn,
        """SELECT r.room_no, r.buyer_no, m.nickname AS buyer_nickname, r.room_status
             FROM chat_room r JOIN member m ON m.member_no=r.buyer_no
            WHERE r.product_no=%s ORDER BY r.created_at""",
        (product_no,),
    )


@router.get("/chats")
def my_chats(member=Depends(current_member), conn=Depends(get_db)):
    """TRD-02 ⑦ 채팅방 목록: 마지막 메시지 + 안 읽은 개수"""
    me = member["member_no"]
    return fetch_all(
        conn,
        """SELECT r.room_no, r.product_no, r.room_status, p.title, p.trade_status,
                  IF(r.seller_no=%s, b.nickname, s.nickname) AS other_nickname,
                  lm.content AS last_message, lm.sent_at AS last_sent_at,
                  (SELECT COUNT(*) FROM chat_message c
                    WHERE c.room_no=r.room_no AND c.sender_no<>%s AND c.read_at IS NULL) AS unread
             FROM chat_room r
             JOIN product p ON p.product_no=r.product_no
             JOIN member s ON s.member_no=r.seller_no
             JOIN member b ON b.member_no=r.buyer_no
             LEFT JOIN chat_message lm ON lm.message_no =
                  (SELECT MAX(message_no) FROM chat_message WHERE room_no=r.room_no)
            WHERE %s IN (r.seller_no, r.buyer_no)
            ORDER BY COALESCE(lm.sent_at, r.created_at) DESC""",
        (me, me, me),
    )


@router.get("/chats/{room_no}")
def room_detail(room_no: int, member=Depends(current_member), conn=Depends(get_db)):
    room = _room_for(conn, room_no, member)
    # TRD-02 ⑥ 상대가 보낸 메시지를 읽음 처리
    execute(
        conn,
        "UPDATE chat_message SET read_at=NOW() WHERE room_no=%s AND sender_no<>%s AND read_at IS NULL",
        (room_no, member["member_no"]),
    )
    room["can_send"] = _can_send(conn, room)
    room["messages"] = fetch_all(
        conn,
        """SELECT c.message_no, c.sender_no, m.nickname AS sender_nickname, c.content, c.sent_at, c.read_at
             FROM chat_message c JOIN member m ON m.member_no=c.sender_no
            WHERE c.room_no=%s ORDER BY c.sent_at, c.message_no""",
        (room_no,),
    )
    return room


@router.post("/chats/{room_no}/messages", status_code=201)
def send_message(room_no: int, body: MessageIn, member=Depends(current_member), conn=Depends(get_db)):
    room = _room_for(conn, room_no, member)
    if not _can_send(conn, room):  # TRD-02 ⑨
        raise HTTPException(409, "메시지를 보낼 수 없는 채팅방입니다.")
    message_no = execute(
        conn,
        "INSERT INTO chat_message (room_no, sender_no, content) VALUES (%s,%s,%s)",
        (room_no, member["member_no"], body.content),
    )
    return {"message_no": message_no}
