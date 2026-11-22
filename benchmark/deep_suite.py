"""Extra defensive integration cases for the used-market-db demo API.

Run ONLY from the isolated local Docker Compose project.  This module is
called by benchmark/run.py after its baseline fixtures have been created.
No load testing, no requests to an internet address, no AWS credentials.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import random
import string
import urllib.error
import urllib.parse
import urllib.request

from run import BASE, request

MAX_ID = 9223372036854775807


def _valid_item(name="test item", price="1000"):
    return {"title": name, "description": "격리 테스트 상품", "price": str(price), "item_condition": "새상품"}


def _report(target_type, target_no, content="문제 신고"):
    return {"target_type": target_type, "target_no": target_no, "reason_code": "기타", "content": content}


def _raw(method, path, raw: bytes, content_type: str, token=None):
    """Small raw HTTP payloads for malformed JSON/content-type checks."""
    headers = {"Content-Type": content_type, "User-Agent": "used-market-local-test/2.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=raw, method=method, headers=headers)
    import time
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=7) as res:
            code, payload = res.status, res.read(2000)
    except urllib.error.HTTPError as exc:
        code, payload = exc.code, exc.read(2000)
    except Exception as exc:
        return {"status": 0, "body": {"error": str(exc)}, "ms": round((time.perf_counter() - start)*1000, 1)}
    try:
        body = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        body = {"body": payload.decode(errors="replace")[:120]}
    return {"status": code, "body": body, "ms": round((time.perf_counter() - start)*1000, 1)}


def _record_check(b, group, name, predicate, detail):
    b.check(group, name, {"status": 200 if predicate else 0, "body": detail, "ms": 0}, 200)


def _call(b, group, name, method, path, expected, *, token=None, data=None, form=False, check=None):
    return b.call(group, name, method, path, expected, token=token, data=data, form=form, check=check)


def _map_cases(b, group, method, path, cases, *, token=None, form=False):
    for label, data, expected in cases:
        _call(b, group, label, method, path, expected, token=token, form=form, data=data)


def run_extended(b, *, seller, buyer, buyer2, outsider, root, staff):
    """Run a large deterministic matrix and constrained fuzzing.  No prod I/O."""
    rng = b.rng
    print("[EXT 1/8] Endpoint coverage, malformed requests and access control")

    # Static route/path/method cases.  Only safe local HTTP requests.
    invalid_paths = [
        ("상품 ID 문자열", "/products/not-a-number", 422),
        ("상품 ID 음수", "/products/-1", 404),
        ("상품 ID 초대형", f"/products/{MAX_ID}", 404),
        ("상품 ID 0", "/products/0", 404),
        ("회원 ID 문자열", "/members/not-a-number", 422),
        ("회원 ID 0", "/members/0", 404),
        ("회원 ID 음수", "/members/-1", 404),
        ("회원 ID 큰 수", f"/members/{MAX_ID}", 404),
        ("상품 없는 경로", "/products/0/unknown", 404),
        ("존재하지 않는 API", "/definitely-not-a-real-route", 404),
    ]
    for name, path, expected in invalid_paths:
        _call(b, "라우팅·경계", name, "GET", path, expected)

    for method, path in [
        ("POST", "/health"), ("DELETE", "/health"), ("POST", "/reports/reasons"),
        ("PUT", "/me"), ("PATCH", "/auth/login"), ("DELETE", "/auth/signup"),
        ("POST", "/members/1"), ("PUT", "/admin/members"),
        ("PATCH", "/products"), ("DELETE", "/chats"),
    ]:
        _call(b, "허용되지 않은 메서드", method + " " + path, method, path, 405)

    for name, path, token in [
        ("내 정보", "/me", None), ("로그인 이력", "/me/logins", None),
        ("내 상품", "/products/mine", None), ("구매내역", "/products/purchased", None),
        ("내 채팅", "/chats", None), ("내 신고", "/reports/mine", None),
        ("관리자 목록", "/admin/members", None),
        ("관리자 신고", "/admin/reports", None),
        ("관리자 상품", "/admin/products", None),
        ("내 정보 무효 토큰", "/me", "broken"),
        ("내 상품 무효 토큰", "/products/mine", "broken"),
    ]:
        _call(b, "비인증 차단", name, "GET", path, 401, token=token)

    # Authorization matrix across GET and mutating endpoints; no state changes should occur.
    auth_paths = [
        ("GET", "/admin/members", None),
        ("GET", f"/admin/members/{seller['member_no']}", None),
        ("GET", "/admin/products", None),
        ("GET", "/admin/reports", None),
        ("GET", "/admin/reports/999999", None),
        ("GET", "/admin/products/999999/actions", None),
        ("POST", f"/admin/members/{seller['member_no']}/sanctions", {"sanction_type": "경고", "reason": "권한 검증"}),
        ("POST", "/admin/reports/999999/review", None),
        ("POST", "/admin/reports/999999/process", {"result": "반려", "reason": "권한 검증"}),
        ("POST", "/admin/products/999999/actions", {"action_type": "삭제", "reason": "권한 검증"}),
        ("PATCH", f"/admin/members/{seller['member_no']}/role", {"role": "staff"}),
        ("POST", "/admin/sanctions/999999/release", {"reason": "권한 검증"}),
    ]
    for method, path, payload in auth_paths:
        _call(b, "권한 매트릭스", "비로그인 " + method + " " + path, method, path, 401, data=payload)
        _call(b, "권한 매트릭스", "일반회원 " + method + " " + path, method, path, 403, data=payload, token=buyer["token"])

    # Bad tokens are expected to be rejected even for dozens of shapes.
    alphabet = string.ascii_letters + string.digits + "-_!.$"
    for i in range(45):
        invalid_token = "".join(rng.choices(alphabet, k=rng.randint(1, 220)))
        if invalid_token == buyer["token"]:
            invalid_token += "x"
        _call(b, "서명·인증 변형", f"잘못된 Bearer #{i:02d}", "GET", "/me", 401, token=invalid_token)

    for name, raw, mime in [
        ("잘린 JSON", b'{"nickname":', "application/json"),
        ("잘못된 JSON 구조", b'{"nickname":"xx",', "application/json"),
        ("문자열 본문", b'"not an object"', "application/json"),
        ("숫자 본문", b'12345', "application/json"),
        ("배열 본문", b'[1,2,3]', "application/json"),
        ("null 본문", b'null', "application/json"),
        ("바이너리 UTF-8", b'\xff\xfe\xfa', "application/json"),
    ]:
        # Malformed JSON / invalid UTF-8 is a client error. Depending on
        # Starlette JSON decoding and validation it can be 400 or 422.
        b.check("비정상 JSON", name, _raw("POST", "/auth/login", raw, mime), {400, 422})

    print("[EXT 2/8] Signup and login mutation matrix")
    # Invalid precise boundary values and data types.
    bad_signup = [
        ("이름 없음", "name", "missing"), ("이름 null", "name", None),
        ("이름 공백 없는 빈값", "name", ""),
        ("닉네임 없음", "nickname", "missing"), ("닉네임 null", "nickname", None),
        ("닉네임 한 글자", "nickname", "a"),
        ("전화 없음", "phone", "missing"), ("전화 null", "phone", None),
        ("전화 국가번호", "phone", "+821012345678"),
        ("전화 문자 포함", "phone", "010-abcd-5555"),
        ("전화 짧음", "phone", "010-12-4567"),
        ("전화 길이 초과", "phone", "010-12345-12345"),
        ("이메일 없음", "email", "missing"), ("이메일 null", "email", None),
        ("이메일 공백", "email", "user @test.com"),
        ("이메일 @ 없음", "email", "user.test.com"),
        ("이메일 도메인 없음", "email", "user@"),
        ("이메일 TLD 없음", "email", "user@server"),
        ("이메일 줄바꿈", "email", "user@site.com\n"),
        ("패스워드 없음", "password", "missing"), ("패스워드 null", "password", None),
        ("패스워드 세 글자", "password", "abc"),
        ("주소 201자", "address", "a"*201),
        ("생년월일 존재하지 않음", "birth_date", "2026-02-30"),
        ("생년월일 날짜가 아님", "birth_date", "not-a-date"),
        ("생년월일 배열", "birth_date", [1,2,3]),
    ]
    for name, key, value in bad_signup:
        data = b.identity("badext")
        if value == "missing": data.pop(key)
        else: data[key] = value
        _call(b, "회원가입 상세 경계", name, "POST", "/auth/signup", 422, data=data)

    # For each string length, test exactly one below and one above declared bounds.
    for field, lengths in {
        "name": [0, 51, 52, 120, 256, 1024],
        "nickname": [0, 1, 31, 32, 64, 256],
        "password": [0, 1, 2, 3, 101, 102, 256, 1024],
        "address": [201, 202, 256, 1024],
    }.items():
        for length in lengths:
            data = b.identity("length")
            data[field] = "Z" * length
            _call(b, "문자열 길이 매트릭스", f"{field}: {length}자", "POST", "/auth/signup", 422, data=data)

    # Independent valid 2/30 char nickname, 4/100 char password, price boundaries later.
    for length in (2, 30):
        ident = b.identity("edgeok")
        ident["nickname"] = ("v" + str(b.run_id) + "z"*30)[:length]
        if length == 2:
            ident["nickname"] = "z" + str(b.serial % 10)
        _call(b, "회원가입 정상 경계", f"닉네임 {length}자", "POST", "/auth/signup", 201, data=ident)
    for length in (4, 100):
        ident = b.identity("passok")
        ident["password"] = "P" * length
        _call(b, "회원가입 정상 경계", f"비밀번호 {length}자", "POST", "/auth/signup", 201, data=ident)

    for name, login_data in [
        ("로그인 nickname 없음", {"password": "x"}),
        ("로그인 password 없음", {"nickname": "x"}),
        ("로그인 null 닉네임", {"nickname": None, "password": "x"}),
        ("로그인 숫자 패스워드", {"nickname": "x", "password": 1234}),
    ]:
        _call(b, "로그인 요청 검증", name, "POST", "/auth/login", 422, data=login_data)

    locked = b.signup("locked")
    for i in range(5):
        _call(b, "로그인 제한", f"연속 실패 #{i+1}", "POST", "/auth/login", 401,
              data={"nickname": locked["nickname"], "password": "wrong-password"})
    _call(b, "로그인 제한", "정확한 비밀번호라도 잠금 지속", "POST", "/auth/login", 423,
          data={"nickname": locked["nickname"], "password": locked["password"]})

    print("[EXT 3/8] Product boundaries, uploads, state transitions")
    for i, price in enumerate(["0", "1", "4294967294", "4294967295"]):
        out = _call(b, "상품 정상 경계", f"가격 {price}", "POST", "/products", 201,
                    token=seller["token"], data=_valid_item(f"가격경계_{b.run_id}_{i}", price), form=True)
        if out:
            _call(b, "상품 정상 경계", f"가격 저장 검증 {price}", "GET", f"/products/{out['product_no']}", 200,
                  check=lambda v, p=int(price): v.get("price") == p)

    for size in (1, 100):
        title = "한" * size
        out = _call(b, "상품 정상 경계", f"상품명 {size}자", "POST", "/products", 201,
                    token=seller["token"], data=_valid_item(title, "0"), form=True)
        if out:
            _call(b, "상품 정상 경계", f"상품명 {size}자 저장", "GET", f"/products/{out['product_no']}", 200,
                  check=lambda v, title=title: v.get("title") == title)

    for name, data in [
        ("상품 제목 누락", {"description":"d", "price":"100", "item_condition":"새상품"}),
        ("상품 설명 누락", {"title":"t", "price":"100", "item_condition":"새상품"}),
        ("상품 가격 누락", {"title":"t", "description":"d", "item_condition":"새상품"}),
        ("상품 상태 누락", {"title":"t", "description":"d", "price":"100"}),
        ("상품 가격 소수", _valid_item("fraction", "1.2")),
        ("상품 가격 공백", _valid_item("blank price", "")),
        ("상품 가격 매우 큰 숫자", _valid_item("large", "9"*64)),
        ("상품 가격 NaN", _valid_item("nan", "NaN")),
        ("상품 가격 Infinity", _valid_item("inf", "Infinity")),
        ("상품 상태 대소문자", {**_valid_item(), "item_condition": "NEW"}),
        ("상품명 101자", _valid_item("a"*101)),
        ("상품명 공백만", _valid_item(" "*10)),
    ]:
        _call(b, "상품 요청 검증", name, "POST", "/products", 422,
              token=seller["token"], data=data, form=True)

    item = b.product(seller, "예외대상")
    for name, method, token, path, data, form, expected in [
        ("비소유자 상품 수정", "PUT", buyer["token"], f"/products/{item}", _valid_item("탈취"), True, 403),
        ("비소유자 상품 삭제", "DELETE", buyer["token"], f"/products/{item}", None, False, 403),
        ("비소유자 예약", "POST", buyer["token"], f"/products/{item}/reserve", {"buyer_no":buyer["member_no"]}, False, 403),
        ("비소유자 예약해제", "POST", buyer["token"], f"/products/{item}/unreserve", None, False, 403),
        ("비소유자 거래완료", "POST", buyer["token"], f"/products/{item}/complete", {"buyer_no":buyer["member_no"]}, False, 403),
        ("상품 없는 수정", "PUT", seller["token"], "/products/99999999", _valid_item(), True, 404),
        ("상품 없는 삭제", "DELETE", seller["token"], "/products/99999999", None, False, 404),
        ("상품 없는 예약", "POST", seller["token"], "/products/99999999/reserve", {"buyer_no":buyer["member_no"]}, False, 404),
        ("상품 없는 완료", "POST", seller["token"], "/products/99999999/complete", {"buyer_no":buyer["member_no"]}, False, 404),
    ]:
        _call(b, "상품 소유권", name, method, path, expected, token=token, data=data, form=form)

    # Validate response after denial: item must stay untouched.
    _call(b, "상품 트랜잭션", "권한 거부 후 상품명 보존", "GET", f"/products/{item}", 200,
          check=lambda d: d.get("seller_no") == seller["member_no"] and "탈취" not in d.get("title", ""))

    deleted = b.product(seller, "숨김상품")
    _call(b, "상품 삭제 상태", "정상 삭제", "DELETE", f"/products/{deleted}", 200, token=seller["token"])
    _call(b, "상품 삭제 상태", "삭제 상품 익명 상세 조회", "GET", f"/products/{deleted}", 404)
    _call(b, "상품 삭제 상태", "삭제 상품 일반회원 상세 조회", "GET", f"/products/{deleted}", 404, token=buyer["token"])
    _call(b, "상품 삭제 상태", "삭제 상품 소유자 조회", "GET", f"/products/{deleted}", 200, token=seller["token"])
    _call(b, "상품 삭제 상태", "삭제 상품 관리자 조회", "GET", f"/products/{deleted}", 200, token=root["token"])
    _call(b, "상품 삭제 상태", "삭제 상품 재삭제", "DELETE", f"/products/{deleted}", 409, token=seller["token"])
    _call(b, "상품 삭제 상태", "삭제 상품 채팅 금지", "POST", f"/products/{deleted}/chat", 409, token=buyer["token"])

    # Content must be verified, not just extension and mime. These are currently expected to reveal flaws.
    before_image_list = request("GET", "/products/mine", token=seller["token"])
    before_image_count = (len(before_image_list["body"]) if before_image_list["status"] == 200 and
                          isinstance(before_image_list["body"], list) else None)
    fake_images = [
        ("위조 PNG 헤더", "counterfeit.png", b"This is just a text file, not PNG", "image/png"),
        ("위조 GIF 헤더", "counterfeit.gif", b"not a valid GIF", "image/gif"),
        ("HTML을 JPEG로 위장", "counterfeit.jpg", b"<html><script>bad</script></html>", "image/jpeg"),
        ("ZIP을 WEBP로 위장", "counterfeit.webp", b"PK\\x03\\x04bad", "image/webp"),
        ("확장자는 JPG인데 MIME은 text/plain", "wrong.jpg", b"plain text not image", "text/plain"),
    ]
    for label, filename, payload, mime in fake_images:
        # Handcraft small harmless test bytes. API must reject these with 422.
        from run import request as multipart_request
        resp = multipart_request("POST", "/products", data=_valid_item("가짜이미지"), token=seller["token"],
                                 upload=("images", filename, payload, mime))
        b.check("이미지 내용 검증", label, resp, {413, 422})
    for label, filename in [("SVG 거부", "vector.svg"), ("확장자 이중위장", "hello.jpg.exe"), ("EXE 거부", "virus.exe"), ("PDF 거부", "report.pdf")]:
        from run import request as multipart_request
        resp = multipart_request("POST", "/products", data=_valid_item("거부확장자"), token=seller["token"],
                                 upload=("images", filename, b"not an image", "application/octet-stream"))
        b.check("이미지 확장자 검증", label, resp, 422)
    if before_image_count is not None:
        _call(b, "이미지 트랜잭션", "거부한 가짜 이미지 요청에서 상품 생성 금지", "GET", "/products/mine", 200,
              token=seller["token"], check=lambda d: isinstance(d, list) and len(d) == before_image_count)

    print("[EXT 4/8] Chatroom and message invariant checks")
    product = b.product(seller, "채팅불변식")
    room_b = _call(b, "채팅 불변식", "구매자1 채팅 생성", "POST", f"/products/{product}/chat", 200,
                   token=buyer["token"])
    room_c = _call(b, "채팅 불변식", "구매자2 채팅 생성", "POST", f"/products/{product}/chat", 200,
                   token=buyer2["token"])
    if room_b and room_c:
        room_no = room_b["room_no"]
        for length in (1, 2000):
            content = "한" * length
            resp = _call(b, "메시지 정상 경계", f"{length}자 메시지", "POST", f"/chats/{room_no}/messages", 201,
                         token=buyer["token"], data={"content": content})
            if resp:
                _call(b, "메시지 정상 경계", f"{length}자 메시지 보존 확인", "GET", f"/chats/{room_no}", 200,
                      token=buyer["token"], check=lambda d, c=content: any(x["content"] == c for x in d.get("messages", [])))
        for msg in ("", "x" * 2001, "한" * 2001):
            _call(b, "메시지 비정상 경계", f"내용 길이 {len(msg)}", "POST", f"/chats/{room_no}/messages", 422,
                  token=buyer["token"], data={"content":msg})
        for msg in ({}, {"content":None}, {"content":123}, {"content":True}):
            _call(b, "메시지 타입 검증", str(msg)[:60], "POST", f"/chats/{room_no}/messages", 422,
                  token=buyer["token"], data=msg)
        _call(b, "메시지 권한", "외부인 채팅방 조회", "GET", f"/chats/{room_no}", 404,
              token=outsider["token"])
        _call(b, "메시지 권한", "외부인 메시지 추가", "POST", f"/chats/{room_no}/messages", 404,
              token=outsider["token"], data={"content":"침입"})
        _call(b, "메시지 권한", "익명 채팅방 조회", "GET", f"/chats/{room_no}", 401)
        _call(b, "메시지 권한", "익명 메시지 추가", "POST", f"/chats/{room_no}/messages", 401,
              data={"content":"침입"})
        _call(b, "메시지 권한", "구매자가 타 구매자 채팅방 조회", "GET", f"/chats/{room_c['room_no']}", 404,
              token=buyer["token"])
        _call(b, "메시지 권한", "판매자 구매자 채팅 목록", "GET", f"/products/{product}/chats", 200,
              token=seller["token"], check=lambda d: isinstance(d, list) and len(d) >= 2)
        _call(b, "메시지 권한", "구매자 구매자 채팅 목록 금지", "GET", f"/products/{product}/chats", 403,
              token=buyer["token"])
        _call(b, "메시지 권한", "판매자 채팅방 상세 조회", "GET", f"/chats/{room_no}", 200,
              token=seller["token"])

    print("[EXT 5/8] Reports and admin process boundary tests")
    report_payload = _report("상품게시글", product)
    rep = _call(b, "신고 절차", "상품게시글 신고", "POST", "/reports", 201, token=buyer["token"], data=report_payload)
    _call(b, "신고 절차", "같은 내용 중복 신고", "POST", "/reports", 409, token=buyer["token"], data=report_payload)
    _call(b, "신고 절차", "같은 대상으로 다른 사유 중복 신고", "POST", "/reports", 409,
          token=buyer["token"], data={**report_payload, "reason_code": "사기의심"})
    for name, data in [
        ("신고 대상 누락", {"target_type":"회원", "reason_code":"기타", "content":"test"}),
        ("신고 타입 없음", {"target_no": seller["member_no"], "reason_code":"기타", "content":"test"}),
        ("신고 사유 없음", {"target_type":"회원", "target_no":seller["member_no"], "content":"test"}),
        ("신고 내용 없음", {"target_type":"회원", "target_no":seller["member_no"], "reason_code":"기타"}),
        ("신고 내용 빈 문자열", {**report_payload, "content":""}),
        ("신고 내용 초과", {**report_payload, "content":"가"*2001}),
        ("신고 대상 비정수", {**report_payload, "target_no":"not-an-int"}),
        ("신고 대상 null", {**report_payload, "target_no":None}),
        ("신고 유형 다른 값", {**report_payload, "target_type":"사업자"}),
        ("신고 사유 다른 값", {**report_payload, "reason_code":"무효사유"}),
    ]:
        _call(b, "신고 입력 검증", name, "POST", "/reports", 422, token=buyer2["token"], data=data)
    if rep:
        report_no = rep["report_no"]
        _call(b, "신고 절차", "신고 검토 시작", "POST", f"/admin/reports/{report_no}/review", 200, token=root["token"])
        _call(b, "신고 절차", "검토 중복 시작", "POST", f"/admin/reports/{report_no}/review", 409, token=root["token"])
        for result, reason in [("조치완료", ""), ("반려", ""), ("별도처리", "검증"), ("반려", "y"*501)]:
            _call(b, "신고 처리 검증", f"{result}/사유 길이{len(reason)}", "POST",
                  f"/admin/reports/{report_no}/process", 422, token=root["token"],
                  data={"result":result, "reason":reason})
        _call(b, "신고 절차", "신고 정상 반려", "POST", f"/admin/reports/{report_no}/process", 201,
              token=root["token"], data={"result":"반려", "reason":"근거 부족"})
        _call(b, "신고 절차", "반려 후 재처리 차단", "POST", f"/admin/reports/{report_no}/process", 409,
              token=root["token"], data={"result":"조치완료", "reason":"재시도"})
        _call(b, "신고 절차", "반려 후 신고 상태 확인", "GET", f"/admin/reports/{report_no}", 200,
              token=root["token"], check=lambda d: d.get("report_status") == "반려")

    other_target = b.signup("sanctiontarget")
    warn_path = f"/admin/members/{other_target['member_no']}/sanctions"
    for name, data in [
        ("제재유형 누락", {"reason":"사유"}),
        ("제재사유 누락", {"sanction_type":"경고"}),
        ("제재사유 빈문자", {"sanction_type":"경고", "reason":""}),
        ("제재사유 501자", {"sanction_type":"경고", "reason":"z"*501}),
        ("제재유형 비정상", {"sanction_type":"사형", "reason":"테스트"}),
        ("제재종료일시 invalid", {"sanction_type":"일시정지", "reason":"테스트", "end_at":"no-date"}),
        ("제재종료일시 과거", {"sanction_type":"일시정지", "reason":"테스트", "end_at":"1999-01-01T00:00:00"}),
    ]:
        _call(b, "제재 검증", name, "POST", warn_path, 422, token=root["token"], data=data)
    _call(b, "제재 검증", "존재하지 않는 회원", "POST", "/admin/members/99999999/sanctions", 404,
          token=root["token"], data={"sanction_type":"경고", "reason":"사유"})
    _call(b, "제재 검증", "관리자 자기 자신", "POST", f"/admin/members/{root['member_no']}/sanctions", 400,
          token=root["token"], data={"sanction_type":"경고", "reason":"사유"})
    _call(b, "제재 검증", "직원 root 제재 금지", "POST", f"/admin/members/{root['member_no']}/sanctions", 403,
          token=staff["token"], data={"sanction_type":"경고", "reason":"사유"})
    _call(b, "제재 검증", "정상 경고", "POST", warn_path, 201, token=root["token"],
          data={"sanction_type":"경고", "reason":"테스트 경고"})
    _call(b, "제재 검증", "경고 후 정상 상태 유지", "GET", f"/admin/members/{other_target['member_no']}", 200,
          token=root["token"], check=lambda d: d.get("account_status") == "정상")

    # Permission and DB trigger protections for member role mutation.
    _call(b, "역할 변경", "staff 다른 회원 역할 변경 금지", "PATCH", f"/admin/members/{buyer['member_no']}/role", 403,
          token=staff["token"], data={"role":"moderator"})
    _call(b, "역할 변경", "root 타인에게 root 역할 부여 금지", "PATCH", f"/admin/members/{buyer['member_no']}/role", 422,
          token=root["token"], data={"role":"root"})
    _call(b, "역할 변경", "root 자신의 역할 변경 금지", "PATCH", f"/admin/members/{root['member_no']}/role", 409,
          token=root["token"], data={"role":"user"})
    _call(b, "역할 변경", "없는 역할 입력", "PATCH", f"/admin/members/{buyer['member_no']}/role", 422,
          token=root["token"], data={"role":"superuser"})

    print("[EXT 6/8] SQL injection, URL/Unicode edge cases (read-only where possible)")
    injections = ["' OR 1=1 --", "\" OR 1=1 --", "admin'/*", "' UNION SELECT NULL --", "\\' OR 'x'='x", "'; DROP TABLE product; --"]
    for inj in injections:
        path = "/products?" + urllib.parse.urlencode({"q": inj})
        _call(b, "SQL 파라미터화", f"상품 검색 {inj[:30]}", "GET", path, 200,
              check=lambda d: isinstance(d, list))
        path = "/admin/members?" + urllib.parse.urlencode({"q": inj})
        _call(b, "SQL 파라미터화", f"관리자 회원 검색 {inj[:30]}", "GET", path, 200,
              token=root["token"], check=lambda d: isinstance(d, list))
        _call(b, "SQL 파라미터화", f"닉네임 인젝션 {inj[:30]}", "POST", "/auth/login", 401,
              data={"nickname":inj, "password":"whatever"})
    special_queries = ["%", "_", "\\", "  ", "한글", "🍓", "e\u0301", "\u202e", "\ud55c", "☃", "😈"]
    for i, text in enumerate(special_queries):
        path = "/products?" + urllib.parse.urlencode({"q": text})
        _call(b, "다국어·검색", f"특수 검색 #{i} {text!r}", "GET", path, 200,
              check=lambda d: isinstance(d, list))

    print("[EXT 7/8] Concurrent operations on disposable rows")
    jobs = max(2, min(b.concurrency, 12))
    def race(group, label, fn, allowed, *, exact_successes=None, expected_id=None):
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(fn, range(jobs)))
        for i, resp in enumerate(results):
            b.check(group, f"{label} worker={i}", resp, allowed)
        if exact_successes is not None:
            _record_check(b, group, f"{label} 정확히 {exact_successes}회 성공", sum(x["status"] in (200, 201) for x in results) == exact_successes,
                          {"statuses":[x["status"] for x in results]})
        if expected_id is not None:
            ids = [x["body"].get("room_no") for x in results if x["status"] == 200 and isinstance(x["body"], dict)]
            _record_check(b, group, f"{label} 채팅방 ID 동일", len(ids) == jobs and set(ids) == {expected_id}, {"room_ids":ids})
        return results

    # Race: two buyers reserve same listing concurrently; exactly one may own reservation.
    rp = b.product(seller, "동시예약대결")
    _call(b, "경쟁 준비", "구매자1 채팅 개설", "POST", f"/products/{rp}/chat", 200, token=buyer["token"])
    _call(b, "경쟁 준비", "구매자2 채팅 개설", "POST", f"/products/{rp}/chat", 200, token=buyer2["token"])
    order = [buyer["member_no"] if j % 2 == 0 else buyer2["member_no"] for j in range(jobs)]
    race("동시 예약", "다수 구매자의 단일 예약", lambda i: request("POST", f"/products/{rp}/reserve",
         data={"buyer_no":order[i]}, token=seller["token"]), {200, 409}, exact_successes=1)
    _call(b, "동시 예약", "예약상태가 유효한 구매자", "GET", f"/products/{rp}", 200,
          check=lambda d: d.get("trade_status") == "예약중" and d.get("reserver_no") in order)

    cp = b.product(seller, "동시거래완료")
    _call(b, "경쟁 준비", "구매자 채팅 개설(완료)", "POST", f"/products/{cp}/chat", 200,
          token=buyer["token"])
    race("동시 완료", "동일 상품 완료", lambda i: request("POST", f"/products/{cp}/complete",
         data={"buyer_no":buyer["member_no"]}, token=seller["token"]), {200, 409}, exact_successes=1)
    _call(b, "동시 완료", "완료 결과 저장", "GET", f"/products/{cp}", 200,
          check=lambda d: d.get("trade_status") == "판매완료" and d.get("buyer_no") == buyer["member_no"])

    # Same report in parallel, uniqueness enforced by composite generated key in schema.
    reptarget = b.signup("racereporttarget")
    identical = _report("회원", reptarget["member_no"], "동시 중복 신고")
    race("동시 신고", "신고 유일성", lambda i: request("POST", "/reports", data=identical,
         token=buyer2["token"]), {201, 409}, exact_successes=1)

    # Same member suspension concurrently; should serialize via member row FOR UPDATE.
    sanction_target = b.signup("racesanctiontarget")
    suspend_until = (datetime.now() + timedelta(days=3)).isoformat(timespec="seconds")
    sanction_path = f"/admin/members/{sanction_target['member_no']}/sanctions"
    race("동시 제재", "일시정지 단일성", lambda i: request("POST", sanction_path, token=root["token"],
         data={"sanction_type":"일시정지", "reason":"동시성 검증", "end_at":suspend_until}),
         {201, 409}, exact_successes=1)
    _call(b, "동시 제재", "제재 후 이용정지 상태", "GET", f"/admin/members/{sanction_target['member_no']}", 200,
          token=root["token"], check=lambda d: d.get("account_status") == "이용정지")

    # Repeat completed/chat concurrency for several rounds. Keep bounded (not a DoS).
    for k in range(5):
        xp = b.product(seller, f"동시채팅확장{k}")
        race("동시 채팅 추가", f"경합 #{k}", lambda _: request("POST", f"/products/{xp}/chat", token=buyer2["token"]),
             200)
        _call(b, "동시 채팅 추가", f"경합 #{k} DB에 방 하나만", "GET", f"/products/{xp}/chats", 200,
              token=seller["token"],
              check=lambda d: isinstance(d, list) and len([r for r in d if r.get("buyer_no") == buyer2["member_no"]]) == 1)

    print("[EXT 8/8] Seeded fuzzing for edge conditions")
    # Deliberately bounded fuzz: small bodies, no network targets, no S3, no file bombs.
    fuzz_quota = b.random_cases
    fuzz_categories = ["signup", "product", "message", "report", "sanction", "login", "path", "query"]
    scratch_room = room_b["room_no"] if room_b else None
    for i in range(fuzz_quota):
        category = fuzz_categories[i % len(fuzz_categories)]
        if category == "signup":
            identity = b.identity("genbad")
            field = rng.choice(["name", "nickname", "phone", "email", "password", "address"])
            if field == "name": identity[field] = "x" * rng.randint(51, 520)
            elif field == "nickname": identity[field] = "z" * rng.randint(31, 320)
            elif field == "password": identity[field] = "q" * rng.randint(101, 520)
            elif field == "address": identity[field] = "a" * rng.randint(201, 520)
            elif field == "phone": identity[field] = rng.choice(["010-abc-1234", "", "+82-100-000-0000", "010 1234 5678"])
            elif field == "email": identity[field] = rng.choice(["bad", "@foo.com", "x@", "x@ .com", "x"*110+"@x.test"])
            _call(b, "생성형 퍼징 회원", f"#{i:04d} {field}", "POST", "/auth/signup", 422, data=identity)
        elif category == "product":
            field = rng.choice(["title", "price", "item_condition"])
            data = _valid_item()
            if field == "title": data[field] = "x" * rng.randint(101, 520)
            elif field == "price": data[field] = rng.choice([str(-rng.randint(1, 10**9)), str(4294967296 + rng.randint(1, 10**9)), "nan", "12.3"])
            else: data[field] = rng.choice(["", "INVALID", "중고", "하자", "NEW"])
            _call(b, "생성형 퍼징 상품", f"#{i:04d} {field}", "POST", "/products", 422, token=seller["token"], data=data, form=True)
        elif category == "message" and scratch_room:
            content = rng.choice(["", "m"*rng.randint(2001, 2500)])
            _call(b, "생성형 퍼징 채팅", f"#{i:04d} 길이 {len(content)}", "POST", f"/chats/{scratch_room}/messages", 422,
                  token=buyer["token"], data={"content":content})
        elif category == "report":
            invalid = rng.choice(["INVALID", "사유없음", "0", "spam"])
            _call(b, "생성형 퍼징 신고", f"#{i:04d} 사유 {invalid}", "POST", "/reports", 422, token=buyer["token"],
                  data={**_report("회원", seller["member_no"]), "reason_code":invalid})
        elif category == "sanction":
            v = rng.choice(["INVALID", "정지", "관리자권한해제", "-", "평생"])
            _call(b, "생성형 퍼징 제재", f"#{i:04d} 유형 {v}", "POST", warn_path, 422, token=root["token"],
                  data={"sanction_type": v, "reason":"격리 검증"})
        elif category == "login":
            username = "definitely_not_real_" + "".join(rng.choices(string.ascii_lowercase, k=16))
            _call(b, "생성형 퍼징 로그인", f"#{i:04d}", "POST", "/auth/login", 401,
                  data={"nickname": username, "password": "Q"*rng.randint(1, 150)})
        elif category == "path":
            endpoint = rng.choice(["products", "members"])
            path_id = rng.choice(["-1", "0", str(rng.randint(10**12, 10**16))])
            _call(b, "생성형 퍼징 경로", f"#{i:04d} {endpoint}/{path_id}", "GET", f"/{endpoint}/{path_id}", 404)
        elif category == "query":
            q = "".join(rng.choices(string.ascii_letters + string.digits + " '%_/-한", k=rng.randint(1, 100)))
            path = "/products?" + urllib.parse.urlencode({"q":q})
            _call(b, "생성형 퍼징 검색", f"#{i:04d}", "GET", path, 200, check=lambda d: isinstance(d, list))

    # End-to-end health after all malformed, concurrent and randomized requests.
    _call(b, "서비스 생존성", "퍼징 이후 health", "GET", "/health", 200,
          check=lambda d: d.get("ok") is True)
    _call(b, "서비스 생존성", "퍼징 이후 상품 조회", "GET", "/products", 200,
          check=lambda d: isinstance(d, list))
    _call(b, "서비스 생존성", "퍼징 이후 관리자 조회", "GET", "/admin/members", 200,
          token=root["token"], check=lambda d: isinstance(d, list))
