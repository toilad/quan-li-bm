"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard, FileText, Globe2, ShieldCheck, LayoutTemplate, ScrollText, Settings, DatabaseBackup, CheckCircle2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Backups = { count: number; latest: string | null; restore_test: string | null };

/** Real backup files reported by the backend — never a made-up number. */
function useBackups() {
  const [b, setB] = useState<Backups | null>(null);
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const load = () => api.get<Backups>("/api/backups").then((x) => { setB(x); setOffline(false); }).catch(() => setOffline(true));
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, []);
  return { b, offline };
}

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
  const { b, offline } = useBackups();
  const last = b?.latest ? new Date(b.latest).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }) : null;

  return (
    <aside className="sticky top-0 flex h-screen w-[264px] shrink-0 flex-col border-r border-line bg-ink-900/70 px-4 py-6 backdrop-blur-xl">
      <Link href="/" className="mb-8 flex items-center gap-3 px-2">
        <Logo />
        <div className="leading-tight">
          <div className="text-[17px] font-bold tracking-tight">
            Quản Lí <span className="text-gradient">BM</span>
          </div>
          <div className="mt-0.5 text-[11.5px] font-medium text-fg-subtle">PDF · Tên miền · Website</div>
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
            <Row label="Sao lưu gần nhất" value={offline ? "—" : last ?? "Chưa có"} />
            <Row label="Số bản" value={offline ? "—" : `${b?.count ?? 0} bản`} />
            <Row label="Thử khôi phục" value={b?.restore_test ?? "Chưa tự động"} />
          </dl>
          <div className="mt-3 flex items-center gap-1.5 text-[11px] text-amber-300/90">
            <CheckCircle2 className="size-3.5" />
            Bản sao lưu ở máy chủ · chưa đẩy ra kho ngoài
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between px-2 text-[12px] text-fg-subtle">
          <span>v0.2 · backend local</span>
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
      <rect x="0.75" y="0.75" width="38.5" height="38.5" rx="10.25" fill="none" stroke="url(#wg-logo)" strokeOpacity="0.45" strokeWidth="1.5" />
      <text
        x="20"
        y="26"
        textAnchor="middle"
        fontSize="15"
        fontWeight="800"
        letterSpacing="-0.5"
        fill="url(#wg-logo)"
        style={{ fontFamily: "var(--font-be-vietnam), system-ui, sans-serif" }}
      >
        BM
      </text>
    </svg>
  );
}
