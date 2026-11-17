"use client";

import Link from "next/link";
import { useState } from "react";
import PriceTag from "@/components/PriceTag";
import ProductImage from "@/components/ProductImage";
import Status from "@/components/Status";
import { dt } from "@/lib/api";
import { useLoad } from "@/lib/hooks";

type Item = {
  product_no: number;
  title: string;
  price: number;
  trade_status: string;
  trade_area: string | null;
  registered_at: string;
  seller_nickname: string;
  thumbnail: string | null;
};

const FILTERS = ["", "판매중", "예약중", "판매완료"];

export default function Home() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [submitted, setSubmitted] = useState("");
  const params = new URLSearchParams();
  if (submitted) params.set("q", submitted);
  if (status) params.set("trade_status", status);
  const { data, error } = useLoad<Item[]>(`/products?${params}`);

  return (
    <>
      <form
        className="search"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(q.trim());
        }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="찾는 물건을 검색하세요" aria-label="상품 검색" />
        <button className="primary">검색</button>
      </form>
      <div className="filters" role="group" aria-label="거래 상태">
        {FILTERS.map((f) => (
          <button key={f || "all"} aria-pressed={status === f} onClick={() => setStatus(f)}>
            {f || "전체"}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {data && (
        <p className="result-count">
          {submitted ? `‘${submitted}’ 검색 결과 ` : ""}
          {data.length}개
        </p>
      )}
      <div className="grid">
        {data?.map((p) => (
          <Link key={p.product_no} href={`/products/${p.product_no}`} className={`card${p.trade_status === "판매완료" ? " sold" : ""}`}>
            <ProductImage path={p.thumbnail} className="thumb" />
            <div className="card-title">{p.title}</div>
            <PriceTag price={p.price} />
            <div className="card-meta">
              <span>{p.trade_area ?? "택배·지역 미정"}</span>
              <Status value={p.trade_status} />
            </div>
            <div className="card-meta">
              <span>{p.seller_nickname}</span>
              <span>{dt(p.registered_at).slice(5, 10).replace("-", ".")}</span>
            </div>
          </Link>
        ))}
      </div>
      {data?.length === 0 && (
        <div className="empty">
          <p>조건에 맞는 물건이 없어요.</p>
          <Link href="/products/new" className="button">
            내 물건 팔기
          </Link>
        </div>
      )}
    </>
  );
}
