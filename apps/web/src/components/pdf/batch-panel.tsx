"use client";

import clsx from "clsx";
import { Play, Pause, RotateCcw, Save, FolderOpen, FileSpreadsheet as SheetIcon, Zap } from "lucide-react";
import { SHEET_TABS, type PdfStatus } from "@/lib/pdf-mock";
import { PDF_STATUS } from "./status";
import type { QueueDispatch, QueueState } from "./use-pdf-queue";
import { validate } from "@/lib/pdf-mock";

const ORDER: PdfStatus[] = ["queued", "processing", "review", "saved", "failed", "duplicate"];

export function BatchPanel({ state, dispatch }: { state: QueueState; dispatch: QueueDispatch }) {
  const { files } = state;
  const count = (s: PdfStatus) => files.filter((f) => f.status === s).length;
  const total = files.length;
  const settled = files.filter((f) => !["queued", "processing"].includes(f.status)).length;
  const pct = total ? Math.round((settled / total) * 100) : 0;
  const queued = count("queued");
  const failed = count("failed");
  const cleanReview = files.filter((f) => f.status === "review" && f.fields && Object.keys(validate(f.fields)).length === 0).length;

  return (
    <section className="panel flex flex-col p-5">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Zap className="size-5 text-violet-300" />
          <h2 className="text-[16px] font-semibold">Lượt xử lý hiện tại</h2>
        </div>
        <span className="font-mono text-[12px] text-fg-subtle">
          {settled}/{total} file
        </span>
      </header>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-indigo-400 via-violet-400 to-fuchsia-400 transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[11.5px] text-fg-subtle">
        <span>{state.running ? "Đang chạy · tối đa 2 file song song" : "Tạm dừng"}</span>
        <span>{pct}%</span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {ORDER.map((s) => {
          const meta = PDF_STATUS[s];
          return (
            <div key={s} className="rounded-xl border border-line bg-ink-850/60 px-3 py-2">
              <div className={clsx("flex items-center gap-1 text-[11px] font-medium", meta.cls.split(" ").find((c) => c.startsWith("text-")))}>
                <meta.icon className={clsx("size-3", meta.spin && count(s) > 0 && "animate-spin")} />
                {meta.label}
              </div>
              <div className="mt-0.5 text-[20px] font-bold leading-tight">{count(s)}</div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          onClick={() => dispatch({ type: "run", on: !state.running })}
          disabled={!state.running && queued === 0}
          className={clsx(
            "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[12.5px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-40",
            state.running ? "bg-white/[0.07] hover:bg-white/[0.11]" : "bg-gradient-to-r from-brand to-brand-2 text-white hover:brightness-110",
          )}
        >
          {state.running ? <Pause className="size-4" /> : <Play className="size-4" />}
          {state.running ? "Tạm dừng" : `Bắt đầu (${queued} chờ)`}
        </button>
        <button
          onClick={() => dispatch({ type: "retryAll" })}
          disabled={failed === 0}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[12.5px] font-medium text-fg-muted transition hover:border-line-strong hover:text-fg disabled:opacity-40"
        >
          <RotateCcw className="size-4" /> Thử lại lỗi ({failed})
        </button>
        <button
          onClick={() => dispatch({ type: "saveAllValid" })}
          disabled={cleanReview === 0}
          title="Chỉ lưu file đã đủ trường, đúng định dạng, không trùng"
          className="col-span-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-2 text-[12.5px] font-semibold text-emerald-200 transition hover:bg-emerald-500/25 disabled:opacity-40"
        >
          <Save className="size-4" /> Lưu tất cả file hợp lệ ({cleanReview})
        </button>
      </div>

    </section>
  );
}

/** Per-run settings shown under the drop zone. */
export function BatchSettings({ state, dispatch }: { state: QueueState; dispatch: QueueDispatch }) {
  return (
    <div className="grid grid-cols-1 gap-2 text-[12.5px] min-[1500px]:grid-cols-3">
      <label className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-line bg-ink-850/60 px-3.5 py-2.5">
        <span className="text-fg-muted">
          Tự lưu file hợp lệ
          <span className="block text-[11px] text-fg-subtle">Đủ trường, đúng định dạng, không trùng</span>
        </span>
        <Toggle on={state.autoSave} onChange={(on) => dispatch({ type: "autoSave", on })} />
      </label>
      <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-ink-850/60 px-3.5 py-2.5">
        <span className="inline-flex items-center gap-1.5 text-fg-muted">
          <SheetIcon className="size-3.5" /> Ghi vào tab
        </span>
        <select
          value={state.tab}
          onChange={(e) => dispatch({ type: "tab", tab: e.target.value as QueueState["tab"] })}
          className="rounded-lg border border-line bg-ink-850 px-2 py-1 text-[12.5px] outline-none focus:border-brand/60"
        >
          {SHEET_TABS.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-ink-850/60 px-3.5 py-2.5">
        <span className="inline-flex items-center gap-1.5 text-fg-muted">
          <FolderOpen className="size-3.5" /> Thư mục Drive
        </span>
        <span className="truncate font-medium">Phôi PDF / 2026-10</span>
      </div>
    </div>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={clsx("relative h-6 w-11 shrink-0 rounded-full transition", on ? "bg-gradient-to-r from-brand to-brand-2" : "bg-white/[0.1]")}
    >
      <span className={clsx("absolute top-0.5 size-5 rounded-full bg-white shadow transition-all", on ? "left-[22px]" : "left-0.5")} />
    </button>
  );
}
