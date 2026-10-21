import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "CV RAG AI — Trợ lý tuyển dụng",
  description: "Tra cứu hồ sơ và hỗ trợ tuyển dụng trong phạm vi được cấp quyền.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi">
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
