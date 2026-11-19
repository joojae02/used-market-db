"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import PriceTag from "@/components/PriceTag";
import ProductImage from "@/components/ProductImage";
import ReportButton from "@/components/ReportButton";
import Status from "@/components/Status";
import { api, dt } from "@/lib/api";
import { act, useLoad, useSession } from "@/lib/hooks";

type Product = {
  product_no: number;
  seller_no: number;
  reserver_no: number | null;
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
      <div className={`detail${p.trade_status === "판매완료" ? " sold" : ""}`}>
        <div className="gallery">
          {p.images.length === 0 && <ProductImage path={null} />}
          {p.images.map((img) => <ProductImage key={img.image_no} path={img.image_path} />)}
        </div>

        <div className="detail-info">
          <div className="row">
            <Status value={p.trade_status} />
            {p.post_status !== "정상" && <Status value={p.post_status} />}
          </div>
          <h1>{p.title}</h1>
          <PriceTag price={p.price} large />
          <dl className="specs">
            <dt>판매자</dt>
            <dd><Link href={`/members/${p.seller_no}`}>{p.seller_nickname}</Link></dd>
            <dt>물품상태</dt>
            <dd>{p.item_condition}</dd>
            <dt>거래 희망 지역</dt>
            <dd>{p.trade_area ?? "정하지 않음"}</dd>
            <dt>가격 제안</dt>
            <dd>{p.price_offer_yn ? "받아요" : "받지 않아요"}</dd>
            {p.reserver_nickname && (
              <>
                <dt>예약자</dt>
                <dd>{p.reserver_nickname}</dd>
              </>
            )}
            {p.buyer_nickname && (
              <>
                <dt>구매자</dt>
                <dd>{p.buyer_nickname} <span className="muted">({dt(p.completed_at)} 거래 완료)</span></dd>
              </>
            )}
            <dt>등록</dt>
            <dd>{dt(p.registered_at)}{p.updated_at && <span className="muted"> (수정 {dt(p.updated_at)})</span>}</dd>
          </dl>
          <p className="description">{p.description}</p>

          {session && !isOwner && (
            <div className="actions">
              <button
                className="primary"
                disabled={p.trade_status === "판매완료"}
                onClick={() => {
                  let room = 0;
                  act(
                    () => api<{ room_no: number }>(`/products/${id}/chat`, { method: "POST" }).then((r) => (room = r.room_no)),
                    () => router.push(`/chats/${room}`),
                  );
                }}
              >
                판매자와 채팅하기
              </button>
              <ReportButton targetType="상품게시글" targetNo={p.product_no} />
              <ReportButton targetType="회원" targetNo={p.seller_no} />
            </div>
          )}
          {!session && (
            <p className="muted">
              <Link href="/login">로그인</Link>하면 판매자와 채팅할 수 있어요.
            </p>
          )}

          {isOwner && (
            <div className="actions">
              {p.trade_status !== "판매완료" && (
                <Link href={`/products/${id}/edit`} className="button">
                  수정
                </Link>
              )}
              {p.trade_status === "예약중" && <button onClick={() => post("/unreserve")}>예약 해제</button>}
              <button
                className="danger"
                onClick={() =>
                  confirm("이 게시글을 삭제할까요?") && act(() => api(`/products/${id}`, { method: "DELETE" }), () => router.push("/me"))
                }
              >
                삭제
              </button>
            </div>
          )}
        </div>
      </div>

      {isOwner && (
        <section className="seller-panel">
          <h3>
            채팅한 구매자
          </h3>
          {p.trade_status === "예약중" && (
            <p className="muted">예약중에는 예약자와만 거래를 완료할 수 있어요. 다른 사람과 거래하려면 먼저 예약을 해제하세요.</p>
          )}
          {buyers?.length === 0 ? (
            <p className="muted">아직 채팅한 구매자가 없어요. 채팅한 사람 중에서 예약자와 구매자를 고를 수 있어요.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>구매자</th><th>채팅방</th><th>처리</th></tr></thead>
                <tbody>
                  {buyers?.map((b) => (
                    <tr key={b.room_no}>
                      <td>{b.buyer_nickname}</td>
                      <td>
                        <Link href={`/chats/${b.room_no}`}>대화 보기</Link> <Status value={b.room_status} />
                      </td>
                      <td>
                        <div className="row">
                          {p.trade_status === "판매중" && (
                            <button onClick={() => post("/reserve", { buyer_no: b.buyer_no })}>예약자로 지정</button>
                          )}
                          {(p.trade_status === "판매중" || (p.trade_status === "예약중" && b.buyer_no === p.reserver_no)) && (
                            <button
                              className="primary"
                              onClick={() => confirm(`${b.buyer_nickname}님과 거래를 완료할까요?`) && post("/complete", { buyer_no: b.buyer_no })}
                            >
                              이 사람과 거래 완료
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </>
  );
}
