"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import ReportButton from "@/components/ReportButton";
import { dt, won } from "@/lib/api";
import { useLoad, useSession } from "@/lib/hooks";

type Profile = {
  member_no: number;
  nickname: string;
  joined_at: string;
  account_status: string;
  products: { product_no: number; title: string; price: number; trade_status: string }[];
};

export default function MemberPage() {
  const { id } = useParams<{ id: string }>();
  const session = useSession();
  const { data: m, error } = useLoad<Profile>(`/members/${id}`);
  if (error) return <p className="error">{error}</p>;
  if (!m) return null;
  return (
    <>
      <h2>{m.nickname}</h2>
      <p className="muted">가입 {dt(m.joined_at)} · {m.account_status}</p>
      {session && session.member.member_no !== m.member_no && <ReportButton targetType="회원" targetNo={m.member_no} />}
      <h3>판매 상품</h3>
      <ul>
        {m.products.map((p) => (
          <li key={p.product_no}>
            <Link href={`/products/${p.product_no}`}>{p.title}</Link> {won(p.price)} [{p.trade_status}]
          </li>
        ))}
      </ul>
    </>
  );
}
