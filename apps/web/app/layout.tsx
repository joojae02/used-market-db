import type { Metadata } from "next";
import { IBM_Plex_Sans_KR } from "next/font/google";
import { Suspense } from "react";
import Nav from "@/components/Nav";
import "./globals.css";

// 한글 글리프는 subset 미리 받기가 안 돼서 preload 를 끈다
const body = IBM_Plex_Sans_KR({ weight: ["400", "500", "600"], preload: false, variable: "--font-body" });

export const metadata: Metadata = {
  title: "중고마켓",
  description: "데이터베이스응용 3조 중고거래 플랫폼 데모",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={body.variable}>
      <body>
        <header className="site-header">
          <Nav />
        </header>
        <main>
          {/* 모든 화면이 클라이언트에서 API 를 부르므로 useParams 등은 Suspense 안에서 스트리밍 */}
          <Suspense fallback={null}>{children}</Suspense>
        </main>
      </body>
    </html>
  );
}
