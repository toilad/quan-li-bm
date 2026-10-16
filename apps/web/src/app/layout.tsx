import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import { Sidebar } from "@/components/shell/sidebar";
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
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="min-w-0 flex-1 px-7 pb-10 pt-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
