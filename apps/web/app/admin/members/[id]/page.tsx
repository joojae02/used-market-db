"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import SanctionForm from "@/components/SanctionForm";
import { api, dt, won } from "@/lib/api";
import { act, useLoad, useSession } from "@/lib/hooks";

type Row = Record<string, any>;

export default function AdminMemberPage() {
  const { id } = useParams<{ id: string }>();
  const session = useSession();
  const { data: m, error, reload } = useLoad<Row>(`/admin/members/${id}`);
  if (error) return <p className="error">{error}</p>;
  if (!m) return null;

  const release = (no: number) => {
    const reason = prompt("해제 사유");
    if (reason) act(() => api(`/admin/sanctions/${no}/release`, { method: "POST", body: { reason } }), reload);
  };

  return (
    <>
      <h2>회원 #{m.member_no} {m.nickname}</h2>
      <table>
        <tbody>
          <tr><th>성명</th><td>{m.name}</td><th>권한</th><td>{m.role}</td></tr>
          <tr><th>이메일</th><td>{m.email}</td><th>전화번호</th><td>{m.phone}</td></tr>
          <tr><th>가입</th><td>{dt(m.joined_at)}</td><th>계정상태</th><td>{m.account_status} {m.withdrawn_at && `(탈퇴 ${dt(m.withdrawn_at)})`}</td></tr>
          <tr><th>로그인 실패</th><td>{m.login_fail_count}회</td><th>로그인 제한</th><td>{dt(m.login_locked_until)}</td></tr>
        </tbody>
      </table>

      {session?.member.role === "root" && m.role !== "root" && (
        <div className="row">
          권한 변경:
          {["user", "moderator", "staff"].map((r) => (
            <button key={r} disabled={m.role === r} onClick={() => act(() => api(`/admin/members/${id}/role`, { method: "PATCH", body: { role: r } }), reload)}>
              {r}
            </button>
          ))}
        </div>
      )}

      <h3>제재 이력</h3>
      <table>
        <thead><tr><th>번호</th><th>유형</th><th>사유</th><th>관리자</th><th>기간</th><th>신고</th><th>해제</th></tr></thead>
        <tbody>
          {m.sanctions.map((s: Row) => (
            <tr key={s.sanction_no}>
              <td>{s.sanction_no}</td><td>{s.sanction_type}</td><td>{s.reason}</td><td>{s.admin_nickname}</td>
              <td>{dt(s.start_at)} ~ {s.end_at ? dt(s.end_at) : s.sanction_type === "영구정지" ? "무기한" : "-"}</td>
              <td>{s.report_no ? <Link href={`/admin/reports/${s.report_no}`}>#{s.report_no}</Link> : "-"}</td>
              <td>
                {s.released_at ? `${dt(s.released_at)} ${s.release_admin_nickname}: ${s.release_reason}` : s.sanction_type !== "경고" && <button onClick={() => release(s.sanction_no)}>해제</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {m.role !== "root" && m.account_status !== "탈퇴" && <SanctionForm memberNo={m.member_no} onDone={reload} />}

      <h3>받은 신고</h3>
      <ul>
        {m.reports_received.map((r: Row) => (
          <li key={r.report_no}>
            <Link href={`/admin/reports/${r.report_no}`}>#{r.report_no}</Link> {r.reason_code} [{r.report_status}] {dt(r.reported_at)}
          </li>
        ))}
      </ul>

      <h3>등록 상품</h3>
      <ul>
        {m.products.map((p: Row) => (
          <li key={p.product_no}>
            <Link href={`/products/${p.product_no}`}>{p.title}</Link> [{p.trade_status} / {p.post_status}] {dt(p.registered_at)}
          </li>
        ))}
      </ul>

      <h3>구매 내역</h3>
      <ul>
        {m.purchases.map((p: Row) => (
          <li key={p.product_no}>
            <Link href={`/products/${p.product_no}`}>{p.title}</Link> {won(p.price)} {dt(p.completed_at)}
          </li>
        ))}
      </ul>
    </>
  );
}
