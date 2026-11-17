"use client";

import { useParams, useRouter } from "next/navigation";
import ProductForm, { ProductValues } from "@/components/ProductForm";
import { api } from "@/lib/api";
import { act, useLoad } from "@/lib/hooks";

export default function EditProductPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error } = useLoad<ProductValues>(`/products/${id}`);
  if (error) return <p className="error">{error}</p>;
  if (!data) return null;
  return (
    <>
      <h2>상품 수정</h2>
      <ProductForm
        initial={data}
        submitLabel="저장"
        onSubmit={(f) => act(() => api(`/products/${id}`, { method: "PUT", body: f }), () => router.push(`/products/${id}`))}
      />
    </>
  );
}
