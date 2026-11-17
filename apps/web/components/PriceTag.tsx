import { won } from "@/lib/api";

export default function PriceTag({ price, large }: { price: number; large?: boolean }) {
  return <span className={`price${large ? " large" : ""}`}>{price === 0 ? "나눔" : won(price)}</span>;
}
