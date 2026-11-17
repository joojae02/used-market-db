-- =====================================================================
-- 중고거래 플랫폼 물리 설계 DDL (MySQL 8.0.16+, InnoDB, utf8mb4)
-- 기준: 개념 모델(ERD) 10개 테이블 / 업무 기능도 (MEM, PRD, TRD, TRS-03, ADM)
-- 실행: mysql -u root -p < schema.sql   (또는 Workbench에서 전체 실행)
-- =====================================================================

SET NAMES utf8mb4;   -- 클라이언트 문자셋 고정 (한글 깨짐 방지)
CREATE DATABASE IF NOT EXISTS used_market
  DEFAULT CHARACTER SET utf8mb4;
USE used_market;

-- 재실행을 위해 의존 역순으로 삭제
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS product_action;
DROP TABLE IF EXISTS member_sanction;
DROP TABLE IF EXISTS report_process;
DROP TABLE IF EXISTS report;
DROP TABLE IF EXISTS chat_message;
DROP TABLE IF EXISTS chat_room;
DROP TABLE IF EXISTS product_image;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS login_history;
DROP TABLE IF EXISTS member;
DROP FUNCTION IF EXISTS fn_is_admin;   -- 함수는 테이블 삭제로 지워지지 않으므로 따로 삭제
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 1. member : 회원 (MEM-01, MEM-02)
-- ---------------------------------------------------------------------
CREATE TABLE member (
  member_no           BIGINT        NOT NULL AUTO_INCREMENT COMMENT '회원번호',
  role                ENUM('user','moderator','staff','root')
                                    NOT NULL DEFAULT 'user'   COMMENT '권한역할',
  name                VARCHAR(50)   NOT NULL                  COMMENT '성명',
  nickname            VARCHAR(30)   NOT NULL                  COMMENT '닉네임',
  phone               VARCHAR(20)   NOT NULL                  COMMENT '전화번호',
  birth_date          DATE          NULL                      COMMENT '생년월일',
  address             VARCHAR(200)  NULL                      COMMENT '집주소',
  email               VARCHAR(100)  NOT NULL                  COMMENT '이메일주소',
  password_hash       VARCHAR(255)  NOT NULL                  COMMENT '패스워드해시',
  joined_at           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '가입일시',
  account_status      ENUM('정상','이용정지','탈퇴')
                                    NOT NULL DEFAULT '정상'   COMMENT '계정상태',
  login_fail_count    INT UNSIGNED  NOT NULL DEFAULT 0        COMMENT '연속로그인실패횟수',
  login_locked_until  DATETIME      NULL                      COMMENT '로그인제한만료일시',
  withdrawn_at        DATETIME      NULL                      COMMENT '탈퇴일시',
  -- [정책 P-05] 루트 계정은 1개만 존재: role='root' 인 행만 1 을 갖고, 나머지는 NULL (UNIQUE 는 NULL 중복 허용)
  root_flag           TINYINT GENERATED ALWAYS AS (IF(role = 'root', 1, NULL)) STORED
                                                              COMMENT '루트유일성보장용(자동)',
  PRIMARY KEY (member_no),
  UNIQUE KEY uk_member_nickname (nickname),
  UNIQUE KEY uk_member_phone (phone),
  UNIQUE KEY uk_member_email (email),
  UNIQUE KEY uk_member_single_root (root_flag),
  -- [정책 P-01, P-02] 탈퇴는 상태 컬럼으로 관리. 재가입 시 같은 행을 '정상'으로 되돌리고 탈퇴일시를 비운다.
  CONSTRAINT chk_member_withdrawn
    CHECK ((account_status = '탈퇴') = (withdrawn_at IS NOT NULL)),
  -- [정책 P-06] 루트는 탈퇴/이용정지 상태가 될 수 없다.
  CONSTRAINT chk_member_root_active
    CHECK (role <> 'root' OR account_status = '정상')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='회원';

-- [정책 P-06, P-08] 루트 계정 보호 트리거
-- ※ DELIMITER 를 바꿔서 실행합니다. (mysql CLI / Workbench 모두 지원)
DELIMITER //

-- 루트 삭제 금지
CREATE TRIGGER trg_member_root_no_delete
BEFORE DELETE ON member FOR EACH ROW
BEGIN
  IF OLD.role = 'root' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '루트 계정은 삭제할 수 없습니다.';
  END IF;
END//

-- 루트의 권한 변경 금지, 루트 권한을 다른 회원에게 부여하는 것 금지
CREATE TRIGGER trg_member_root_no_role_change
BEFORE UPDATE ON member FOR EACH ROW
BEGIN
  IF OLD.role = 'root' AND NEW.role <> 'root' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '루트 계정의 권한은 변경할 수 없습니다.';
  END IF;
  IF OLD.role <> 'root' AND NEW.role = 'root' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '루트 권한은 다른 회원에게 부여할 수 없습니다.';
  END IF;
END//

DELIMITER ;

-- ---------------------------------------------------------------------
-- 2. login_history : 로그인 이력 (MEM-02)
-- ---------------------------------------------------------------------
CREATE TABLE login_history (
  login_no      BIGINT        NOT NULL AUTO_INCREMENT COMMENT '로그인이력번호',
  member_no     BIGINT        NOT NULL                COMMENT '회원번호',
  login_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '로그인일시',
  ip_address    VARCHAR(45)   NOT NULL                COMMENT '접속IP (IPv6 최대 45자)',
  device_info   VARCHAR(255)  NULL                    COMMENT '기기정보',
  login_result  TINYINT(1)    NOT NULL                COMMENT '로그인결과(0:실패, 1:성공)',
  PRIMARY KEY (login_no),
  KEY idx_login_member_time (member_no, login_at),
  CONSTRAINT fk_login_member FOREIGN KEY (member_no) REFERENCES member (member_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='로그인 이력';

-- ---------------------------------------------------------------------
-- 3. product : 상품 (PRD-01, PRD-02, PRD-04)
-- ---------------------------------------------------------------------
CREATE TABLE product (
  product_no        BIGINT        NOT NULL AUTO_INCREMENT COMMENT '상품번호',
  seller_no         BIGINT        NOT NULL                COMMENT '판매자회원번호',
  reserver_no       BIGINT        NULL                    COMMENT '예약자회원번호',
  buyer_no          BIGINT        NULL                    COMMENT '구매자회원번호',
  title             VARCHAR(100)  NOT NULL                COMMENT '상품명',
  description       TEXT          NOT NULL                COMMENT '상품설명',
  price             INT UNSIGNED  NOT NULL                COMMENT '판매가격(원)',
  item_condition    ENUM('새상품','거의새것','사용감있음','하자있음')
                                  NOT NULL                COMMENT '물품상태',
  trade_area        VARCHAR(100)  NULL                    COMMENT '거래희망지역',
  price_offer_yn    TINYINT(1)    NOT NULL DEFAULT 0      COMMENT '가격제안허용여부(0:불가, 1:허용)',
  trade_status      ENUM('판매중','예약중','판매완료')
                                  NOT NULL DEFAULT '판매중' COMMENT '거래상태',
  trade_status_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '거래상태변경일시',
  completed_at      DATETIME      NULL                    COMMENT '거래완료일시',
  post_status       ENUM('정상','블라인드','삭제')
                                  NOT NULL DEFAULT '정상'   COMMENT '게시글상태',
  registered_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일시',
  updated_at        DATETIME      NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
  deleted_at        DATETIME      NULL                    COMMENT '삭제일시',
  PRIMARY KEY (product_no),
  KEY idx_product_list (post_status, trade_status, registered_at),
  KEY idx_product_seller (seller_no, registered_at),
  KEY idx_product_reserver (reserver_no),
  KEY idx_product_buyer (buyer_no),
  CONSTRAINT fk_product_seller   FOREIGN KEY (seller_no)   REFERENCES member (member_no),
  CONSTRAINT fk_product_reserver FOREIGN KEY (reserver_no) REFERENCES member (member_no),
  CONSTRAINT fk_product_buyer    FOREIGN KEY (buyer_no)    REFERENCES member (member_no),
  CONSTRAINT chk_product_price CHECK (price >= 0),
  CONSTRAINT chk_product_not_self CHECK (
        (reserver_no IS NULL OR reserver_no <> seller_no)
    AND (buyer_no    IS NULL OR buyer_no    <> seller_no)),
  CONSTRAINT chk_product_reserved CHECK (trade_status <> '예약중' OR reserver_no IS NOT NULL),
  CONSTRAINT chk_product_completed CHECK (
        trade_status <> '판매완료' OR (buyer_no IS NOT NULL AND completed_at IS NOT NULL)),
  CONSTRAINT chk_product_deleted CHECK ((post_status = '삭제') = (deleted_at IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상품';

-- ---------------------------------------------------------------------
-- 4. product_image : 상품 이미지 (PRD-01)
-- ---------------------------------------------------------------------
CREATE TABLE product_image (
  image_no     BIGINT        NOT NULL AUTO_INCREMENT COMMENT '이미지번호',
  product_no   BIGINT        NOT NULL                COMMENT '상품번호',
  image_path   VARCHAR(500)  NOT NULL                COMMENT '이미지경로',
  image_order  INT UNSIGNED  NOT NULL DEFAULT 0      COMMENT '이미지순서(0이 대표)',
  PRIMARY KEY (image_no),
  UNIQUE KEY uk_image_order (product_no, image_order),
  CONSTRAINT fk_image_product FOREIGN KEY (product_no) REFERENCES product (product_no)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상품 이미지';

-- ---------------------------------------------------------------------
-- 5. chat_room : 채팅방 (TRD-01)  ※후순위
-- ---------------------------------------------------------------------
CREATE TABLE chat_room (
  room_no      BIGINT   NOT NULL AUTO_INCREMENT COMMENT '채팅방번호',
  product_no   BIGINT   NOT NULL                COMMENT '상품번호',
  seller_no    BIGINT   NOT NULL                COMMENT '판매자회원번호',
  buyer_no     BIGINT   NOT NULL                COMMENT '구매자회원번호',
  room_status  ENUM('활성','비활성')
                        NOT NULL DEFAULT '활성'   COMMENT '채팅방상태',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
  PRIMARY KEY (room_no),
  UNIQUE KEY uk_room_product_buyer (product_no, buyer_no),   -- 중복 개설 방지
  KEY idx_room_seller (seller_no),
  KEY idx_room_buyer (buyer_no),
  CONSTRAINT fk_room_product FOREIGN KEY (product_no) REFERENCES product (product_no),
  CONSTRAINT fk_room_seller  FOREIGN KEY (seller_no)  REFERENCES member (member_no),
  CONSTRAINT fk_room_buyer   FOREIGN KEY (buyer_no)   REFERENCES member (member_no),
  CONSTRAINT chk_room_not_self CHECK (seller_no <> buyer_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='채팅방';

-- ---------------------------------------------------------------------
-- 6. chat_message : 채팅 메시지 (TRD-02)  ※후순위
--    읽음 여부는 read_at IS NULL 로 판단 (read_yn 컬럼 제거)
-- ---------------------------------------------------------------------
CREATE TABLE chat_message (
  message_no  BIGINT    NOT NULL AUTO_INCREMENT COMMENT '메시지번호',
  room_no     BIGINT    NOT NULL                COMMENT '채팅방번호',
  sender_no   BIGINT    NOT NULL                COMMENT '발신자회원번호',
  content     TEXT      NOT NULL                COMMENT '메시지내용',
  sent_at     DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '전송일시',
  read_at     DATETIME  NULL                    COMMENT '읽은일시(NULL이면 안읽음)',
  PRIMARY KEY (message_no),
  KEY idx_message_room_time (room_no, sent_at),
  KEY idx_message_sender (sender_no),
  CONSTRAINT fk_message_room   FOREIGN KEY (room_no)   REFERENCES chat_room (room_no),
  CONSTRAINT fk_message_sender FOREIGN KEY (sender_no) REFERENCES member (member_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='채팅 메시지';

-- ---------------------------------------------------------------------
-- 7. report : 신고 (TRS-03)
--    신고 대상은 회원 또는 상품 게시글 중 하나만 (CHECK)
--    target_key 는 중복 신고 방지용 생성 컬럼 (NULL 은 UNIQUE 에서 중복이 허용되므로)
-- ---------------------------------------------------------------------
CREATE TABLE report (
  report_no          BIGINT    NOT NULL AUTO_INCREMENT COMMENT '신고번호',
  reporter_no        BIGINT    NOT NULL                COMMENT '신고자회원번호',
  target_type        ENUM('상품게시글','회원')
                               NOT NULL                COMMENT '신고대상유형',
  target_member_no   BIGINT    NULL                    COMMENT '피신고회원번호',
  target_product_no  BIGINT    NULL                    COMMENT '신고상품번호',
  reason_code        ENUM('스팸/광고','사기의심','욕설/비방','부적절한게시물','기타')
                               NOT NULL                COMMENT '신고사유',
  content            TEXT      NULL                    COMMENT '신고내용',
  report_status      ENUM('접수','검토중','처리완료','반려')
                               NOT NULL DEFAULT '접수'  COMMENT '신고상태',
  reported_at        DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '신고일시',
  target_key         BIGINT GENERATED ALWAYS AS (COALESCE(target_member_no, target_product_no)) STORED
                               COMMENT '중복신고방지용(대상번호)',
  PRIMARY KEY (report_no),
  UNIQUE KEY uk_report_once (reporter_no, target_type, target_key),
  KEY idx_report_status (report_status, reported_at),
  KEY idx_report_target_member (target_member_no),
  KEY idx_report_target_product (target_product_no),
  CONSTRAINT fk_report_reporter FOREIGN KEY (reporter_no)       REFERENCES member (member_no),
  CONSTRAINT fk_report_member   FOREIGN KEY (target_member_no)  REFERENCES member (member_no),
  CONSTRAINT fk_report_product  FOREIGN KEY (target_product_no) REFERENCES product (product_no),
  CONSTRAINT chk_report_target CHECK (
       (target_type = '회원'      AND target_member_no  IS NOT NULL AND target_product_no IS NULL)
    OR (target_type = '상품게시글' AND target_product_no IS NOT NULL AND target_member_no  IS NULL)),
  CONSTRAINT chk_report_not_self CHECK (target_member_no IS NULL OR target_member_no <> reporter_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='신고';

-- ---------------------------------------------------------------------
-- 8. report_process : 신고 처리 이력 (ADM-03)  -- 신고 1건 : 처리 이력 N건
-- ---------------------------------------------------------------------
CREATE TABLE report_process (
  process_no    BIGINT        NOT NULL AUTO_INCREMENT COMMENT '신고처리번호',
  report_no     BIGINT        NOT NULL                COMMENT '신고번호',
  admin_no      BIGINT        NOT NULL                COMMENT '처리관리자회원번호',
  result        ENUM('조치완료','조치없음','반려')
                              NOT NULL                COMMENT '처리결과',
  reason        VARCHAR(500)  NOT NULL                COMMENT '처리사유',
  processed_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '처리일시',
  PRIMARY KEY (process_no),
  KEY idx_process_report (report_no, processed_at),
  KEY idx_process_admin (admin_no),
  CONSTRAINT fk_process_report FOREIGN KEY (report_no) REFERENCES report (report_no),
  CONSTRAINT fk_process_admin  FOREIGN KEY (admin_no)  REFERENCES member (member_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='신고 처리 이력';

-- ---------------------------------------------------------------------
-- 9. member_sanction : 회원 제재 (ADM-01)
-- ---------------------------------------------------------------------
CREATE TABLE member_sanction (
  sanction_no       BIGINT        NOT NULL AUTO_INCREMENT COMMENT '제재번호',
  member_no         BIGINT        NOT NULL                COMMENT '대상회원번호',
  admin_no          BIGINT        NOT NULL                COMMENT '제재관리자회원번호',
  report_no         BIGINT        NULL                    COMMENT '관련신고번호',
  sanction_type     ENUM('경고','일시정지','영구정지')
                                  NOT NULL                COMMENT '제재유형',
  reason            VARCHAR(500)  NOT NULL                COMMENT '제재사유',
  sanctioned_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '제재일시',
  start_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '제재시작일시',
  end_at            DATETIME      NULL                    COMMENT '제재종료예정일시',
  released_at       DATETIME      NULL                    COMMENT '해제일시',
  release_admin_no  BIGINT        NULL                    COMMENT '해제관리자회원번호',
  release_reason    VARCHAR(500)  NULL                    COMMENT '해제사유',
  PRIMARY KEY (sanction_no),
  KEY idx_sanction_member (member_no, start_at),
  KEY idx_sanction_admin (admin_no),
  KEY idx_sanction_report (report_no),
  KEY idx_sanction_release_admin (release_admin_no),
  CONSTRAINT fk_sanction_member FOREIGN KEY (member_no)        REFERENCES member (member_no),
  CONSTRAINT fk_sanction_admin  FOREIGN KEY (admin_no)         REFERENCES member (member_no),
  CONSTRAINT fk_sanction_report FOREIGN KEY (report_no)        REFERENCES report (report_no),
  CONSTRAINT fk_sanction_release_admin FOREIGN KEY (release_admin_no) REFERENCES member (member_no),
  CONSTRAINT chk_sanction_period CHECK (end_at IS NULL OR end_at >= start_at),
  CONSTRAINT chk_sanction_temp   CHECK (sanction_type <> '일시정지' OR end_at IS NOT NULL),
  CONSTRAINT chk_sanction_release CHECK ((released_at IS NULL) = (release_admin_no IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='회원 제재';

-- (제재 관련 트리거는 파일 맨 아래 '권한 검증' 구역에 있습니다)

-- ---------------------------------------------------------------------
-- 10. product_action : 상품 게시글 관리 이력 (ADM-02)
-- ---------------------------------------------------------------------
CREATE TABLE product_action (
  action_no    BIGINT        NOT NULL AUTO_INCREMENT COMMENT '관리이력번호',
  product_no   BIGINT        NOT NULL                COMMENT '상품번호',
  admin_no     BIGINT        NOT NULL                COMMENT '조치관리자회원번호',
  report_no    BIGINT        NULL                    COMMENT '관련신고번호',
  action_type  ENUM('블라인드','삭제','블라인드해제')
                             NOT NULL                COMMENT '조치유형',
  reason       VARCHAR(500)  NOT NULL                COMMENT '조치사유',
  action_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '조치일시',
  PRIMARY KEY (action_no),
  KEY idx_action_product (product_no, action_at),
  KEY idx_action_admin (admin_no),
  KEY idx_action_report (report_no),
  CONSTRAINT fk_action_product FOREIGN KEY (product_no) REFERENCES product (product_no),
  CONSTRAINT fk_action_admin   FOREIGN KEY (admin_no)   REFERENCES member (member_no),
  CONSTRAINT fk_action_report  FOREIGN KEY (report_no)  REFERENCES report (report_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상품 게시글 관리 이력';

-- =====================================================================
-- 권한 검증 (DB 단에서 막을 수 있는 범위)
--  · DB 는 "누가 요청했는지"를 알 수 없으므로, 기록에 남는 사람(admin_no, sender_no 등)이
--    그 행동을 할 자격이 있는지를 검사한다.
--  · 관리자급 = 모더레이터 / 어드민(staff) / 루트 이면서 계정 상태가 '정상'
--    (모더레이터와 어드민의 기능 구분은 팀 미결정이라 아직 나누지 않음)
-- =====================================================================
DELIMITER //

CREATE FUNCTION fn_is_admin(p_member_no BIGINT) RETURNS TINYINT
DETERMINISTIC READS SQL DATA
BEGIN
  RETURN EXISTS (SELECT 1 FROM member
                  WHERE member_no = p_member_no
                    AND role IN ('moderator', 'staff', 'root')
                    AND account_status = '정상');
END//

-- 신고 처리자는 관리자급이어야 한다
CREATE TRIGGER trg_report_process_admin
BEFORE INSERT ON report_process FOR EACH ROW
BEGIN
  IF fn_is_admin(NEW.admin_no) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '관리자 권한이 없는 회원은 신고를 처리할 수 없습니다.';
  END IF;
END//

-- 게시글 조치자는 관리자급이어야 한다
CREATE TRIGGER trg_product_action_admin
BEFORE INSERT ON product_action FOR EACH ROW
BEGIN
  IF fn_is_admin(NEW.admin_no) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '관리자 권한이 없는 회원은 게시글을 조치할 수 없습니다.';
  END IF;
END//

-- 제재: 제재자는 관리자급, 대상은 루트가 아니어야 한다 [정책 P-08]
CREATE TRIGGER trg_sanction_insert
BEFORE INSERT ON member_sanction FOR EACH ROW
BEGIN
  IF fn_is_admin(NEW.admin_no) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '관리자 권한이 없는 회원은 제재할 수 없습니다.';
  END IF;
  IF (SELECT role FROM member WHERE member_no = NEW.member_no) = 'root' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '루트 계정은 제재할 수 없습니다.';
  END IF;
END//

-- 제재 해제자도 관리자급이어야 한다
CREATE TRIGGER trg_sanction_release
BEFORE UPDATE ON member_sanction FOR EACH ROW
BEGIN
  IF NEW.release_admin_no IS NOT NULL AND NOT (NEW.release_admin_no <=> OLD.release_admin_no)
     AND fn_is_admin(NEW.release_admin_no) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '관리자 권한이 없는 회원은 제재를 해제할 수 없습니다.';
  END IF;
END//

-- 채팅방의 판매자는 해당 상품의 판매자여야 한다
CREATE TRIGGER trg_chat_room_seller
BEFORE INSERT ON chat_room FOR EACH ROW
BEGIN
  IF NEW.seller_no <> (SELECT seller_no FROM product WHERE product_no = NEW.product_no) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '채팅방의 판매자는 상품의 판매자와 같아야 합니다.';
  END IF;
END//

-- 메시지 발신자는 그 채팅방의 판매자 또는 구매자여야 한다
CREATE TRIGGER trg_chat_message_sender
BEFORE INSERT ON chat_message FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1 FROM chat_room
                  WHERE room_no = NEW.room_no
                    AND NEW.sender_no IN (seller_no, buyer_no)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '채팅방 참여자만 메시지를 보낼 수 있습니다.';
  END IF;
END//

DELIMITER ;
