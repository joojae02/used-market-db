"use client";

import { useRouter } from "next/navigation";
import ProductForm from "@/components/ProductForm";
import { api } from "@/lib/api";
import { act } from "@/lib/hooks";

export default function NewProductPage() {
  const router = useRouter();
  return (
    <>
      <h2>상품 등록</h2>
      <ProductForm
        submitLabel="등록"
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
