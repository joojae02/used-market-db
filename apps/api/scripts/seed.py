"""데모용 시드 데이터. schema.sql 실행 후: uv run python -m scripts.seed
모든 계정 비밀번호: 1234
"""

from app.auth import hash_password
from app.db import connect, execute

MEMBERS = [
    # role, name, nickname, phone, email
    ("root", "루트", "root", "010-0000-0000", "root@demo.com"),
    ("moderator", "김모더", "mod", "010-1111-1111", "mod@demo.com"),
    ("user", "이판매", "seller", "010-2222-2222", "seller@demo.com"),
    ("user", "박구매", "buyer", "010-3333-3333", "buyer@demo.com"),
    ("user", "최구매", "buyer2", "010-4444-4444", "buyer2@demo.com"),
]

PRODUCTS = [
    # seller nickname, title, description, price, condition, area, offer
    ("seller", "아이패드 에어 5세대", "케이스 포함, 잔기스 조금", 450000, "거의새것", "서울 마포구", 1),
    ("seller", "자전거 팝니다", "1년 탔어요", 120000, "사용감있음", "서울 은평구", 0),
    ("buyer", "전공책 데이터베이스론", "필기 약간 있음", 15000, "사용감있음", None, 1),
]


def main():
    conn = connect()
    pw = hash_password("1234")
    ids = {}
    for role, name, nick, phone, email in MEMBERS:
        ids[nick] = execute(
            conn,
            "INSERT INTO member (role, name, nickname, phone, email, password_hash) VALUES (%s,%s,%s,%s,%s,%s)",
            (role, name, nick, phone, email, pw),
        )
    for seller, title, desc, price, cond, area, offer in PRODUCTS:
        execute(
            conn,
            """INSERT INTO product (seller_no, title, description, price, item_condition, trade_area, price_offer_yn)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (ids[seller], title, desc, price, cond, area, offer),
        )
    room = execute(
        conn,
        "INSERT INTO chat_room (product_no, seller_no, buyer_no) VALUES (1,%s,%s)",
        (ids["seller"], ids["buyer"]),
    )
    execute(conn, "INSERT INTO chat_message (room_no, sender_no, content) VALUES (%s,%s,%s)",
            (room, ids["buyer"], "안녕하세요, 아직 판매하시나요?"))
    execute(
        conn,
        """INSERT INTO report (reporter_no, target_type, target_product_no, reason_code, content)
           VALUES (%s,'상품게시글',2,'사기의심','사진이 인터넷 이미지 같아요')""",
        (ids["buyer2"],),
    )
    conn.commit()
    conn.close()
    print("seed 완료:", ", ".join(f"{k}(#{v})" for k, v in ids.items()), "/ 비밀번호 1234")


if __name__ == "__main__":
    main()
