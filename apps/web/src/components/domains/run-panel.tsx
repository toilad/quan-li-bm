"use client";

import { useState } from "react";
import clsx from "clsx";
import { Zap, Play, Pause, RotateCcw, ListChecks, Shuffle, Eye, Layers } from "lucide-react";
import { ROW_STATUS, SimTag } from "./ui";
import { previewIssue, usablePool, type DomainDispatch, type DomainState, type Strategy } from "./use-domain-queue";
import type { RowStatus } from "@/lib/domain-mock";

const ORDER: RowStatus[] = ["queued", "running", "done", "failed", "conflict", "idle"];

const STRATEGIES: { key: Strategy; label: string }[] = [
  { key: "roundRobin", label: "Xoay vòng các miền đã chọn (đan xen nick)" },
  { key: "weighted", label: "Theo tỷ trọng nick, xoay vòng miền trong nick" },
  { key: "single", label: "Dồn vào một miền" },
];

export function RunPanel({ state, dispatch, onPreview }: { state: DomainState; dispatch: DomainDispatch; onPreview: () => void }) {
  const [n, setN] = useState(10);
  const [skipFlagged, setSkipFlagged] = useState(true);
  const [strategy, setStrategy] = useState<Strategy>("roundRobin");
  const pool = usablePool(state);
  const [root, setRoot] = useState("");
  const singleRoot = pool.some((p) => p.root.name === root) ? root : pool[0]?.root.name ?? "";
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

        <div className="flex flex-wrap items-center gap-2">
          <ListChecks className="size-4 text-fg-subtle" />
          <span className="text-fg-muted">Chọn nhanh</span>
          <input
            type="number"
            min={1}
            max={state.batchLimit}
            value={n}
            onChange={(e) => setN(Math.max(1, Math.min(state.batchLimit, Number(e.target.value) || 1)))}
            className="h-8 w-16 rounded-lg border border-line bg-ink-850 px-2 text-center outline-none focus:border-brand/60"
            aria-label="Số dòng muốn chọn"
          />
          <button
            onClick={() => dispatch({ type: "checkFirst", n, skipFlagged })}
            className="rounded-lg bg-white/[0.07] px-2.5 py-1 font-medium hover:bg-white/[0.11]"
          >
            Chọn {n} dòng
          </button>
          <label className="ml-auto flex cursor-pointer items-center gap-1.5 text-[11.5px] text-fg-muted">
            <input type="checkbox" checked={skipFlagged} onChange={(e) => setSkipFlagged(e.target.checked)} className="accent-[#4f7cff]" />
            Bỏ qua dòng cần kiểm tra
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Shuffle className="size-4 text-fg-subtle" />
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as Strategy)}
            className="h-8 flex-1 rounded-lg border border-line bg-ink-850 px-2 outline-none focus:border-brand/60"
            aria-label="Cách phân bổ nick"
          >
            {STRATEGIES.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
          {strategy === "single" && (
            <select
              value={singleRoot}
              onChange={(e) => setRoot(e.target.value)}
              className="h-8 max-w-[180px] rounded-lg border border-line bg-ink-850 px-2 font-mono text-[12px] outline-none focus:border-brand/60"
              aria-label="Miền gốc nhận"
            >
              {pool.map((p) => (
                <option key={p.root.name} value={p.root.name}>{p.root.name} · {p.nick.name}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => dispatch({ type: "strategy", strategy, root: singleRoot })}
            disabled={!checked.length || !pool.length}
            className="rounded-lg border border-line px-2.5 py-1 font-medium text-fg-muted hover:border-line-strong hover:text-fg disabled:opacity-40"
          >
            Phân bổ {checked.length} dòng
          </button>
        </div>
        <p className="-mt-1 text-[11px] text-fg-subtle">Chỉ phân bổ vào {pool.length} miền gốc đã tích chọn và dùng được (nick bật, đủ quyền API, còn hạn mức).</p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          onClick={onPreview}
          disabled={!checked.length || !pool.length}
          className="col-span-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 py-2.5 text-[13px] font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Eye className="size-4" /> Xem trước & chạy {checked.length} dòng
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
