-- =====================================================================
-- 샘플 데이터 (schema.sql 실행 후 실행)
-- =====================================================================
SET NAMES utf8mb4;   -- 클라이언트 문자셋 고정 (한글 깨짐 방지)
USE used_market;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE product_action;
TRUNCATE TABLE member_sanction;
TRUNCATE TABLE report_process;
TRUNCATE TABLE report;
TRUNCATE TABLE chat_message;
TRUNCATE TABLE chat_room;
TRUNCATE TABLE product_image;
TRUNCATE TABLE product;
TRUNCATE TABLE login_history;
TRUNCATE TABLE member;
SET FOREIGN_KEY_CHECKS = 1;

-- 회원 (1: 운영자(staff), 2~5: 일반회원, 6: 탈퇴회원, 7: 루트 — 루트는 1개만 존재) ※ 비밀번호 해시는 예시 문자열
INSERT INTO member (member_no, role, name, nickname, phone, birth_date, address, email, password_hash,
                    joined_at, account_status, login_fail_count, login_locked_until, withdrawn_at) VALUES
(1, 'staff', '김운영', '운영자',   '010-1000-0001', '1990-01-15', '서울 동작구', 'admin@market.test', '$2b$10$sampleHash0000000000000000000000000000000000000001', '2026-09-01 09:00:00', '정상',     0, NULL, NULL),
(2, 'user',  '이판매', '판매왕',   '010-2000-0002', '1998-03-02', '서울 동작구', 'seller@market.test', '$2b$10$sampleHash0000000000000000000000000000000000000002', '2026-09-05 10:00:00', '정상',     0, NULL, NULL),
(3, 'user',  '박구매', '구매왕',   '010-3000-0003', '1999-07-21', '서울 관악구', 'buyer@market.test',  '$2b$10$sampleHash0000000000000000000000000000000000000003', '2026-09-06 11:30:00', '정상',     0, NULL, NULL),
(4, 'user',  '최학생', '학생이',   '010-4000-0004', '2001-11-09', '서울 동작구', 'student@market.test','$2b$10$sampleHash0000000000000000000000000000000000000004', '2026-09-10 14:20:00', '정상',     1, NULL, NULL),
(5, 'user',  '정사용', '사용자5',  '010-5000-0005', '1995-05-30', '경기 성남시', 'user5@market.test',  '$2b$10$sampleHash0000000000000000000000000000000000000005', '2026-09-12 16:40:00', '이용정지', 0, NULL, NULL),
(6, 'user',  '한탈퇴', '탈퇴회원', '010-6000-0006', '1993-12-25', '서울 마포구', 'gone@market.test',   '$2b$10$sampleHash0000000000000000000000000000000000000006', '2026-09-15 08:10:00', '탈퇴',     0, NULL, '2026-10-20 18:00:00'),
(7, 'root',  '루트',   '슈퍼루트', '010-0000-0000', '1990-01-01', '서울 동작구', 'root@market.test',    '$2b$10$sampleHash0000000000000000000000000000000000000007', '2026-09-01 00:00:00', '정상',     0, NULL, NULL);

-- 로그인 이력
INSERT INTO login_history (member_no, login_at, ip_address, device_info, login_result) VALUES
(1, '2026-11-01 09:01:00', '203.0.113.10', 'Chrome / macOS', 1),
(2, '2026-11-01 10:15:00', '203.0.113.21', 'Safari / iPhone', 1),
(3, '2026-11-02 11:00:00', '203.0.113.32', 'Chrome / Windows', 1),
(4, '2026-11-02 14:00:00', '203.0.113.43', 'Chrome / Android', 0),
(4, '2026-11-02 14:01:00', '203.0.113.43', 'Chrome / Android', 1),
(5, '2026-11-03 16:00:00', '203.0.113.54', 'Edge / Windows', 1);

-- 상품 (1:판매중, 2:예약중, 3:판매완료, 4:판매중, 5:블라인드, 6:삭제)
INSERT INTO product (product_no, seller_no, reserver_no, buyer_no, title, description, price, item_condition,
                     trade_area, price_offer_yn, trade_status, trade_status_at, completed_at, post_status,
                     registered_at, updated_at, deleted_at) VALUES
