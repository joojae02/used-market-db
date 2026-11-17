"use client";

import Link from "next/link";
import { useState } from "react";
import ProductImage from "@/components/ProductImage";
import { dt, won } from "@/lib/api";
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

export default function Home() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("/products");
  const { data, error } = useLoad<Item[]>(query);

  return (
    <>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          const p = new URLSearchParams();
          if (q) p.set("q", q);
          if (status) p.set("trade_status", status);
          setQuery(`/products?${p}`);
        }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="상품 검색" />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">전체</option>
          <option>판매중</option>
          <option>예약중</option>
          <option>판매완료</option>
        </select>
        <button>검색</button>
      </form>
      {error && <p className="error">{error}</p>}
      <div className="grid" style={{ marginTop: 12 }}>
        {data?.map((p) => (
          <Link key={p.product_no} href={`/products/${p.product_no}`} className="card">
            <ProductImage path={p.thumbnail} className="thumb" />
            <div>{p.title}</div>
            <b>{won(p.price)}</b> <span className="muted">[{p.trade_status}]</span>
            <div className="muted">
              {p.seller_nickname} · {p.trade_area ?? "지역 미정"} · {dt(p.registered_at)}
            </div>
          </Link>
        ))}
      </div>
      {data?.length === 0 && <p className="muted">상품이 없습니다.</p>}
    </>
  );
}
