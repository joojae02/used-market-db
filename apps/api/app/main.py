import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .routers import admin, chats, members, products, reports
from .routers.products import UPLOAD_DIR

app = FastAPI(title="중고거래 플랫폼 데모 API")

# 입력 검증 실패(422)를 화면에 그대로 띄울 수 있는 한국어 문장으로 바꾼다
FIELD_LABELS = {
    "name": "성명", "nickname": "닉네임", "phone": "전화번호", "birth_date": "생년월일",
    "address": "집주소", "email": "이메일", "password": "패스워드", "content": "내용",
    "reason": "사유", "reason_code": "신고 사유", "end_at": "종료예정일시", "buyer_no": "구매자",
    "title": "상품명", "description": "상품설명", "price": "판매가격", "item_condition": "물품상태",
}
FIELD_HINTS = {
    "phone": "전화번호 형식이 올바르지 않습니다. 예: 010-1234-5678",
    "email": "이메일 형식이 올바르지 않습니다. 예: name@example.com",
}


def _validation_message(err: dict) -> str:
    field = str(err["loc"][-1]) if err.get("loc") else ""
    label = FIELD_LABELS.get(field, field)
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    if kind == "missing":
        return f"{label}을(를) 입력하세요."
    if kind == "string_pattern_mismatch" and field in FIELD_HINTS:
        return FIELD_HINTS[field]
    if kind == "string_too_short":
        return f"{label}은(는) {ctx.get('min_length')}자 이상이어야 합니다."
    if kind == "string_too_long":
        return f"{label}은(는) {ctx.get('max_length')}자 이하여야 합니다."
    return f"{label} 값이 올바르지 않습니다."


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    messages = list(dict.fromkeys(_validation_message(e) for e in exc.errors()))
    return JSONResponse(status_code=422, content={"detail": "\n".join(messages)})

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (members, products, chats, reports, admin):
    app.include_router(r.router)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/health")
def health():
    return {"ok": True}
