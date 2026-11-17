"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import ProductImage from "@/components/ProductImage";
import ReportButton from "@/components/ReportButton";
import { api, dt, won } from "@/lib/api";
import { act, useLoad, useSession } from "@/lib/hooks";

type Product = {
  product_no: number;
  seller_no: number;
  seller_nickname: string;
  reserver_nickname: string | null;
  buyer_nickname: string | null;
  title: string;
  description: string;
  price: number;
  item_condition: string;
  trade_area: string | null;
  price_offer_yn: number;
  trade_status: string;
  post_status: string;
  registered_at: string;
  updated_at: string | null;
  completed_at: string | null;
  images: { image_no: number; image_path: string }[];
};

type Buyer = { room_no: number; buyer_no: number; buyer_nickname: string; room_status: string };

export default function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const session = useSession();
  const { data: p, error, reload } = useLoad<Product>(`/products/${id}`);
  const isOwner = !!session && !!p && session.member.member_no === p.seller_no;
  const { data: buyers } = useLoad<Buyer[]>(isOwner ? `/products/${id}/chats` : null);

  if (error) return <p className="error">{error}</p>;
  if (!p) return null;

  const post = (path: string, body?: unknown) => act(() => api(`/products/${id}${path}`, { method: "POST", body }), reload);

  return (
    <>
      <div className="images">
        {p.images.length === 0 && <ProductImage path={null} />}
        {p.images.map((img) => <ProductImage key={img.image_no} path={img.image_path} />)}
      </div>
      <h2>
        {p.title} <span className="muted">[{p.trade_status}]</span>
        {p.post_status !== "정상" && <span className="error"> ({p.post_status})</span>}
      </h2>
      <p>
        <b>{won(p.price)}</b> {p.price_offer_yn ? "· 가격 제안 가능" : ""}
      </p>
      <table>
        <tbody>
          <tr><th>판매자</th><td><Link href={`/members/${p.seller_no}`}>{p.seller_nickname}</Link></td></tr>
          <tr><th>물품상태</th><td>{p.item_condition}</td></tr>
          <tr><th>거래 희망 지역</th><td>{p.trade_area ?? "-"}</td></tr>
          <tr><th>등록 / 수정</th><td>{dt(p.registered_at)} / {dt(p.updated_at)}</td></tr>
          {p.reserver_nickname && <tr><th>예약자</th><td>{p.reserver_nickname}</td></tr>}
          {p.buyer_nickname && <tr><th>구매자</th><td>{p.buyer_nickname} ({dt(p.completed_at)})</td></tr>}
        </tbody>
      </table>
      <p style={{ whiteSpace: "pre-wrap" }}>{p.description}</p>

      {session && !isOwner && (
        <div className="row">
          <button
            onClick={() => {
              let room = 0;
              act(
                () => api<{ room_no: number }>(`/products/${id}/chat`, { method: "POST" }).then((r) => (room = r.room_no)),
                () => router.push(`/chats/${room}`),
              );
            }}
          >
            채팅하기
          </button>
          <ReportButton targetType="상품게시글" targetNo={p.product_no} />
          <ReportButton targetType="회원" targetNo={p.seller_no} />
        </div>
      )}

      {isOwner && (
        <>
          <div className="row">
            {p.trade_status !== "판매완료" && <Link href={`/products/${id}/edit`}>수정</Link>}
            <button
              onClick={() =>
                confirm("삭제할까요?") && act(() => api(`/products/${id}`, { method: "DELETE" }), () => router.push("/me"))
              }
            >
              삭제
            </button>
            {p.trade_status === "예약중" && <button onClick={() => post("/unreserve")}>예약 해제</button>}
          </div>
          <h3>채팅한 구매자</h3>
          <table>
            <thead><tr><th>구매자</th><th>채팅방</th><th>처리</th></tr></thead>
            <tbody>
              {buyers?.map((b) => (
                <tr key={b.room_no}>
                  <td>{b.buyer_nickname}</td>
                  <td><Link href={`/chats/${b.room_no}`}>#{b.room_no}</Link> {b.room_status}</td>
                  <td className="row">
                    {p.trade_status === "판매중" && (
                      <button onClick={() => post("/reserve", { buyer_no: b.buyer_no })}>예약자 지정</button>
                    )}
                    {p.trade_status !== "판매완료" && (
                      <button
                        onClick={() => confirm(`${b.buyer_nickname}님과 거래 완료할까요?`) && post("/complete", { buyer_no: b.buyer_no })}
                      >
                        거래 완료
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {buyers?.length === 0 && <p className="muted">아직 채팅한 구매자가 없습니다.</p>}
        </>
      )}
    </>
  );
}