(1, 2, NULL, NULL, '아이패드 에어 5세대 64GB', '1년 사용, 케이스 포함, 생활 흠집 약간 있습니다.', 520000, '사용감있음', '서울 동작구 숭실대입구역', 1, '판매중',   '2026-11-01 10:30:00', NULL,                  '정상',     '2026-11-01 10:30:00', NULL, NULL),
(2, 2, 3,    NULL, '데이터베이스 개론 전공책', '필기 없음, 깨끗합니다.', 15000, '거의새것', '서울 동작구 숭실대 정문', 0, '예약중',   '2026-11-02 13:00:00', NULL,                  '정상',     '2026-10-28 09:00:00', NULL, NULL),
(3, 4, NULL, 3,    '접이식 자전거', '타이어 교체 완료. 직거래만 가능합니다.', 90000, '사용감있음', '서울 관악구 서울대입구역', 1, '판매완료', '2026-10-30 18:00:00', '2026-10-30 18:00:00', '정상',     '2026-10-25 12:00:00', NULL, NULL),
(4, 4, NULL, NULL, '게이밍 마우스', '박스 풀구성, 사용 3개월.', 25000, '거의새것', '서울 동작구', 0, '판매중',   '2026-11-02 15:00:00', NULL,                  '정상',     '2026-11-02 15:00:00', NULL, NULL),
(5, 5, NULL, NULL, '정품 명품 가방 (급처)', '시세보다 매우 저렴. 계좌이체 선입금만 받습니다.', 50000, '새상품', '전국 택배', 0, '판매중',   '2026-11-02 20:00:00', NULL,                  '블라인드', '2026-11-02 20:00:00', NULL, NULL),
(7, 6, NULL, NULL, '탈퇴 회원이 올린 노트북 거치대', '탈퇴 후에도 게시글이 보존되는 예시입니다.', 12000, '거의새것', '서울 마포구', 0, '판매중',   '2026-10-01 10:00:00', NULL,                  '정상',     '2026-10-01 10:00:00', NULL, NULL),
(6, 2, NULL, NULL, '캠핑 의자 (삭제됨)', '판매자가 삭제한 글입니다.', 10000, '사용감있음', '서울 동작구', 0, '판매중',   '2026-10-27 10:00:00', NULL,                  '삭제',     '2026-10-27 10:00:00', '2026-10-27 11:00:00', '2026-10-27 11:00:00');

-- 상품 이미지 (image_order 0 = 대표 이미지)
INSERT INTO product_image (product_no, image_path, image_order) VALUES
(1, '/images/product/1/0.jpg', 0),
(1, '/images/product/1/1.jpg', 1),
(2, '/images/product/2/0.jpg', 0),
(3, '/images/product/3/0.jpg', 0),
(4, '/images/product/4/0.jpg', 0),
(4, '/images/product/4/1.jpg', 1),
(5, '/images/product/5/0.jpg', 0);

-- 채팅방
INSERT INTO chat_room (room_no, product_no, seller_no, buyer_no, room_status, created_at) VALUES
(1, 1, 2, 3, '활성',   '2026-11-01 12:00:00'),
(2, 2, 2, 3, '활성',   '2026-11-02 12:30:00'),
(3, 3, 4, 3, '비활성', '2026-10-27 09:00:00'),
(4, 1, 2, 4, '활성',   '2026-11-02 18:00:00');

-- 채팅 메시지 (read_at IS NULL = 안읽음)
INSERT INTO chat_message (room_no, sender_no, content, sent_at, read_at) VALUES
(1, 3, '안녕하세요, 아이패드 아직 있나요?',            '2026-11-01 12:01:00', '2026-11-01 12:05:00'),
(1, 2, '네 있습니다. 직거래 가능하세요?',             '2026-11-01 12:06:00', '2026-11-01 12:07:00'),
(1, 3, '49만원에 가능할까요?',                         '2026-11-01 12:08:00', NULL),
(2, 3, '전공책 예약하고 싶어요.',                      '2026-11-02 12:31:00', '2026-11-02 12:40:00'),
(2, 2, '좋아요. 내일 정문에서 뵐게요.',                '2026-11-02 12:41:00', '2026-11-02 12:50:00'),
(3, 3, '자전거 구매하겠습니다.',                       '2026-10-27 09:01:00', '2026-10-27 09:10:00'),
(3, 4, '네, 토요일 6시에 만나요.',                     '2026-10-27 09:11:00', '2026-10-27 09:12:00'),
(4, 4, '아이패드 상태 사진 더 보여주실 수 있나요?',    '2026-11-02 18:01:00', NULL);

-- 신고 (1: 상품5 → 처리완료, 2: 회원5 → 처리완료, 3: 상품4 → 접수)
INSERT INTO report (report_no, reporter_no, target_type, target_member_no, target_product_no, reason_code,
                    content, report_status, reported_at) VALUES
(1, 3, '상품게시글', NULL, 5, '사기의심',  '선입금만 요구하는 의심스러운 게시글입니다.', '처리완료', '2026-11-03 09:00:00'),
(2, 4, '회원',       5,    NULL, '사기의심', '채팅에서 계좌이체를 강요했습니다.',         '처리완료', '2026-11-03 09:30:00'),
(3, 3, '상품게시글', NULL, 4, '기타',       '가격이 시세와 달라 보입니다.',               '접수',     '2026-11-04 10:00:00');

-- 신고 처리 이력
INSERT INTO report_process (report_no, admin_no, result, reason, processed_at) VALUES
(1, 1, '조치완료', '선입금 유도 게시글로 판단하여 블라인드 처리', '2026-11-03 10:00:00'),
(2, 1, '조치완료', '사기 시도로 판단하여 일시정지 제재',         '2026-11-03 10:30:00');

-- 회원 제재
INSERT INTO member_sanction (member_no, admin_no, report_no, sanction_type, reason, sanctioned_at, start_at, end_at) VALUES
(5, 1, 2, '일시정지', '사기 시도(선입금 강요)', '2026-11-03 10:30:00', '2026-11-03 10:30:00', '2026-11-17 10:30:00');

-- 상품 게시글 관리 이력
INSERT INTO product_action (product_no, admin_no, report_no, action_type, reason, action_at) VALUES
(5, 1, 1, '블라인드', '신고 접수 후 검토: 선입금 유도', '2026-11-03 10:00:00');
