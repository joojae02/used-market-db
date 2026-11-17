import type { Metadata } from "next";
import { Suspense } from "react";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "중고마켓 데모",
  description: "데이터베이스응용 3조 중고거래 플랫폼 데모",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <Nav />
        <main>
          {/* 모든 화면이 클라이언트에서 API 를 부르므로 useParams 등은 Suspense 안에서 스트리밍 */}
          <Suspense fallback={null}>{children}</Suspense>
        </main>
      </body>
    </html>
  );
}
