"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { FileText, Globe2, MonitorCheck, Play, Pause, RotateCcw, Zap, Lock } from "lucide-react";
import { Ring } from "@/components/ui/charts";
import { COMPANIES } from "@/lib/mock-data";
import { isEligibleForDomain, isEligibleForWebsite, type ModuleKey } from "@/lib/sheet-rules";

type RunState = "running" | "paused" | "idle";

type ModuleCard = {
  key: ModuleKey;
  title: string;
  desc: string;
  rule: string;
  icon: typeof FileText;
  color: string;
  iconCls: string;
  barCls: string;
  unit: string;
};

const CARDS: ModuleCard[] = [
  {
    key: "pdf",
    title: "PDF → Sheets + Drive",
    desc: "Đọc PDF, ghi A, D–J và link “Xem phôi” cột K",
    rule: "Không ghi B, C",
    icon: FileText,
    color: "#7c8cff",
    iconCls: "bg-indigo-500/15 text-indigo-200",
    barCls: "from-indigo-400 to-violet-400",
    unit: "file",
  },
  {
    key: "domain",
    title: "Tạo miền iNET",
    desc: "Dòng có cột B trống → tạo miền → kiểm tra",
    rule: "Chỉ ghi B khi thành công",
    icon: Globe2,
    color: "#34d399",
    iconCls: "bg-emerald-500/15 text-emerald-200",
    barCls: "from-emerald-400 to-teal-300",
    unit: "miền",
  },
  {
    key: "web",
    title: "SSL + Tạo web",
    desc: "Dòng có B, C trống → dựng web → SSL → HTTPS",
    rule: "Chỉ ghi C khi HTTPS chạy",
    icon: MonitorCheck,
    color: "#60a5fa",
    iconCls: "bg-sky-500/15 text-sky-200",
    barCls: "from-sky-400 to-blue-500",
    unit: "web",
  },
];

const failed = (k: ModuleKey) => COMPANIES.filter((c) => c.stages[k] === "error").length;

const INITIAL: Record<ModuleKey, { state: RunState; done: number; total: number; secs: number }> = {
  pdf: { state: "running", done: 34, total: 38, secs: 742 },
  domain: { state: "running", done: 2, total: COMPANIES.filter((c) => isEligibleForDomain(c) && c.stages.pdf === "done").length, secs: 495 },
  web: { state: "paused", done: 2, total: COMPANIES.filter(isEligibleForWebsite).length, secs: 920 },
};

const fmt = (s: number) =>
  [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60].map((n) => String(n).padStart(2, "0")).join(":");

export function ModuleProgress() {
  const [runs, setRuns] = useState(INITIAL);

  // Demo ticker: each module advances only while *it* is running — never triggers another module.
  useEffect(() => {
    const id = setInterval(() => {
      setRuns((prev) => {
        const next = { ...prev };
        (Object.keys(prev) as ModuleKey[]).forEach((k) => {
          const r = prev[k];
          if (r.state !== "running") return;
          const secs = r.secs + 1;
          const done = secs % 4 === 0 ? Math.min(r.total, r.done + 1) : r.done;
          next[k] = { ...r, secs, done, state: done >= r.total ? "idle" : "running" };
        });
        return next;
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const toggle = (k: ModuleKey) =>
    setRuns((p) => ({ ...p, [k]: { ...p[k], state: p[k].state === "running" ? "paused" : "running" } }));

  return (
    <section className="panel flex h-full flex-col p-5">
      <header className="mb-4 flex items-start gap-3">
        <Zap className="mt-0.5 size-5 text-violet-300" />
        <div>
          <h2 className="text-[17px] font-semibold">Tiến trình hệ thống</h2>
          <p className="text-[12.5px] text-fg-muted">3 module độc lập · chạy trên server, đóng trình duyệt vẫn tiếp tục</p>
        </div>
      </header>

      <div className="flex flex-1 flex-col gap-3">
        {CARDS.map((m) => {
          const r = runs[m.key];
          const pct = r.total ? Math.round((r.done / r.total) * 100) : 0;
          const errs = failed(m.key);
          return (
            <article key={m.key} className="rounded-2xl border border-line bg-ink-850/60 p-4">
              <div className="flex items-start gap-3">
                <span className={clsx("grid size-11 shrink-0 place-items-center rounded-xl", m.iconCls)}>
                  <m.icon className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="text-[14px] font-semibold">{m.title}</h3>
                  <p className="mt-0.5 text-[12px] text-fg-muted">{m.desc}</p>
                  <p className="mt-1 inline-flex items-center gap-1 text-[11px] text-fg-subtle">
                    <Lock className="size-3" /> {m.rule}
                  </p>
                </div>
                <div className="relative grid place-items-center">
                  <Ring value={pct} color={m.color} size={58} />
                  <span className="absolute text-[13px] font-bold">{pct}%</span>
                </div>
              </div>

              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className={clsx("h-full rounded-full bg-gradient-to-r transition-[width] duration-500", m.barCls)}
                  style={{ width: `${pct}%` }}
                />
              </div>

              <div className="mt-2.5 flex items-center justify-between text-[12px]">
                <span className="flex items-center gap-2 text-fg-muted">
                  <RunBadge state={r.state} />
                  {r.done}/{r.total} {m.unit}
                  {errs > 0 && <span className="ml-2 text-rose-300">· {errs} lỗi</span>}
                </span>
                <span className="font-mono text-fg-subtle">{fmt(r.secs)}</span>
              </div>

              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => toggle(m.key)}
                  disabled={r.state === "idle" && r.done >= r.total}
                  className={clsx(
                    "inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-40",
                    r.state === "running"
                      ? "bg-white/[0.06] text-fg hover:bg-white/[0.1]"
                      : "bg-gradient-to-r from-brand to-brand-2 text-white hover:brightness-110",
                  )}
                >
                  {r.state === "running" ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
                  {r.state === "running" ? "Tạm dừng" : r.done >= r.total ? "Đã xong lượt" : "Tiếp tục"}
                </button>
                <button
                  disabled={errs === 0}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[12px] font-medium text-fg-muted transition hover:border-line-strong hover:text-fg disabled:opacity-40"
                >
                  <RotateCcw className="size-3.5" /> Thử lại lỗi
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function RunBadge({ state }: { state: RunState }) {
  const map = {
    running: { text: "Đang chạy", cls: "text-sky-300 bg-sky-400/10", dot: "bg-sky-300 animate-pulse-dot" },
    paused: { text: "Tạm dừng", cls: "text-amber-300 bg-amber-400/10", dot: "bg-amber-300" },
    idle: { text: "Rảnh", cls: "text-fg-subtle bg-white/[0.04]", dot: "bg-fg-subtle" },
  }[state];
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[10.5px] font-semibold", map.cls)}>
      <span className={clsx("size-1.5 rounded-full", map.dot)} />
      {map.text}
    </span>
  );
}
