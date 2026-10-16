"use client";

import clsx from "clsx";
import { Zap, Play, Pause, RotateCcw, Eye, Layers, Bot, ListChecks } from "lucide-react";
import { SimTag, Toggle } from "@/components/domains/ui";
import type { WebStatus } from "@/lib/web-mock";
import { WEB_STATUS } from "./web-ui";
import { webIssue, type AiProvider, type WebDispatch, type WebState } from "./use-web-queue";

const ORDER: WebStatus[] = ["queued", "running", "done", "failed", "conflict", "idle"];
const PROVIDERS: { key: AiProvider; label: string }[] = [
  { key: "claude", label: "Claude (Anthropic API)" },
  { key: "openai", label: "OpenAI API" },
];

export function WebRunPanel({ state, dispatch, onPreview }: { state: WebState; dispatch: WebDispatch; onPreview: () => void }) {
  const { rows } = state;
  const count = (s: WebStatus) => rows.filter((r) => r.status === s).length;
  const inRun = rows.filter((r) => r.status !== "idle");
  const settled = inRun.filter((r) => ["done", "failed", "conflict"].includes(r.status)).length;
  const pct = inRun.length ? Math.round((settled / inRun.length) * 100) : 0;
  const checked = rows.filter((r) => r.checked && r.status === "idle");
  const startable = checked.filter((r) => !webIssue(r));
  const ready = rows.filter((r) => r.status === "idle" && !webIssue(r));
  const failed = count("failed");
  const active = count("running") + count("queued") > 0;

  return (
    <section className="panel flex flex-col p-5">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Zap className="size-5 text-emerald-300" />
          <h2 className="text-[16px] font-semibold">Lượt dựng web + SSL</h2>
          <SimTag />
        </div>
        <span className="font-mono text-[12px] text-fg-subtle">{settled}/{inRun.length}</span>
      </header>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-300 transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between text-[11.5px] text-fg-subtle">
        <span>{state.paused ? "Tạm dừng — bước đang chạy xong rồi dừng" : active ? "Đang chạy · mỗi hosting 1 site · tối đa 2 hosting song song" : "Rảnh — không tự chạy khi mở trang"}</span>
        <span>{pct}%</span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {ORDER.map((s) => {
          const m = WEB_STATUS[s];
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
            type="number" min={1} max={100} value={state.batchLimit}
            onChange={(e) => dispatch({ type: "batchLimit", n: Math.max(1, Math.min(100, Number(e.target.value) || 1)) })}
            className="h-8 w-16 rounded-lg border border-line bg-ink-850 px-2 text-center outline-none focus:border-brand/60"
            aria-label="Giới hạn số website mỗi lượt"
          />
          <span className="text-[11px] text-fg-subtle">site (app cũ: 30)</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ListChecks className="size-4 text-fg-subtle" />
          <button
            onClick={() => dispatch({ type: "checkAll", rows: ready.map((r) => r.row), on: true })}
            disabled={!ready.length}
            className="rounded-lg bg-white/[0.07] px-2.5 py-1 font-medium hover:bg-white/[0.11] disabled:opacity-40"
          >
            Chọn {ready.length} dòng sẵn sàng
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Bot className="size-4 text-fg-subtle" />
          <select
            value={state.provider}
            onChange={(e) => dispatch({ type: "provider", provider: e.target.value as AiProvider })}
            className="h-8 flex-1 rounded-lg border border-line bg-ink-850 px-2 outline-none focus:border-brand/60"
            aria-label="Nhà cung cấp AI"
          >
            {PROVIDERS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-[11.5px] text-fg-muted">
            <Toggle on={state.fallback} onChange={(on) => dispatch({ type: "fallback", on })} label="Dự phòng nhà cung cấp còn lại" /> Dự phòng
          </label>
        </div>
        <p className="-mt-1 text-[11px] text-fg-subtle">Khoá AI lưu phía server, chọn model ở Cài đặt API. Nội dung luôn qua bước kiểm tra “không bịa” trước khi dựng.</p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          onClick={onPreview}
          disabled={!checked.length}
          className="col-span-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 py-2.5 text-[13px] font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Eye className="size-4" /> Xem trước & chạy {startable.length} site
        </button>
        <button
          onClick={() => dispatch({ type: state.paused ? "resume" : "pause" })}
          disabled={!active && !state.paused}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white/[0.07] px-3 py-2 text-[12.5px] font-semibold hover:bg-white/[0.11] disabled:opacity-40"
        >
          {state.paused ? <Play className="size-4" /> : <Pause className="size-4" />} {state.paused ? "Tiếp tục" : "Tạm dừng"}
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
