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
      className="panel"
      style={{ maxWidth: 640 }}
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        f.set("price_offer_yn", f.get("price_offer_yn") ? "true" : "false");
        onSubmit(f);
      }}
    >
      <label className="field">
        사진 <small>여러 장 올릴 수 있고 첫 장이 대표 사진이에요{initial && ". 새로 올리면 기존 사진을 바꿔요"}</small>
        <input name="images" type="file" accept="image/*" multiple />
      </label>
      <label className="field">
        상품명
        <input name="title" defaultValue={initial?.title} maxLength={100} required />
      </label>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <label className="field" style={{ flex: 1, minWidth: 160 }}>
          판매가격 (원) <small>0원이면 나눔으로 표시돼요</small>
          <input name="price" type="number" min={0} step={100} defaultValue={initial?.price} required />
        </label>
        <label className="field" style={{ flex: 1, minWidth: 160 }}>
          물품상태
          <select name="item_condition" defaultValue={initial?.item_condition ?? "사용감있음"}>
            {CONDITIONS.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
      </div>
      <label className="check">
        <input name="price_offer_yn" type="checkbox" defaultChecked={!!initial?.price_offer_yn} /> 가격 제안 받기
      </label>
      <label className="field">
        거래 희망 지역 <small>직거래할 때만</small>
        <input name="trade_area" placeholder="예: 숭실대입구역 2번 출구" defaultValue={initial?.trade_area ?? ""} />
      </label>
      <label className="field">
        설명
        <textarea name="description" rows={6} placeholder="구매 시기, 사용 기간, 하자 여부를 적어주세요" defaultValue={initial?.description} required />
      </label>
      <div>
        <button className="primary">{submitLabel}</button>
      </div>
    </form>
  );
}
