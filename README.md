# 중고거래 플랫폼 데모 (데이터베이스응용 3조)

기능 위주 데모. 디자인은 최소한.

```
apps/
  api/   FastAPI + PyMySQL (ORM 없이 SQL 직접 작성)
  web/   Next.js (App Router, 전부 클라이언트 컴포넌트)
db/
  schema.sql   물리 설계 DDL (MySQL 8, 트리거·CHECK 포함)
docs/
  문서-불일치-정리.md   업무기술서·흐름도·ERD·DDL 간 차이
```

## 실행

준비물: Node 22+, pnpm, [uv](https://docs.astral.sh/uv/), MySQL 8 (로컬 또는 `docker compose up -d`)

```bash
pnpm install

# DB 생성 + 데모 데이터 (로컬 MySQL)
pnpm db:init
# docker 를 쓰면 스키마는 자동 실행되므로 시드만
pnpm db:seed

# 터미널 두 개에서
pnpm dev:api   # http://localhost:8000  (API 문서: /docs)
pnpm dev:web   # http://localhost:3000
```

DB 접속 정보가 기본값(root, 비밀번호 없음, 3306)과 다르면 환경변수로 넘긴다. `apps/api/.env.example` 참고.

```bash
DB_PASSWORD=secret pnpm dev:api
```

데모 계정 (비밀번호 모두 `1234`)

| 닉네임 | 권한 | 용도 |
| --- | --- | --- |
| root | root | 권한 변경 포함 모든 관리 |
| mod | moderator | 신고·제재·게시글 조치 |
| seller | user | 상품 2개 등록됨 |
| buyer | user | seller 상품에 채팅 중 |
| buyer2 | user | 상품 신고 1건 |

## 단위업무 ↔ 구현

번호는 업무기능도 기준. 업무기술서 제목·업무흐름도는 번호가 다르다 (`docs/문서-불일치-정리.md` 0-1).

| 업무 (기능도) | 기술서 | API | 화면 |
| --- | --- | --- | --- |
| MEM-01 회원가입/탈퇴 | MEM-01 | `GET /auth/check`, `POST /auth/signup`, `POST /me/withdraw` | `/signup`, `/me` |
| MEM-02 로그인 | MEM-02 | `POST /auth/login` (5회 실패 10분 잠금, 로그인 이력) | `/login`, `/me` |
| PRD-01~02 상품 등록/수정/삭제 | PRD-01~02 | `POST·PUT·DELETE /products` | `/products/new`, `/products/[id]` |
| PRD-04 거래 상태 변경 | PRD-03 | 아래 예약·완료 API가 상태를 바꿈 | 상품 상세 |
| TRD-01~02 채팅 | TRD-01~02 | `POST /products/{no}/chat`, `/chats/*` | `/chats` (3초 폴링) |
| TRD-04 예약자 지정/해제 | TRD-03 | `POST /products/{no}/reserve·unreserve` | 상품 상세(판매자) |
| TRD-05 거래 완료 | TRD-04 | `POST /products/{no}/complete` | 상품 상세(판매자) |
| TRS-03 신고 | TRS-01 | `POST /reports`, `GET /reports/mine` | 상품 상세, 회원 페이지, `/me` |
| ADM-01 회원 관리/제재 | ADM-01 | `/admin/members/*`, `/admin/sanctions/*` | `/admin` → 회원 |
| ADM-02 게시글 관리 | ADM-02 | `/admin/products/{no}/actions` | `/admin` → 게시글 |
| ADM-03 신고 처리 | ADM-03 | `/admin/reports/*` | `/admin` → 신고 |
| (문서 없음) 권한 관리 | — | `PATCH /admin/members/{no}/role` (root만) | 관리자 회원 상세 |

문서가 정하지 않은 규칙은 `docs/문서-불일치-정리.md` 7절의 임시 해석을 따른다.
