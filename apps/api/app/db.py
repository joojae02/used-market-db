import os
from collections.abc import Iterator

import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = dict(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "used_market"),
    charset="utf8mb4",
    cursorclass=DictCursor,
    autocommit=False,
)


def connect() -> pymysql.Connection:
    return pymysql.connect(**DB_CONFIG)


def get_db() -> Iterator[pymysql.Connection]:
    """요청 하나 = 트랜잭션 하나. 정상 종료 시 commit, 예외 시 rollback."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_one(conn, sql: str, params=None) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def fetch_all(conn, sql: str, params=None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def execute(conn, sql: str, params=None) -> int:
    """INSERT 면 lastrowid, 그 외엔 영향받은 행 수를 돌려준다."""
    with conn.cursor() as cur:
        affected = cur.execute(sql, params)
        return cur.lastrowid or affected
