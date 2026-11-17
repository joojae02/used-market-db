"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import PriceTag from "@/components/PriceTag";
import ReportButton from "@/components/ReportButton";
import Status from "@/components/Status";
import { dt } from "@/lib/api";
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
      <h1>{m.nickname}</h1>
      <p className="muted">
        {dt(m.joined_at).slice(0, 10)} 가입 {m.account_status !== "정상" && <Status value={m.account_status} />}
      </p>
      {session && session.member.member_no !== m.member_no && <ReportButton targetType="회원" targetNo={m.member_no} />}
      <h3>판매 물건 {m.products.length}개</h3>
      <div className="table-wrap">
        <table>
          <tbody>
            {m.products.map((p) => (
              <tr key={p.product_no}>
                <td><Link href={`/products/${p.product_no}`}>{p.title}</Link></td>
                <td><PriceTag price={p.price} /></td>
                <td><Status value={p.trade_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
