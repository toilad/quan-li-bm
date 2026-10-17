import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import { AppFrame } from "@/components/shell/app-frame";
import "./globals.css";

const beVietnam = Be_Vietnam_Pro({
  variable: "--font-be-vietnam",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Quản Lí BM",
  description: "Quản lý PDF doanh nghiệp, tên miền và website tự động",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body className={`${beVietnam.variable} font-sans antialiased`}>
        <AppFrame>{children}</AppFrame>
      </body>
    </html>
  );
}
