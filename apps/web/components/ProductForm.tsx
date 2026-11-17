"use client";

const CONDITIONS = ["새상품", "거의새것", "사용감있음", "하자있음"];

export type ProductValues = {
  title: string;
  description: string;
  price: number;
  item_condition: string;
  trade_area: string | null;
  price_offer_yn: number | boolean;
};

export default function ProductForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial?: ProductValues;
  submitLabel: string;
  onSubmit: (form: FormData) => void;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        f.set("price_offer_yn", f.get("price_offer_yn") ? "true" : "false");
        onSubmit(f);
      }}
    >
      <input name="title" placeholder="상품명 *" defaultValue={initial?.title} required />
      <textarea name="description" placeholder="상품 설명 *" defaultValue={initial?.description} required />
      <input name="price" type="number" min={0} placeholder="판매가격 *" defaultValue={initial?.price} required />
      <select name="item_condition" defaultValue={initial?.item_condition ?? "사용감있음"}>
        {CONDITIONS.map((c) => <option key={c}>{c}</option>)}
      </select>
      <input name="trade_area" placeholder="거래 희망 지역 (직거래 시)" defaultValue={initial?.trade_area ?? ""} />
      <label>
        <input name="price_offer_yn" type="checkbox" defaultChecked={!!initial?.price_offer_yn} /> 가격 제안 허용
      </label>
      <label>
        사진 (여러 장, 첫 장이 대표) {initial && <span className="muted">— 새로 올리면 기존 사진 교체</span>}
        <input name="images" type="file" accept="image/*" multiple />
      </label>
      <button>{submitLabel}</button>
    </form>
  );
}
