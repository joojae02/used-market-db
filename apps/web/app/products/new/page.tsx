"use client";

import { useRouter } from "next/navigation";
import ProductForm from "@/components/ProductForm";
import { api } from "@/lib/api";
import { act } from "@/lib/hooks";

export default function NewProductPage() {
  const router = useRouter();
  return (
    <>
      <div className="page-head">
        <h1>
          내 물건 팔기
        </h1>
      </div>
      <ProductForm
        submitLabel="판매 글 올리기"
        onSubmit={(f) => {
          let no = 0;
          act(
            () => api<{ product_no: number }>("/products", { method: "POST", body: f }).then((r) => (no = r.product_no)),
            () => router.push(`/products/${no}`),
          );
        }}
      />
    </>
  );
}
