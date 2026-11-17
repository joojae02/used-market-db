# 중고거래 플랫폼 데모 (데이터베이스응용 3조)

기능 위주 데모. 디자인은 최소한.

<img width="1440" height="675" alt="중고마켓 화면" src="https://github.com/user-attachments/assets/9cf178b5-e26b-4d8d-8843-de85c03c2af3" />

```
apps/
  api/   FastAPI + PyMySQL (ORM 없이 SQL 직접 작성)
  web/   Next.js (App Router, 전부 클라이언트 컴포넌트)
db/
  schema.sql   물리 설계 DDL (MySQL 8, 트리거·CHECK 포함)
docs/
  문서-불일치-정리.md   산출물 간 불일치, 미구현 항목, 코드의 임시 해석
```

## 실행 튜토리얼

처음 받은 사람이 로컬에서 화면을 띄우기까지의 순서다. 명령어는 모두 레포 최상위 폴더에서 실행한다.

### 1. 준비물 설치

| 도구 | 버전 | 확인 명령 | 설치 |
| --- | --- | --- | --- |
| Node.js | 22 이상 | `node -v` | [nodejs.org](https://nodejs.org) |
| pnpm | 10 이상 | `pnpm -v` | `npm install -g pnpm` |
| uv (Python 관리) | 최신 | `uv --version` | [설치 안내](https://docs.astral.sh/uv/getting-started/installation/) |
| MySQL 8 **또는** Docker | MySQL 8.0.16 이상 | `mysql --version` / `docker -v` | [MySQL](https://dev.mysql.com/downloads/mysql/) / [Docker Desktop](https://www.docker.com/products/docker-desktop/) |

Python은 따로 설치하지 않아도 된다. uv가 필요한 버전(3.12)을 알아서 받는다.
macOS라면 `brew install node pnpm uv mysql` 한 줄로 끝난다.

### 2. 코드 받기와 의존성 설치

```bash
git clone https://github.com/joojae02/used-market-db.git
cd used-market-db
pnpm install
```

### 3. 접속 정보 설정 (root 비밀번호가 있을 때만)

MySQL root 비밀번호가 비어 있거나 Docker를 쓴다면 이 단계는 건너뛴다. 비밀번호가 있거나 포트가 3306이 아니면, 예시 파일을 복사해 값을 고친다.

```bash
cp apps/api/.env.example apps/api/.env
```

```ini
# apps/api/.env
DB_PASSWORD=내_root_비밀번호
DB_PORT=3306
```

`.env`는 git에 올라가지 않는다. API 서버와 다음 단계의 비밀번호 설정 스크립트가 이 파일을 읽는다.

### 4. 데이터베이스 준비

둘 중 하나를 고른다.

**방법 A. 내 컴퓨터의 MySQL을 쓰는 경우**

```bash
# MySQL 서버 켜기 (macOS brew 기준. Windows는 설치 시 서비스로 자동 실행됨)
brew services start mysql

# 테이블 생성 → 샘플 데이터 → 샘플 계정 비밀번호를 1234로 설정
pnpm db:init
```

`Enter password:`가 두 번 나온다. MySQL root 비밀번호를 입력하고, 비밀번호가 없으면 그냥 Enter를 누른다.

**방법 B. Docker를 쓰는 경우**

```bash
# MySQL 컨테이너 실행. 처음 뜰 때 db/schema.sql이 자동으로 들어간다 (30초 정도 걸림)
docker compose up -d

# 샘플 데이터 넣기 + 비밀번호 설정
docker compose exec -T mysql mysql -uroot used_market < db/sample_data.sql
pnpm db:passwords
```

컨테이너 안에서 직접 SQL을 칠 때는 한글이 깨지지 않게 문자셋을 지정한다.

```bash
docker compose exec mysql mysql -uroot --default-character-set=utf8mb4 used_market
```

### 5. 서버 실행

터미널을 두 개 열고 각각 실행한다.

```bash
# 터미널 1: API 서버
pnpm dev:api
```

```bash
# 터미널 2: 웹
pnpm dev:web
```

| 주소 | 내용 |
| --- | --- |
| http://localhost:3000 | 웹 화면 |
| http://localhost:8000/docs | API 문서 (요청을 직접 보내볼 수 있음) |

### 6. 동작 확인

1. http://localhost:3000 에 들어가면 상품 5개가 보인다.
2. 오른쪽 위 **로그인**에서 `판매왕` / `1234`로 로그인한다.
3. 아이패드 상품을 열면 "채팅한 구매자" 목록에서 예약자 지정과 거래 완료를 할 수 있다.
4. `운영자` / `1234`로 로그인하면 상단에 **운영 관리** 메뉴가 생긴다.

### 샘플 계정

`db/sample_data.sql`에 들어 있는 계정이다. 비밀번호는 `pnpm db:passwords`가 모두 `1234`로 맞춘다.

| 닉네임 | 권한 | 상태 |
| --- | --- | --- |
| 슈퍼루트 | root | 권한 변경을 포함한 모든 관리 |
| 운영자 | staff | 신고·제재·게시글 조치 |
| 판매왕 | user | 상품 1(판매중), 2(예약중) 판매 |
| 구매왕 | user | 상품 1·2 판매자와 채팅 중 |
| 학생이 | user | 상품 3(판매완료), 4 판매 |
| 사용자5 | user | 일시정지 (2026-11-17 종료) |
| 탈퇴회원 | user | 탈퇴, 로그인 불가 |

`pnpm db:seed`는 샘플 데이터 대신 쓸 수 있는 최소 시드(root, mod, seller, buyer, buyer2)를 넣는다. 둘 중 하나만 쓴다.

### 처음부터 다시 하고 싶을 때

`pnpm db:init`을 다시 실행하면 테이블을 지우고 샘플 데이터 상태로 돌아간다. Docker라면 `docker compose down -v` 후 4단계부터 다시 한다.

### 자주 막히는 문제

| 증상 | 원인과 해결 |
| --- | --- |
| `Can't connect to MySQL server on '127.0.0.1'` | MySQL이 꺼져 있다. 4단계의 서버 켜기 명령이나 `docker compose up -d`를 실행한다 |
| `Access denied for user 'root'` | root 비밀번호가 있다. 3단계대로 `apps/api/.env`에 `DB_PASSWORD`를 넣는다 |
| 로그인하면 "닉네임 또는 패스워드가 일치하지 않습니다" | 샘플 데이터의 비밀번호는 예시 문자열이다. `pnpm db:passwords`를 실행한다 |
| 로그인하면 "5회 실패로 … 제한됩니다" | 10분을 기다리거나 `pnpm db:init`으로 초기화한다 |
| 화면에 "Failed to fetch" 또는 아무 상품도 안 보임 | API 서버(터미널 1)가 꺼져 있다 |
| `EADDRINUSE` / `address already in use` | 3000이나 8000 포트를 다른 프로그램이 쓰고 있다. 그 프로그램을 끈다 |
| `docker compose up` 에서 `port is already allocated` | 내 컴퓨터의 MySQL이 3306을 쓰고 있다. 로컬 MySQL을 끄거나 방법 A를 쓴다 |
| 상품 사진이 "사진 없음"으로 나옴 | 정상이다. 샘플 데이터의 이미지 경로에 실제 파일이 없다. 새로 등록한 상품의 사진은 보인다 |

## 단위업무 ↔ 구현

번호는 업무기능도 기준. 업무기술서 제목·업무흐름도는 번호가 다르다 (`docs/문서-불일치-정리.md` 1-1).

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

문서가 정하지 않은 규칙은 `docs/문서-불일치-정리.md` 7장의 임시 해석을 따르고, 아직 구현하지 않은 항목은 6장에 있다.
