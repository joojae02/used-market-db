"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import SanctionForm from "@/components/SanctionForm";
import { api, dt } from "@/lib/api";
import { act, useLoad } from "@/lib/hooks";

type Row = Record<string, any>;

export default function AdminReportPage() {
  const { id } = useParams<{ id: string }>();
  const { data: r, error, reload } = useLoad<Row>(`/admin/reports/${id}`);
  if (error) return <p className="error">{error}</p>;
  if (!r) return null;

  const done = r.report_status === "처리완료" || r.report_status === "반려";
  const productAction = (action_type: string) => {
    const reason = prompt(`${action_type} 사유`);
    if (reason)
      act(() => api(`/admin/products/${r.target_product_no}/actions`, { method: "POST", body: { action_type, reason, report_no: r.report_no } }), reload);
  };

  return (
    <>
      <div className="page-head">
        <h1>
          신고 {r.report_no}번 <span className="status" data-s={r.report_status}>{r.report_status}</span>
        </h1>
      </div>
      <table>
        <tbody>
          <tr><th>신고자</th><td><Link href={`/admin/members/${r.reporter_no}`}>{r.reporter_nickname}</Link></td></tr>
          <tr>
            <th>대상</th>
            <td>
              {r.target_type === "회원" ? (
                <Link href={`/admin/members/${r.target_member_no}`}>회원 {r.target_member_nickname} (#{r.target_member_no})</Link>
              ) : (
                <>
                  <Link href={`/products/${r.target_product_no}`}>{r.target_product_title} (#{r.target_product_no})</Link> 게시글 상태: {r.target_post_status}
                </>
              )}
            </td>
          </tr>
          <tr><th>사유</th><td>{r.reason_code}</td></tr>
          <tr><th>내용</th><td style={{ whiteSpace: "pre-wrap" }}>{r.content}</td></tr>
          <tr><th>신고일시</th><td>{dt(r.reported_at)}</td></tr>
        </tbody>
      </table>

      {r.report_status === "접수" && (
        <button onClick={() => act(() => api(`/admin/reports/${id}/review`, { method: "POST" }), reload)}>검토 시작</button>
      )}

      {r.report_status === "검토중" && (
        <>
          <h3>조치 (ADM-01 / ADM-02 연계)</h3>
          {r.target_type === "상품게시글" ? (
            <div className="row">
              {r.target_post_status === "정상" && <button onClick={() => productAction("블라인드")}>게시글 블라인드</button>}
              {r.target_post_status !== "삭제" && <button onClick={() => productAction("삭제")}>게시글 삭제</button>}
              <SanctionForm memberNo={r.target_product_seller} reportNo={r.report_no} onDone={reload} />
            </div>
          ) : (
            <SanctionForm memberNo={r.target_member_no} reportNo={r.report_no} onDone={reload} />
          )}
        </>
      )}

      {!done && (
        <form
          className="box"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            act(() => api(`/admin/reports/${id}/process`, { method: "POST", body: Object.fromEntries(f) }), reload);
          }}
        >
          <b>처리 결과 기록</b>
          <select name="result">
            <option>조치완료</option>
            <option>조치없음</option>
            <option>반려</option>
          </select>
          <textarea name="reason" placeholder="처리 사유" required />
          <button>처리 완료</button>
        </form>
      )}

      <h3>처리 이력</h3>
      <ul>
        {r.processes.map((p: Row) => (
          <li key={p.process_no}>{dt(p.processed_at)} {p.admin_nickname}: {p.result} — {p.reason}</li>
        ))}
      </ul>

      <h3>같은 대상의 다른 신고</h3>
      <ul>
        {r.related.map((x: Row) => (
          <li key={x.report_no}>
            <Link href={`/admin/reports/${x.report_no}`}>#{x.report_no}</Link> {x.reason_code} [{x.report_status}] {dt(x.reported_at)}
          </li>
        ))}
      </ul>
    </>
  );
}
