"""sample_data.sql 의 비밀번호 해시는 예시 문자열이라 로그인이 안 된다.
데모용으로 모든 회원 비밀번호를 1234 로 맞춘다: uv run python -m scripts.demo_passwords
"""

from app.auth import hash_password
from app.db import connect, execute


def main():
    conn = connect()
    n = execute(conn, "UPDATE member SET password_hash=%s", (hash_password("1234"),))
    conn.commit()
    conn.close()
    print(f"회원 {n}명 비밀번호를 1234 로 설정")


if __name__ == "__main__":
    main()
