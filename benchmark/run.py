#!/usr/bin/env python3
"""Defensive, repeatable integration benchmark for used-market-db.

* Targets only http://127.0.0.1:18080 / http://localhost:18080.
* Uses benchmark/compose.yml's disposable MySQL/API stack, never production AWS.
* Generates negative, boundary, authZ, transaction, and bounded concurrency cases.
* No dependencies beyond Python stdlib and Docker CLI (for test admin promotion).
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "http://127.0.0.1:18080"
BENCH_DIR = Path(__file__).resolve().parent
COMPOSE = BENCH_DIR / "compose.yml"
SEED = 260222


def request(method, path, *, data=None, token=None, form=False, upload=None, timeout=8):
    url = BASE + path
    headers = {"User-Agent": "used-market-benchmark/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if upload is not None:
        # upload = (field_name, filename, bytes, mime_type), for harmless test files only.
        boundary = "----usedmarkettest" + uuid.uuid4().hex
        parts = []
        for k, v in (data or {}).items():
            parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode("utf-8"))
        field, filename, blob, mime = upload
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n").encode("utf-8"))
        parts.append(blob)
        parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        payload = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        if form:
            payload = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
        else:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
    else:
        payload = None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            status, raw = res.status, res.read(200000)
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read(200000)
    except Exception as e:
        return {"status": 0, "body": {"error": str(e)}, "ms": round((time.perf_counter()-started)*1000, 1)}
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = {"body": raw[:180].decode("utf-8", errors="replace")}
    return {"status": status, "body": body, "ms": round((time.perf_counter()-started)*1000, 1)}


class Bench:
    def __init__(self, seed, random_cases, concurrency, deep=False):
        self.seed, self.random_cases, self.concurrency, self.deep = seed, random_cases, concurrency, deep
        self.rng = random.Random(seed)
        self.rows = []
        self.run_id = uuid.uuid4().hex[:9]
        self.serial = 0
        self.failed_printed = 0

    def check(self, group, name, response, expected, check=None):
        acceptable = [expected] if isinstance(expected, int) else list(expected)
        status_ok = response["status"] in acceptable
        check_error = None
        try:
            semantic_ok = check(response["body"]) if status_ok and check else True
        except Exception as exc:
            semantic_ok = False
            check_error = f"검증 콜백 오류: {type(exc).__name__}: {str(exc)[:160]}"
        passed = status_ok and semantic_ok
        self.rows.append({
            "case_id": len(self.rows) + 1,
            "group": group, "name": name, "status": response["status"],
            "expected": acceptable, "ok": bool(passed), "ms": response["ms"],
            "detail": "" if passed else (check_error or str(response["body"])[:180]),
        })
        if not passed:
            if self.failed_printed < 30:
                print(f"  FAIL {group}: {name} (HTTP {response['status']}, 예상 {acceptable})")
            self.failed_printed += 1
        return response["body"] if passed else None

    def call(self, group, name, method, path, expected, *, token=None, data=None, form=False, upload=None, check=None):
        r = request(method, path, data=data, token=token, form=form, upload=upload)
        result = self.check(group, name, r, expected, check=check)
        self.rows[-1].update({"method": method, "path": path[:280]})
        return result

    def identity(self, prefix="u"):
        self.serial += 1
        n = self.serial
        # member.nickname is VARCHAR(30). Long diagnostic prefixes must not
        # invalidate setup accounts when the case counter becomes 4+ digits.
        suffix = f"_{self.run_id}_{n}"
        nickname = prefix[:max(1, 30 - len(suffix))] + suffix
        # Valid 010-1234-5678-style telephone numbers unique per run.
        suffix = int(self.run_id[:6], 16) * 50 + n
        phone = f"010-{suffix % 10000:04d}-{(suffix // 10000) % 10000:04d}"
        return {
            "name": "자동테스트", "nickname": nickname, "phone": phone,
            "email": f"{nickname}@benchmark.test", "password": "TestPass_1234!",
        }

    def signup(self, prefix):
        info = self.identity(prefix)
        body = self.call("준비", f"{prefix} 회원가입", "POST", "/auth/signup", 201, data=info)
        if not body:
            raise RuntimeError(f"테스트 계정 생성 실패: {prefix}. DB 초기화 또는 충돌을 확인하세요.")
        info["member_no"] = body["member_no"]
        auth = self.call("준비", f"{prefix} 로그인", "POST", "/auth/login", 200,
                         data={"nickname": info["nickname"], "password": info["password"]})
        if not auth:
            raise RuntimeError("로그인 실패")
        info["token"] = auth["token"]
        return info

    def signup_root_staging_only(self):
        """Bootstrap the unique test root via INSERT, not a prohibited role UPDATE.

        The production schema correctly blocks promoting an existing user into root.
        This method runs exclusively against the verified disposable MySQL container.
        """
        info = self.identity("root")
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", info["password"].encode("utf-8"), salt.encode("utf-8"), 200_000
        ).hex()
        password_hash = f"pbkdf2${salt}${digest}"
        sql = (
            "INSERT INTO member (role, name, nickname, phone, email, password_hash) "
            f"VALUES ('root', '자동테스트', '{info['nickname']}', '{info['phone']}', "
            f"'{info['email']}', '{password_hash}'); "
            "SELECT LAST_INSERT_ID();"
        )
        cmd = [
            "docker", "compose", "-p", "used-market-bench", "-f", str(COMPOSE),
            "exec", "-T", "-e", "MYSQL_PWD=benchmark-local-only", "db",
            "mysql", "--default-character-set=utf8mb4", "-N", "-B", "-uroot",
            "used_market", "-e", sql,
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if p.returncode:
            raise RuntimeError("격리 테스트 DB의 루트 계정 초기 생성 실패: " + p.stderr[:300])
        try:
            info["member_no"] = int(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise RuntimeError("루트 계정 번호 확인 실패: " + p.stdout[:200]) from exc
        auth = self.call(
            "준비", "root 관리자 로그인", "POST", "/auth/login", 200,
            data={"nickname": info["nickname"], "password": info["password"]},
        )
        if not auth or auth.get("member", {}).get("role") != "root":
            raise RuntimeError("격리 테스트 DB의 루트 로그인 또는 권한 확인 실패")
        info["token"] = auth["token"]
        return info

    def promote_staging_only(self, member_no, role):
        """Change ordinary test user to staff only; root promotion is forbidden by DB."""
        if role != "staff" or not isinstance(member_no, int):
            raise ValueError("only staff promotion allowed")
        cmd = [
            "docker", "compose", "-p", "used-market-bench", "-f", str(COMPOSE),
            "exec", "-T", "-e", "MYSQL_PWD=benchmark-local-only", "db",
            "mysql", "-uroot", "used_market", "-e",
            f"UPDATE member SET role='{role}' WHERE member_no={member_no};",
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if p.returncode:
            raise RuntimeError("격리된 테스트 DB의 관리자 계정 생성 실패: " + p.stderr[:300])

    def product(self, seller, label="상품"):
        value = {
            "title": f"{label}_{self.run_id}_{self.serial}",
            "description": "예외 케이스 자동 시험 상품", "price": "15000", "item_condition": "새상품",
        }
        b = self.call("준비", f"{label} 등록", "POST", "/products", 201,
                      token=seller["token"], form=True, data=value)
        if not b:
            raise RuntimeError("상품 등록 실패")
        return b["product_no"]

    def run(self):
        print("[1/7] 읽기·건강 검사")
        self.call("공개 API", "health", "GET", "/health", 200, check=lambda d: d.get("ok") is True)
        self.call("공개 API", "상품 조회", "GET", "/products", 200, check=lambda d: isinstance(d, list))
        self.call("공개 API", "신고 사유", "GET", "/reports/reasons", 200, check=lambda d: isinstance(d, list))

        print("[2/7] 테스트 계정 생성 및 권한 설정")
        seller = self.signup("seller")
        buyer = self.signup("buyer")
        buyer2 = self.signup("buyer2")
        outsider = self.signup("outsider")
        root = self.signup_root_staging_only()
        staff = self.signup("staff")
        self.promote_staging_only(staff["member_no"], "staff")

        print("[3/7] 인증·입력 검증 난수 케이스")
        self.call("인증", "비로그인 내 정보", "GET", "/me", 401)
        self.call("인증", "임의 토큰", "GET", "/me", 401, token="invalid.token")
        self.call("인증", "비로그인 채팅", "GET", "/chats", 401)
        self.call("인증", "비로그인 상품 등록", "POST", "/products", 401, data={
            "title": "t", "description": "d", "price": "50", "item_condition": "새상품"
        }, form=True)
        self.call("권한", "일반회원 관리자 조회", "GET", "/admin/members", 403, token=buyer["token"])
        self.call("권한", "비로그인 관리자 조회", "GET", "/admin/members", 401)
        self.call("권한", "관리자 회원 목록", "GET", "/admin/members", 200, token=root["token"])
        self.call("인증", "없는 회원 로그인", "POST", "/auth/login", 401,
                  data={"nickname": "not_existing_user_XZZ", "password": "no"})
        for name, field, value in [
            ("빈 이름", "name", ""), ("긴 이름", "name", "X" * 51),
            ("짧은 닉네임", "nickname", "a"), ("긴 닉네임", "nickname", "x" * 31),
            ("전화 형식", "phone", "010-abc-ffff"), ("전화 누락 숫자", "phone", "010-123-456"),
            ("이메일 형식", "email", "invalid-email"), ("긴 이메일", "email", "x"*96+"@a.com"),
            ("짧은 비밀번호", "password", "abc"), ("긴 비밀번호", "password", "x"*101),
            ("긴 주소", "address", "x"*201), ("존재하지 않는 생년월일", "birth_date", "2026-02-30"),
        ]:
            info = self.identity("invalid")
            info[field] = value
            self.call("회원가입 경계", name, "POST", "/auth/signup", 422, data=info)
        for field in ("nickname", "email", "phone"):
            info = self.identity("duplicate")
            info[field] = seller[field]
            self.call("회원가입 중복", field, "POST", "/auth/signup", 409, data=info)
        self.call("인증", "로그인 비밀번호 불일치", "POST", "/auth/login", 401,
                  data={"nickname": buyer["nickname"], "password": "wrong"})

        # Fuzz invalid signup inputs; property: any single invalid field -> 422, never 500.
        mutate = [
            ("name", lambda: ""), ("name", lambda: "a" * self.rng.randrange(51, 120)),
            ("nickname", lambda: "x" * self.rng.randrange(31, 70)),
            ("email", lambda: "bad-" + self.run_id),
            ("phone", lambda: "PHONE" + str(self.rng.randint(10, 90000))),
            ("password", lambda: "x" * self.rng.randrange(101, 180)),
            ("address", lambda: "x" * self.rng.randrange(201, 400)),
        ]
        for i in range(self.random_cases):
            field, generator = self.rng.choice(mutate)
            info = self.identity("fuzz")
            info[field] = generator()
            self.call("회원가입 자동생성", f"seed={self.seed} #{i:03d} {field}",
                      "POST", "/auth/signup", 422, data=info)

        print("[4/7] 상품·채팅·거래 방어")
        p = self.product(seller, "기준상품")
        valid = {"title": "정상 상품", "description": "설명", "price": "100", "item_condition": "새상품"}
        bad_product = [
            ("빈 제목", "title", ""), ("공백 제목", "title", "   "),
            ("긴 제목", "title", "a"*101), ("음수 가격", "price", "-1"),
            ("초과 가격", "price", "4294967296"), ("숫자 아닌 가격", "price", "abc"),
            ("상품 상태 오류", "item_condition", "파손"),
        ]
        for name, field, val in bad_product:
            x = dict(valid); x[field] = val
            self.call("상품 경계", name, "POST", "/products", 422, token=seller["token"], data=x, form=True)
        for i in range(max(10, self.random_cases // 3)):
            field, val = self.rng.choice([
                ("title", " "), ("title", "x" * self.rng.randrange(101, 140)),
                ("price", str(-self.rng.randint(1, 10**9))),
                ("price", str(4294967295 + self.rng.randint(1, 10**9))),
                ("item_condition", "INVALID" + str(self.rng.randint(1, 10000))),
            ])
            x = dict(valid); x[field] = val
            self.call("상품 자동생성", f"seed={self.seed} #{i:03d} {field}", "POST", "/products", 422,
                      token=seller["token"], data=x, form=True)
        # Content validation: current code checks filename extension only; a fake JPEG should be rejected.
        self.call("이미지 검증", "JPEG 확장자지만 파일 내용이 이미지 아님", "POST", "/products", 422,
                  token=seller["token"], data=valid,
                  upload=("images", "fake-image.jpg", b"THIS IS NOT ACTUALLY A JPEG", "image/jpeg"))
        self.call("상품 권한", "타인 수정", "PUT", f"/products/{p}", 403,
                  token=outsider["token"], data=valid, form=True)
        self.call("상품 권한", "타인 삭제", "DELETE", f"/products/{p}", 403, token=outsider["token"])
        self.call("상품", "없는 상품", "GET", "/products/2147483647", 404)
        self.call("채팅", "판매자 본인 채팅", "POST", f"/products/{p}/chat", 400, token=seller["token"])
        self.call("채팅", "없는 상품 채팅", "POST", "/products/2147483647/chat", 404, token=buyer["token"])
        room = self.call("채팅", "구매자 채팅 생성", "POST", f"/products/{p}/chat", 200, token=buyer["token"])
        if not room: raise RuntimeError("채팅 생성 실패")
        room_id = room["room_no"]
        self.call("채팅", "중복 채팅은 기존 방", "POST", f"/products/{p}/chat", 200,
                  token=buyer["token"], check=lambda d: d.get("room_no") == room_id and d.get("created") is False)
        self.call("채팅", "다른 구매자 방 생성", "POST", f"/products/{p}/chat", 200, token=buyer2["token"])
        self.call("채팅 권한", "제3자 메시지 조회", "GET", f"/chats/{room_id}", 404, token=outsider["token"])
        self.call("채팅 권한", "제3자 메시지 등록", "POST", f"/chats/{room_id}/messages", 404,
                  token=outsider["token"], data={"content": "몰래 보내기"})
        for text in ("", "X" * 2001):
            self.call("채팅 경계", f"메시지 길이 {len(text)}", "POST", f"/chats/{room_id}/messages", 422,
                      token=buyer["token"], data={"content": text})
        self.call("채팅", "메시지 전송", "POST", f"/chats/{room_id}/messages", 201,
                  token=buyer["token"], data={"content": "안녕하세요"})
        self.call("거래 권한", "구매자 예약 요청", "POST", f"/products/{p}/reserve", 403,
                  token=buyer["token"], data={"buyer_no": buyer["member_no"]})
        self.call("거래 경계", "채팅 미참여자를 예약", "POST", f"/products/{p}/reserve", 422,
                  token=seller["token"], data={"buyer_no": outsider["member_no"]})
        self.call("거래", "정상 예약", "POST", f"/products/{p}/reserve", 200,
                  token=seller["token"], data={"buyer_no": buyer["member_no"]})
        self.call("거래", "중복 예약", "POST", f"/products/{p}/reserve", 409,
                  token=seller["token"], data={"buyer_no": buyer["member_no"]})
        self.call("거래", "예약자 아닌 구매자로 완료", "POST", f"/products/{p}/complete", 409,
                  token=seller["token"], data={"buyer_no": buyer2["member_no"]})
        self.call("거래", "예약중 삭제 금지", "DELETE", f"/products/{p}", 409, token=seller["token"])
        self.call("거래", "예약 해제", "POST", f"/products/{p}/unreserve", 200, token=seller["token"])
        self.call("거래", "중복 예약 해제", "POST", f"/products/{p}/unreserve", 409, token=seller["token"])
        self.call("거래", "구매자 확정", "POST", f"/products/{p}/complete", 200,
                  token=seller["token"], data={"buyer_no": buyer["member_no"]})
        self.call("거래", "중복 완료", "POST", f"/products/{p}/complete", 409,
                  token=seller["token"], data={"buyer_no": buyer["member_no"]})
        self.call("거래", "완료된 상품 새 채팅", "POST", f"/products/{p}/chat", 409, token=outsider["token"])
        self.call("거래", "완료 상태 DB 반영", "GET", f"/products/{p}", 200,
                  check=lambda d: d.get("trade_status") == "판매완료" and d.get("buyer_no") == buyer["member_no"])

        print("[5/7] 신고·제재 및 관리자 권한")
        self.call("신고", "본인 회원 신고", "POST", "/reports", 400, token=buyer["token"],
                  data={"target_type": "회원", "target_no": buyer["member_no"], "reason_code": "기타", "content": "t"})
        self.call("신고", "없는 회원 신고", "POST", "/reports", 404, token=buyer["token"],
                  data={"target_type": "회원", "target_no": 2147483647, "reason_code": "기타", "content": "t"})
        self.call("신고", "존재하지 않는 사유", "POST", "/reports", 422, token=buyer["token"],
                  data={"target_type": "회원", "target_no": seller["member_no"], "reason_code": "NOT_A_REASON", "content": "t"})
        self.call("신고", "게시글 자기 신고", "POST", "/reports", 400, token=seller["token"],
                  data={"target_type": "상품게시글", "target_no": p, "reason_code": "기타", "content": "t"})
        report_data = {"target_type": "회원", "target_no": seller["member_no"], "reason_code": "기타", "content": "신고 테스트"}
        report = self.call("신고", "정상 신고", "POST", "/reports", 201, token=buyer["token"], data=report_data)
        self.call("신고", "중복 신고", "POST", "/reports", 409, token=buyer["token"], data=report_data)
        if not report: raise RuntimeError("신고 생성 실패")
        rn = report["report_no"]
        self.call("관리자 권한", "일반회원 신고 조회", "GET", f"/admin/reports/{rn}", 403, token=buyer["token"])
        self.call("관리자", "관리자 신고 조회", "GET", f"/admin/reports/{rn}", 200, token=root["token"])
        self.call("관리자", "검토 시작", "POST", f"/admin/reports/{rn}/review", 200, token=root["token"])
        self.call("관리자", "중복 검토 시작", "POST", f"/admin/reports/{rn}/review", 409, token=root["token"])
        self.call("관리자", "신고 처리", "POST", f"/admin/reports/{rn}/process", 201,
                  token=root["token"], data={"result": "조치없음", "reason": "검토 끝"})
        self.call("관리자", "신고 중복 처리", "POST", f"/admin/reports/{rn}/process", 409,
                  token=root["token"], data={"result": "조치없음", "reason": "중복"})
        self.call("제재 권한", "일반회원 제재 시도", "POST", f"/admin/members/{seller['member_no']}/sanctions", 403,
                  token=buyer["token"], data={"sanction_type": "경고", "reason": "권한 없음"})
        self.call("제재 권한", "관리자 자기 제재", "POST", f"/admin/members/{root['member_no']}/sanctions", 400,
                  token=root["token"], data={"sanction_type": "경고", "reason": "셀프"})
        self.call("제재 권한", "staff가 root 제재", "POST", f"/admin/members/{root['member_no']}/sanctions", 403,
                  token=staff["token"], data={"sanction_type": "경고", "reason": "권한 없음"})
        self.call("제재 경계", "일시정지 종료시각 없음", "POST", f"/admin/members/{outsider['member_no']}/sanctions", 422,
                  token=root["token"], data={"sanction_type": "일시정지", "reason": "종료 누락"})
        self.call("제재 경계", "종료시각 과거", "POST", f"/admin/members/{outsider['member_no']}/sanctions", 422,
                  token=root["token"], data={"sanction_type": "일시정지", "reason": "과거", "end_at": "2021-01-01T00:00:00"})
        self.call("제재", "경고 적용(알림 대상)", "POST", f"/admin/members/{outsider['member_no']}/sanctions", 201,
                  token=root["token"], data={"sanction_type": "경고", "reason": "정상적인 테스트 경고"})
        future = (datetime.now() + timedelta(days=2)).isoformat(timespec="seconds")
        suspension = self.call("제재", "일시정지 적용", "POST", f"/admin/members/{outsider['member_no']}/sanctions", 201,
                               token=root["token"], data={"sanction_type": "일시정지", "reason": "테스트 정지", "end_at": future})
        self.call("제재", "중복 일시정지", "POST", f"/admin/members/{outsider['member_no']}/sanctions", 409,
                  token=root["token"], data={"sanction_type": "일시정지", "reason": "중복", "end_at": future})
        self.call("제재", "정지 계정의 API 접근 차단", "GET", "/me", 403, token=outsider["token"])
        if suspension:
            self.call("제재", "제재 해제", "POST", f"/admin/sanctions/{suspension['sanction_no']}/release", 200,
                      token=root["token"], data={"reason": "테스트 해제"})
            self.call("제재", "중복 해제", "POST", f"/admin/sanctions/{suspension['sanction_no']}/release", 409,
                      token=root["token"], data={"reason": "중복 해제"})
            self.call("제재", "제재 해제 후 로그인 허용", "GET", "/me", 200, token=outsider["token"])
        # Known tricky case: timezone-aware ISO input must not crash the API.
        time_target = self.signup("timezoneprobe")
        self.call("제재 경계", "타임존 포함 일시정지 - 500 금지", "POST",
                  f"/admin/members/{time_target['member_no']}/sanctions", {201, 422}, token=root["token"],
                  data={"sanction_type": "일시정지", "reason": "시간대 처리", "end_at": future + "+09:00"})

        print("[6/7] 동시성 경쟁 조건")
        # Identical concurrent chat opens on a new product. Should produce one room, no 500.
        for round_no in range(3):
            pc = self.product(seller, f"동시채팅{round_no}")
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                requests = list(pool.map(lambda _: request("POST", f"/products/{pc}/chat", token=buyer["token"]),
                                         range(self.concurrency)))
            ids = {r["body"].get("room_no") for r in requests if isinstance(r["body"], dict) and r["status"] == 200}
            for i, r in enumerate(requests):
                self.check("동시성 채팅", f"round={round_no} worker={i}", r, 200)
            self.check("동시성 채팅", f"round={round_no} 방 번호 단일성",
                       {"status": 200 if len(ids) == 1 else 0, "body": {"room_ids": list(ids)}, "ms": 0}, 200)

        # Concurrent duplicate signup should have exactly one success (other attempts 409).
        duplicate = self.identity("racesignup")
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            responses = list(pool.map(lambda _: request("POST", "/auth/signup", data=duplicate), range(self.concurrency)))
        for i, r in enumerate(responses):
            self.check("동시성 가입", f"worker={i}", r, {201, 409})
        self.check("동시성 가입", "성공 1건 보장",
                   {"status": 200 if sum(r["status"] == 201 for r in responses) == 1 else 0,
                    "body": {"statuses": [r["status"] for r in responses]}, "ms": 0}, 200)

        if self.deep:
            from deep_suite import run_extended
            run_extended(self, seller=seller, buyer=buyer, buyer2=buyer2,
                         outsider=outsider, root=root, staff=staff)
        print("[7/7] 결과 기록")
        self.report()

    def report(self, aborted=None):
        ok = sum(row["ok"] for row in self.rows)
        fail = [row for row in self.rows if not row["ok"]]
        ms = sorted(row["ms"] for row in self.rows if row["ms"] > 0)
        counts = {}
        for row in self.rows:
            cat = counts.setdefault(row["group"], {"pass": 0, "fail": 0})
            cat["pass" if row["ok"] else "fail"] += 1
        out = {
            "seed": self.seed, "random_cases": self.random_cases, "concurrency": self.concurrency,
            "deep_suite": self.deep,
            "completed": aborted is None,
            "aborted_reason": aborted,
            "total": len(self.rows), "pass": ok, "fail": len(fail),
            "pass_rate_percent": round(ok / len(self.rows) * 100, 2) if self.rows else 0,
            "latency_ms_p50": ms[len(ms)//2] if ms else None,
            "latency_ms_p95": ms[int((len(ms)-1)*.95)] if ms else None,
            "categories": counts, "failures": fail,
        }
        outdir = BENCH_DIR / "out"
        outdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jpath = outdir / f"bench_{stamp}.json"
        mpath = outdir / f"bench_{stamp}.md"
        jpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = ["# 중고거래 API 방어 벤치마크", "",
                 "**실행 상태: 중단 — 전체 테스트 미수행**" if aborted else "**실행 상태: 완료**", "",
                 f"중단 사유: {aborted}" if aborted else "",
                 f"Seed: `{self.seed}` / 동시 요청: `{self.concurrency}`",
                 f"총 {len(self.rows)}개, PASS {ok}개, FAIL {len(fail)}개, 방어 성공률 {out['pass_rate_percent']}%",
                 f"응답 지연 p50 {out['latency_ms_p50']} ms / p95 {out['latency_ms_p95']} ms", "",
                 "| 분야 | PASS | FAIL |", "|---|---:|---:|"]
        lines += [f"| {cat} | {stats['pass']} | {stats['fail']} |" for cat,stats in sorted(counts.items())]
        lines += ["", "## 실패 케이스"]
        lines += [f"- **{x['group']} / {x['name']}**: HTTP {x['status']} (예상 {x['expected']}), {x['detail']}" for x in fail] or ["- 없음"]
        mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if aborted:
            print("\n[주의] 실행 중단: 다음 통계는 완료된 일부 케이스에만 해당합니다.")
        print(f"\n방어 벤치마크: {ok}/{len(self.rows)} 통과 ({out['pass_rate_percent']}%), 실패 {len(fail)}건")
        print(f"p50 {out['latency_ms_p50']}ms / p95 {out['latency_ms_p95']}ms")
        print("JSON:", jpath)
        print("Markdown:", mpath)
        if fail:
            print("첫 번째 실패:", fail[0]["group"], fail[0]["name"], fail[0]["detail"][:120])
        return out


def assert_isolated_compose():
    """Fail closed: benchmark must run against the exact disposable Compose API.

    The loopback URL alone is NOT sufficient: it could be forwarded to production.
    Check Docker project/service labels, API environment and port mapping first.
    """
    basecmd = ["docker", "compose", "-p", "used-market-bench", "-f", str(COMPOSE)]
    try:
        result = subprocess.run(basecmd + ["ps", "-q", "api"], capture_output=True, text=True, timeout=15, check=True)
        cid = result.stdout.strip()
        if not cid:
            raise RuntimeError("격리된 테스트용 api 컨테이너를 찾지 못했습니다.")
        meta = subprocess.run(["docker", "inspect", cid], capture_output=True, text=True, timeout=15, check=True)
        info = json.loads(meta.stdout)[0]
        labels = info["Config"]["Labels"] or {}
        actual = dict(kv.split("=", 1) for kv in info["Config"]["Env"] if "=" in kv)
        checks = {
            "Compose project": labels.get("com.docker.compose.project") == "used-market-bench",
            "Compose service": labels.get("com.docker.compose.service") == "api",
            "DB_HOST": actual.get("DB_HOST") == "db",
            "DB_NAME": actual.get("DB_NAME") == "used_market",
            "DB_PASSWORD": actual.get("DB_PASSWORD") == "benchmark-local-only",
            "S3 disabled": actual.get("S3_BUCKET") == "",
            "SECRET_KEY": actual.get("SECRET_KEY") == "benchmark-secret-only-do-not-use-in-production",
            "no AWS static keys": "AWS_ACCESS_KEY_ID" not in actual and "AWS_SECRET_ACCESS_KEY" not in actual,
        }
        ports = info.get("NetworkSettings", {}).get("Ports", {}).get("8000/tcp") or []
        checks["localhost port"] = bool(ports) and all(
            p.get("HostIp") in ("127.0.0.1", "::1") and p.get("HostPort") == "18080" for p in ports
        )
        db = subprocess.run(basecmd + ["ps", "-q", "db"], capture_output=True, text=True, timeout=15, check=True)
        checks["isolated MySQL"] = bool(db.stdout.strip())
        wrong = [name for name, passed in checks.items() if not passed]
        if wrong:
            raise RuntimeError("테스트 DB 격리 검증 실패: " + ", ".join(wrong))
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, ValueError, KeyError, IndexError) as exc:
        raise RuntimeError("테스트 컨테이너를 검증할 수 없습니다. Docker Desktop/Engine 실행 상태를 확인하세요.") from exc


def main():
    parser = argparse.ArgumentParser(description="격리형 중고거래 API 예외 케이스 벤치마크")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--random-cases", type=int, default=500)
    parser.add_argument("--deep", action="store_true", help="추가 경계/권한/동시성/퍼징 수백~수천 케이스")
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()
    if not 0 <= args.random_cases <= 5000 or not 1 <= args.concurrency <= 12:
        parser.error("random-cases는 0~5000, concurrency는 1~12만 허용합니다.")
    assert urllib.parse.urlsplit(BASE).hostname in ("localhost", "127.0.0.1"), "로컬만 허용"
    assert urllib.parse.urlsplit(BASE).port == 18080, "전용 테스트 포트만 허용"
    if not COMPOSE.is_file():
        parser.error("benchmark/compose.yml 파일이 없습니다.")
    try:
        assert_isolated_compose()
    except RuntimeError as exc:
        parser.error(str(exc))
    health = request("GET", "/health", timeout=3)
    if health["status"] != 200:
        parser.error("로컬 테스트 API가 없습니다. 먼저 'docker compose -p used-market-bench -f benchmark/compose.yml up -d --build' 실행")
    b = Bench(args.seed, args.random_cases, args.concurrency, args.deep)
    try:
        b.run()
    except Exception as e:
        print("\n[중단] ", str(e), file=sys.stderr)
        b.report(aborted=str(e))
        sys.exit(2)
    if any(not x["ok"] for x in b.rows):
        sys.exit(1)


if __name__ == "__main__":
    main()
