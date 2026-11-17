"use client";

import Link from "next/link";
import { useState } from "react";
import { api, dt, won } from "@/lib/api";
import { act, useLoad } from "@/lib/hooks";

type Row = Record<string, any>;
const TABS = ["회원", "게시글", "신고"] as const;

export default function AdminPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("신고");
  return (
    <>
      <h2>관리자</h2>
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>
      {tab === "회원" && <Members />}
      {tab === "게시글" && <Products />}
      {tab === "신고" && <Reports />}
    </>
  );
}

function SearchBar({ statuses, onSearch }: { statuses: string[]; onSearch: (q: string, s: string) => void }) {
  return (
    <form
      className="row"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        onSearch(String(f.get("q") ?? ""), String(f.get("s") ?? ""));
      }}
    >
      <input name="q" placeholder="검색어 / 번호" />
      <select name="s">
        <option value="">전체</option>
        {statuses.map((s) => <option key={s}>{s}</option>)}
      </select>
      <button>검색</button>
    </form>
  );
}

function Members() {
  const [query, setQuery] = useState("/admin/members");
  const { data, error } = useLoad<Row[]>(query);
  return (
    <>
      <SearchBar statuses={["정상", "이용정지", "탈퇴"]} onSearch={(q, s) => setQuery(`/admin/members?${new URLSearchParams({ q, status: s })}`)} />
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>번호</th><th>닉네임</th><th>성명</th><th>이메일</th><th>권한</th><th>상태</th><th>가입</th></tr></thead>
        <tbody>
          {data?.map((m) => (
            <tr key={m.member_no}>
              <td>{m.member_no}</td>
              <td><Link href={`/admin/members/${m.member_no}`}>{m.nickname}</Link></td>
              <td>{m.name}</td><td>{m.email}</td><td>{m.role}</td><td>{m.account_status}</td><td>{dt(m.joined_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Products() {
  const [query, setQuery] = useState("/admin/products");
  const { data, error, reload } = useLoad<Row[]>(query);
  const action = (no: number, action_type: string) => {
    const reason = prompt(`${action_type} 사유`);
    if (reason) act(() => api(`/admin/products/${no}/actions`, { method: "POST", body: { action_type, reason } }), reload);
  };
  return (
    <>
      <SearchBar statuses={["정상", "블라인드", "삭제"]} onSearch={(q, s) => setQuery(`/admin/products?${new URLSearchParams({ q, post_status: s })}`)} />
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>번호</th><th>상품</th><th>판매자</th><th>가격</th><th>거래</th><th>게시글</th><th>신고</th><th>조치</th></tr></thead>
        <tbody>
          {data?.map((p) => (
            <tr key={p.product_no}>
              <td>{p.product_no}</td>
              <td><Link href={`/products/${p.product_no}`}>{p.title}</Link></td>
              <td><Link href={`/admin/members/${p.seller_no}`}>{p.seller_nickname}</Link></td>
              <td>{won(p.price)}</td><td>{p.trade_status}</td><td>{p.post_status}</td><td>{p.report_count}</td>
              <td className="row">
                {p.post_status === "정상" && <button onClick={() => action(p.product_no, "블라인드")}>블라인드</button>}
                {p.post_status === "블라인드" && <button onClick={() => action(p.product_no, "블라인드해제")}>해제</button>}
                {p.post_status !== "삭제" && <button onClick={() => action(p.product_no, "삭제")}>삭제</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Reports() {
  const [query, setQuery] = useState("/admin/reports");
  const { data, error } = useLoad<Row[]>(query);
  return (
    <>
      <SearchBar statuses={["접수", "검토중", "처리완료", "반려"]} onSearch={(_, s) => setQuery(`/admin/reports?${new URLSearchParams({ status: s })}`)} />
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>번호</th><th>대상</th><th>사유</th><th>신고자</th><th>상태</th><th>일시</th></tr></thead>
        <tbody>
          {data?.map((r) => (
            <tr key={r.report_no}>
              <td><Link href={`/admin/reports/${r.report_no}`}>#{r.report_no}</Link></td>
              <td>{r.target_type} #{r.target_member_no ?? r.target_product_no}</td>
              <td>{r.reason_code}</td><td>{r.reporter_nickname}</td><td>{r.report_status}</td><td>{dt(r.reported_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
