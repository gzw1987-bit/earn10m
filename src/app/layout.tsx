import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import NavUnified from "@/components/NavUnified";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "OPC一人公司 | 从负债360万到年赚千万 · 真实记录",
  description:
    "一个人+AI，从负债360万出发，OPC一人公司模式，目标年赚千万。每一天、每一笔、每一个决策，全过程公开记录。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col" style={{ background: "#08080c" }}>
        <NavUnified />
        <main className="flex-1 pt-16">{children}</main>
        <footer className="border-t border-[#1e1e2e] py-8 text-center text-sm text-text-muted">
          <div className="mx-auto max-w-6xl px-4">
            <p>
              <span className="text-[#818cf8]">OPC 一人公司</span>
              <span className="mx-2">×</span>
              <span className="text-[#34d399]">AI</span>
              <span className="mx-2">—</span>
              从负债360万到年赚千万 · 全过程真实记录
            </p>
            <p className="mt-1">0 员工 · N 个 AI Agent · Started 2026.04.13</p>
          </div>
        </footer>
        <Analytics />
      </body>
    </html>
  );
}
