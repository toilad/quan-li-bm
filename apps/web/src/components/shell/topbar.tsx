"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { Bell, ChevronDown, FlaskConical, FileSpreadsheet, HardDrive, Globe2, Server, Bot, LogOut, UserCog } from "lucide-react";
import { ACTIVITY, CONNECTIONS } from "@/lib/mock-data";

const CONNECTION_ICON = { sheets: FileSpreadsheet, drive: HardDrive, inet: Globe2, hosting: Server, ai: Bot } as const;

export function Topbar({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-[28px] font-bold tracking-tight">{title}</h1>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-2.5 py-1 text-[11px] font-semibold text-amber-300">
            <FlaskConical className="size-3.5" />
            Bản thiết kế · dữ liệu giả
          </span>
        </div>
        <p className="mt-1 text-[14px] text-fg-muted">{subtitle}</p>
      </div>

      <div className="flex items-center gap-2">
        {CONNECTIONS.map((c) => {
          const Icon = CONNECTION_ICON[c.key as keyof typeof CONNECTION_ICON];
          return (
            <div
              key={c.key}
              title={c.detail}
              className="panel flex items-center gap-2.5 !rounded-xl px-3 py-2"
            >
              <Icon className={clsx("size-[18px]", c.status === "ok" ? "text-sky-300" : "text-amber-300")} />
              <div className="leading-tight">
                <div className="text-[12px] font-semibold">{c.label}</div>
                <div className={clsx("flex items-center gap-1 text-[11px]", c.status === "ok" ? "text-emerald-400" : "text-amber-300")}>
                  <span className={clsx("size-1.5 rounded-full", c.status === "ok" ? "bg-emerald-400" : "bg-amber-300")} />
                  {c.status === "ok" ? "Đã kết nối" : "Cần kiểm tra"}
                </div>
              </div>
            </div>
          );
        })}
        <div className="mx-1 h-9 w-px bg-line" />
        <Notifications />
        <UserMenu />
      </div>
    </header>
  );
}

function useDismiss<T extends HTMLElement>(open: boolean, close: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

function Notifications() {
  const [open, setOpen] = useState(false);
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false));
  const items = ACTIVITY.filter((a) => a.tone !== "ok").slice(0, 4);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Thông báo"
        className="relative grid size-10 place-items-center rounded-xl text-fg-muted transition hover:bg-white/[0.05] hover:text-fg"
      >
        <Bell className="size-5" />
        <span className="absolute right-1.5 top-1.5 grid size-4 place-items-center rounded-full bg-rose-500 text-[10px] font-bold text-white">
          {items.length}
        </span>
      </button>
      {open && (
        <div className="panel absolute right-0 top-12 z-30 w-[340px] p-2">
          <div className="px-3 py-2 text-[13px] font-semibold">Cần chú ý</div>
          {items.map((a) => (
            <div key={a.time + a.title} className="rounded-xl px-3 py-2.5 hover:bg-white/[0.04]">
              <div className="flex items-center justify-between gap-2">
                <span className={clsx("text-[13px] font-medium", a.tone === "error" ? "text-rose-300" : "text-amber-200")}>
                  {a.title}
                </span>
                <span className="text-[11px] text-fg-subtle">{a.time}</span>
              </div>
              <div className="mt-0.5 text-[12px] text-fg-muted">{a.detail}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const [open, setOpen] = useState(false);
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false));

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2.5 rounded-xl py-1 pl-1 pr-2 transition hover:bg-white/[0.05]"
      >
        <span className="grid size-9 place-items-center rounded-full bg-gradient-to-br from-brand to-brand-2 text-[13px] font-bold">
          QT
        </span>
        <span className="text-left leading-tight">
          <span className="block text-[13px] font-semibold">Quản trị viên</span>
          <span className="block text-[11px] text-fg-subtle">Administrator</span>
        </span>
        <ChevronDown className="size-4 text-fg-subtle" />
      </button>
      {open && (
        <div className="panel absolute right-0 top-12 z-30 w-52 p-1.5 text-[13px]">
          <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-fg-muted hover:bg-white/[0.05] hover:text-fg">
            <UserCog className="size-4" /> Tài khoản & phân quyền
          </button>
          <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-fg-muted hover:bg-white/[0.05] hover:text-fg">
            <LogOut className="size-4" /> Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}
