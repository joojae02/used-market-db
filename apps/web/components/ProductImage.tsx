"use client";

import { useState } from "react";
import { imageUrl } from "@/lib/api";

/** 이미지가 없거나 불러오기 실패하면 회색 플레이스홀더 */
export default function ProductImage({ path, className }: { path: string | null; className?: string }) {
  const [broken, setBroken] = useState(false);
  if (!path || broken) return <div className={`placeholder ${className ?? ""}`}>이미지 없음</div>;
  return <img src={imageUrl(path)} alt="" className={className} onError={() => setBroken(true)} />;
}
