"use client";

import { useState } from "react";
import clsx from "clsx";
import { Zap, Play, Pause, RotateCcw, ListChecks, Shuffle } from "lucide-react";
import { ROW_STATUS, SimTag } from "./ui";
import { previewIssue, type DomainDispatch, type DomainState, type Strategy } from "./use-domain-queue";
import type { RowStatus } from "@/lib/domain-mock";

const ORDER: RowStatus[] = ["queued", "running", "done", "failed", "conflict", "idle"];
const MAX_PER_RUN = 30;

const STRATEGIES: { key: Strategy; label: string }[] = [
  { key: "roundRobin", label: "Xoay vòng đều các nick" },
  { key: "random", label: "Ngẫu nhiên (như app cũ)" },
  { key: "single", label: "Dồn vào 1 nick" },
];

export function RunPanel({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const [n, setN] = useState(10);
  const [strategy, setStrategy] = useState<Strategy>("roundRobin");
  const [nickId, setNickId] = useState(state.nicks[0].id);
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
          {state.paused ? "Tạm dừng — bước đang chạy hoàn tất rồi dừng" : active ? "Đang chạy · mỗi nick tuần tự · tối đa 2 nick song song" : "Rảnh"}
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
          <ListChecks className="size-4 text-fg-subtle" />
          <span className="text-fg-muted">Số dòng</span>
          <input
            type="number"
            min={1}
            max={MAX_PER_RUN}
            value={n}
            onChange={(e) => setN(Math.max(1, Math.min(MAX_PER_RUN, Number(e.target.value) || 1)))}
            className="h-8 w-16 rounded-lg border border-line bg-ink-850 px-2 text-center outline-none focus:border-brand/60"
            aria-label="Số dòng muốn chọn"
          />
          {[5, 10, 30].map((v) => (
            <button key={v} onClick={() => setN(v)} className={clsx("rounded-md px-2 py-1 text-[11.5px]", n === v ? "bg-white/[0.1] text-fg" : "text-fg-subtle hover:text-fg")}>
              {v}
            </button>
          ))}
          <button
            onClick={() => dispatch({ type: "checkFirst", n })}
            className="ml-auto rounded-lg bg-white/[0.07] px-2.5 py-1 font-medium hover:bg-white/[0.11]"
          >
            Chọn {n} dòng
          </button>
        </div>
        <p className="-mt-1 text-[11px] text-fg-subtle">Tối đa {MAX_PER_RUN} dòng/lượt như app cũ · chỉ chọn dòng chưa chạy, không vướng trùng.</p>

        <div className="flex flex-wrap items-center gap-2">
          <Shuffle className="size-4 text-fg-subtle" />
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as Strategy)}
            className="h-8 flex-1 rounded-lg border border-line bg-ink-850 px-2 outline-none focus:border-brand/60"
            aria-label="Cách chia nick"
          >
            {STRATEGIES.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
          {strategy === "single" && (
            <select
              value={nickId}
              onChange={(e) => setNickId(e.target.value)}
              className="h-8 rounded-lg border border-line bg-ink-850 px-2 outline-none focus:border-brand/60"
              aria-label="Nick nhận"
            >
              {state.nicks.filter((x) => x.enabled).map((x) => (
                <option key={x.id} value={x.id}>{x.name}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => dispatch({ type: "strategy", strategy, nickId })}
            disabled={!checked.length}
            className="rounded-lg border border-line px-2.5 py-1 font-medium text-fg-muted hover:border-line-strong hover:text-fg disabled:opacity-40"
          >
            Chia cho {checked.length} dòng
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          onClick={() => dispatch({ type: "start" })}
          disabled={!startable}
          className="col-span-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 py-2.5 text-[13px] font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Play className="size-4" /> Bắt đầu tạo {startable} miền
          {checked.length > startable && <span className="font-normal opacity-80">· {checked.length - startable} dòng bị chặn</span>}
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
