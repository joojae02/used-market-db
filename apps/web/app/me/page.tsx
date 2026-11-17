"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, dt, setSession, won } from "@/lib/api";
import { act, useLoad } from "@/lib/hooks";

type Me = { member_no: number; role: string; name: string; nickname: string; phone: string; email: string; birth_date: string | null; address: string | null; joined_at: string; account_status: string };
type Row = Record<string, any>;

export default function MePage() {
  const router = useRouter();
  const { data: me, error } = useLoad<Me>("/me");
  const { data: products } = useLoad<Row[]>("/products/mine");
  const { data: purchases } = useLoad<Row[]>("/products/purchased");
  const { data: reports } = useLoad<Row[]>("/reports/mine");
  const { data: logins } = useLoad<Row[]>("/me/logins");

  if (error) return <p className="error">{error}</p>;
  if (!me) return null;

  return (
    <>
      <h2>내 정보</h2>
      <table>
        <tbody>
          <tr><th>회원번호</th><td>{me.member_no}</td><th>권한</th><td>{me.role}</td></tr>
          <tr><th>성명</th><td>{me.name}</td><th>닉네임</th><td>{me.nickname}</td></tr>
          <tr><th>전화번호</th><td>{me.phone}</td><th>이메일</th><td>{me.email}</td></tr>
          <tr><th>생년월일</th><td>{me.birth_date ?? "-"}</td><th>주소</th><td>{me.address ?? "-"}</td></tr>
          <tr><th>가입일시</th><td>{dt(me.joined_at)}</td><th>계정상태</th><td>{me.account_status}</td></tr>
        </tbody>
      </table>

      <h3>판매 상품</h3>
      <table>
        <thead><tr><th>상품</th><th>가격</th><th>거래상태</th><th>게시글</th><th>등록</th></tr></thead>
        <tbody>
          {products?.map((p) => (
            <tr key={p.product_no}>
              <td><Link href={`/products/${p.product_no}`}>{p.title}</Link></td>
              <td>{won(p.price)}</td><td>{p.trade_status}</td><td>{p.post_status}</td><td>{dt(p.registered_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>구매 내역</h3>
      <table>
        <thead><tr><th>상품</th><th>가격</th><th>판매자</th><th>완료일시</th></tr></thead>
        <tbody>
          {purchases?.map((p) => (
            <tr key={p.product_no}>
              <td><Link href={`/products/${p.product_no}`}>{p.title}</Link></td>
              <td>{won(p.price)}</td><td>{p.seller_nickname}</td><td>{dt(p.completed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>내 신고</h3>
      <table>
        <thead><tr><th>번호</th><th>대상</th><th>사유</th><th>상태</th><th>일시</th></tr></thead>
        <tbody>
          {reports?.map((r) => (
            <tr key={r.report_no}>
              <td>{r.report_no}</td><td>{r.target_type} #{r.target_no}</td><td>{r.reason_code}</td>
              <td>{r.report_status}</td><td>{dt(r.reported_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>최근 로그인</h3>
      <table>
        <thead><tr><th>일시</th><th>IP</th><th>결과</th><th>기기</th></tr></thead>
        <tbody>
          {logins?.map((l, i) => (
            <tr key={i}>
              <td>{dt(l.login_at)}</td><td>{l.ip_address}</td><td>{l.login_result ? "성공" : "실패"}</td>
              <td className="muted">{l.device_info?.slice(0, 60)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <button
        onClick={() =>
          confirm("정말 탈퇴할까요?") &&
          act(() => api("/me/withdraw", { method: "POST" }), () => {
            setSession(null);
            router.push("/");
          })
        }
      >
        회원 탈퇴
      </button>
    </>
  );
}
