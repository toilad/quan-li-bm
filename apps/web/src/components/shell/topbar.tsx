"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { Bell, FlaskConical, FileSpreadsheet, HardDrive, Globe2, Server, Bot, PlugZap, UserX } from "lucide-react";
import { api, type Job } from "@/lib/api";
import { useBackendStatus } from "./backend-status";

type Pill = { key: string; label: string; icon: typeof Bot; state: "ok" | "partial" | "missing" | "offline"; detail: string };

/**
 * `demo` marks screens that still show sample data (the Dashboard). Connection pills show what the
 * backend reports — "Đã cấu hình" means credentials are set, not that a live call succeeded.
 */
export function Topbar({ title, subtitle, demo = false }: { title: string; subtitle: string; demo?: boolean }) {
  const { status, offline } = useBackendStatus();
  const pills: Pill[] = [];
  if (offline || !status) {
    pills.push({ key: "api", label: "Backend", icon: PlugZap, state: offline ? "offline" : "partial", detail: offline ? "Không kết nối được API" : "Đang kiểm tra…" });
  } else {
    const nk = status.nicks.length;
    const inet = status.nicks.filter((n) => n.inet_key).length;
    const cp = status.nicks.filter((n) => n.cpanel.configured).length;
    const of = (n: number): Pill["state"] => (n === nk ? "ok" : n ? "partial" : "missing");
    pills.push(
      { key: "sheets", label: "Google Sheets", icon: FileSpreadsheet, state: status.google.sheets.configured ? "ok" : "missing", detail: status.google.sheets.missing.join(", ") || "Đã cấu hình" },
      { key: "drive", label: "Drive", icon: HardDrive, state: status.google.drive.configured ? "ok" : "missing", detail: status.google.drive.missing.join(", ") || "Đã cấu hình" },
      { key: "inet", label: "iNET", icon: Globe2, state: of(inet), detail: `${inet}/${nk} nick có khoá API` },
      { key: "hosting", label: "Hosting", icon: Server, state: of(cp), detail: `${cp}/${nk} cPanel có token` },
      { key: "ai", label: "AI", icon: Bot, state: status.ai.configured ? "ok" : "missing", detail: status.ai.configured ? status.ai.model : status.ai.missing.join(", ") },
    );
  }
  const text = { ok: "Đã cấu hình", partial: "Thiếu một phần", missing: "Chưa cấu hình", offline: "Không kết nối" } as const;

  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-[28px] font-bold tracking-tight">{title}</h1>
          {demo && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-2.5 py-1 text-[11px] font-semibold text-amber-300">
              <FlaskConical className="size-3.5" />
              Dữ liệu mẫu
            </span>
          )}
        </div>
        <p className="mt-1 text-[14px] text-fg-muted">{subtitle}</p>
      </div>

      <div className="flex items-center gap-2">
        {pills.map((c) => (
          <div key={c.key} title={c.detail} className="panel flex items-center gap-2.5 !rounded-xl px-3 py-2">
            <c.icon className={clsx("size-[18px]", c.state === "ok" ? "text-sky-300" : c.state === "partial" ? "text-amber-300" : "text-rose-300")} />
            <div className="leading-tight">
              <div className="text-[12px] font-semibold">{c.label}</div>
              <div className={clsx("flex items-center gap-1 text-[11px]", c.state === "ok" ? "text-emerald-400" : c.state === "partial" ? "text-amber-300" : "text-rose-300")}>
                <span className={clsx("size-1.5 rounded-full", c.state === "ok" ? "bg-emerald-400" : c.state === "partial" ? "bg-amber-300" : "bg-rose-400")} />
                {text[c.state]}
              </div>
            </div>
          </div>
        ))}
        <div className="mx-1 h-9 w-px bg-line" />
        <Notifications />
        <span title="Chưa bật đăng nhập / phân quyền" className="grid size-10 place-items-center rounded-xl text-fg-subtle">
          <UserX className="size-5" />
        </span>
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

const KIND_LABEL: Record<string, string> = { pdf_save: "Lưu PDF", pdf_ai_read: "AI đọc PDF", domain_create: "Tạo miền", web_build: "Dựng web" };

/** Real jobs that need attention (failed / blocked / conflict). */
function Notifications() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Job[]>([]);
  const ref = useDismiss<HTMLDivElement>(open, () => setOpen(false));
  useEffect(() => {
    const load = () =>
      api.get<Job[]>("/api/jobs")
        .then((js) => setItems(js.filter((j) => ["failed", "blocked", "conflict"].includes(j.status)).slice(0, 6)))
        .catch(() => setItems([]));
    load();
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Thông báo"
        className="relative grid size-10 place-items-center rounded-xl text-fg-muted transition hover:bg-white/[0.05] hover:text-fg"
      >
        <Bell className="size-5" />
        {items.length > 0 && (
          <span className="absolute right-1.5 top-1.5 grid size-4 place-items-center rounded-full bg-rose-500 text-[10px] font-bold text-white">{items.length}</span>
        )}
      </button>
      {open && (
        <div className="panel absolute right-0 top-12 z-30 w-[360px] p-2">
          <div className="px-3 py-2 text-[13px] font-semibold">Cần chú ý</div>
          {items.length === 0 && <div className="px-3 pb-3 text-[12px] text-fg-subtle">Không có tác vụ lỗi.</div>}
          {items.map((j) => (
            <div key={j.id} className="rounded-xl px-3 py-2.5 hover:bg-white/[0.04]">
              <span className={clsx("text-[13px] font-medium", j.status === "failed" ? "text-rose-300" : "text-amber-200")}>
                {KIND_LABEL[j.kind] ?? j.kind} #{j.id} · {j.status === "blocked" ? "dừng" : j.status === "conflict" ? "xung đột" : "lỗi"}
              </span>
              <div className="mt-0.5 line-clamp-2 text-[12px] text-fg-muted">{j.error}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
