"use client";

import clsx from "clsx";
import { Zap, Play, Pause, RotateCcw, Shuffle, Eye, Layers } from "lucide-react";
import { ROW_STATUS, SimTag } from "./ui";
import { previewIssue, usablePool, type DomainDispatch, type DomainState } from "./use-domain-queue";
import type { RowStatus } from "@/lib/domain-mock";

const ORDER: RowStatus[] = ["queued", "running", "done", "failed", "conflict", "idle"];

export function RunPanel({ state, dispatch, onPreview }: { state: DomainState; dispatch: DomainDispatch; onPreview: () => void }) {
  const pool = usablePool(state);
  const { rows } = state;
  const count = (s: RowStatus) => rows.filter((r) => r.status === s).length;
  const inRun = rows.filter((r) => r.status !== "idle");
  const settled = inRun.filter((r) => ["done", "failed", "conflict"].includes(r.status)).length;
  const pct = inRun.length ? Math.round((settled / inRun.length) * 100) : 0;
  const checked = rows.filter((r) => r.checked && r.status === "idle");
  const startable = checked.filter((r) => !previewIssue(r, state)).length;
  const failed = count("failed");
  const active = count("running") + count("queued") > 0;

  return (
    <section className="panel flex flex-col p-5">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Zap className="size-5 text-emerald-300" />
          <h2 className="text-[16px] font-semibold">Lượt tạo miền</h2>
          <SimTag />
        </div>
        <span className="font-mono text-[12px] text-fg-subtle">
          {settled}/{inRun.length}
        </span>
      </header>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-300 transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between text-[11.5px] text-fg-subtle">
        <span>
          {state.paused ? "Đã tạm dừng — bước đang chạy xong rồi dừng" : active ? "Backend đang chạy · mỗi nick một việc một lúc" : "Rảnh — không có việc trong hàng đợi"}
        </span>
        <span>{pct}%</span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {ORDER.map((s) => {
          const m = ROW_STATUS[s];
          return (
            <div key={s} className="rounded-xl border border-line bg-ink-850/60 px-3 py-2">
              <div className={clsx("flex items-center gap-1 text-[11px] font-medium", m.cls.split(" ").find((c) => c.startsWith("text-")))}>
                <m.icon className={clsx("size-3", m.spin && count(s) > 0 && "animate-spin")} /> {m.label}
              </div>
              <div className="mt-0.5 text-[20px] font-bold leading-tight">{count(s)}</div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 space-y-3 border-t border-line pt-4 text-[12.5px]">
        <div className="flex items-center gap-2">
          <Layers className="size-4 text-fg-subtle" />
          <span className="text-fg-muted">Giới hạn mỗi lượt</span>
          <input
            type="number"
            min={1}
            max={200}
            value={state.batchLimit}
            onChange={(e) => dispatch({ type: "batchLimit", n: Math.max(1, Math.min(200, Number(e.target.value) || 1)) })}
            className="h-8 w-16 rounded-lg border border-line bg-ink-850 px-2 text-center outline-none focus:border-brand/60"
            aria-label="Giới hạn số dòng mỗi lượt"
          />
          <span className="text-[11px] text-fg-subtle">dòng · khác hạn mức từng nick/ngày</span>
        </div>

        <div className="flex items-start gap-2 rounded-lg border border-line bg-ink-850/50 px-3 py-2">
          <Shuffle className="mt-0.5 size-4 shrink-0 text-fg-subtle" />
          <div className="text-[12px] leading-relaxed">
            {pool.length ? (
              <>
                <b>{checked.length}</b> dòng cột B trống (từ trên xuống) · chia lần lượt cho{" "}
                <span className="font-mono">{[...pool].map((p) => p.root.name).sort().join(" → ")}</span>, rồi quay vòng.
                {checked.length > state.batchLimit && <span className="text-fg-subtle"> Lượt này chạy {state.batchLimit} dòng đầu.</span>}
              </>
            ) : (
              <span className="text-amber-200">Bấm chọn miền gốc ở bảng “Miền gốc” bên dưới — app tự lấy các dòng cột B trống.</span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          onClick={onPreview}
          disabled={!checked.length || !pool.length}
          className="col-span-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 py-2.5 text-[13px] font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Eye className="size-4" /> Xem trước & chạy {Math.min(startable, state.batchLimit)} dòng
          {checked.length > startable && <span className="font-normal opacity-80">· {checked.length - startable} bị chặn</span>}
        </button>
        <button
          onClick={() => dispatch({ type: state.paused ? "resume" : "pause" })}
          disabled={!active && !state.paused}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white/[0.07] px-3 py-2 text-[12.5px] font-semibold hover:bg-white/[0.11] disabled:opacity-40"
        >
          {state.paused ? <Play className="size-4" /> : <Pause className="size-4" />}
          {state.paused ? "Tiếp tục" : "Tạm dừng"}
        </button>
        <button
          onClick={() => dispatch({ type: "retryAll" })}
          disabled={!failed}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[12.5px] font-medium text-fg-muted hover:border-line-strong hover:text-fg disabled:opacity-40"
        >
          <RotateCcw className="size-4" /> Thử lại lỗi ({failed})
        </button>
      </div>
    </section>
  );
}
