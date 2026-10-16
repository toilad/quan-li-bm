"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard, FileText, Globe2, ShieldCheck, LayoutTemplate, ScrollText, Settings, DatabaseBackup, CheckCircle2,
} from "lucide-react";
import { BACKUP } from "@/lib/mock-data";

const NAV = [
  { href: "/", label: "Tổng quan", icon: LayoutDashboard },
  { href: "/pdf", label: "PDF Manager", icon: FileText },
  { href: "/domains", label: "Tạo miền iNET", icon: Globe2 },
  { href: "/websites", label: "SSL + Tạo web", icon: ShieldCheck },
  { href: "/templates", label: "Kho mẫu web", icon: LayoutTemplate },
  { href: "/logs", label: "Nhật ký", icon: ScrollText },
  { href: "/settings", label: "Cài đặt API", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-screen w-[264px] shrink-0 flex-col border-r border-line bg-ink-900/70 px-4 py-6 backdrop-blur-xl">
      <Link href="/" className="mb-8 flex items-center gap-3 px-2">
        <Logo />
        <div className="leading-tight">
          <div className="text-[15px] font-bold tracking-tight">WebsiteGenerator</div>
          <div className="text-gradient text-[13px] font-semibold">Studio</div>
        </div>
      </Link>

      <nav className="flex flex-col gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "group relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-[14px] font-medium transition-colors",
                active
                  ? "bg-gradient-to-r from-brand/90 to-brand-2/70 text-white shadow-[0_8px_24px_-8px_rgb(79_124_255/0.6)]"
                  : "text-fg-muted hover:bg-white/[0.04] hover:text-fg",
              )}
            >
              <Icon className={clsx("size-[18px]", active ? "text-white" : "text-fg-subtle group-hover:text-fg-muted")} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto">
        <div className="panel !rounded-2xl p-4">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold">
            <DatabaseBackup className="size-4 text-emerald-400" />
            Bảo vệ dữ liệu
          </div>
          <dl className="space-y-2 text-[12px]">
            <Row label="Sao lưu gần nhất" value={BACKUP.lastRun} />
            <Row label="Số phiên bản" value={`${BACKUP.versions} bản`} />
            <Row label="Thử khôi phục" value={BACKUP.lastRestoreTest} />
          </dl>
          <div className="mt-3 flex items-center gap-1.5 text-[11px] text-emerald-400/90">
            <CheckCircle2 className="size-3.5" />
            Lưu tại kho độc lập · mã hoá
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between px-2 text-[12px] text-fg-subtle">
          <span>v0.1 · bản thiết kế</span>
          <span className="flex items-center gap-1.5">
            <span className="animate-pulse-dot size-1.5 rounded-full bg-emerald-400" />
            Hoạt động
          </span>
        </div>
      </div>
    </aside>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-fg-subtle">{label}</dt>
      <dd className="font-medium text-fg-muted">{value}</dd>
    </div>
  );
}

function Logo() {
  return (
    <svg viewBox="0 0 40 40" className="size-10" aria-hidden>
      <defs>
        <linearGradient id="wg-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5b8cff" />
          <stop offset="1" stopColor="#9b6bff" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#wg-logo)" opacity="0.16" />
      <path
        d="M8 11l5.2 18L20 15.5 26.8 29 32 11"
        fill="none"
        stroke="url(#wg-logo)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
