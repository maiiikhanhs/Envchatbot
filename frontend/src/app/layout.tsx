import type { Metadata } from "next";
import { AuthProvider } from "@/components/AuthProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "EnvChat — Chatbot Quan Trắc Môi Trường",
  description:
    "Chatbot hỗ trợ nghiệp vụ quan trắc môi trường: pháp lý, thông số, quy trình, hồ sơ, vận hành.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
