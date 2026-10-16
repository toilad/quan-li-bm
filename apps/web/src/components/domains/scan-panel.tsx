"use client";

import { useState } from "react";
import clsx from "clsx";
import { FileSpreadsheet, RefreshCw, ChevronDown, ListFilter, Flag, AlertTriangle, Lock } from "lucide-react";
import { SLUG_RULES, scanSheet, type SlugRule } from "@/lib/domain-mock";
import type { DomainDispatch, DomainState } from "./use-domain-queue";

export function ScanPanel({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const scan = scanSheet();
  const [open, setOpen] = useState(true);
  const flagged = state.rows.filter((r) => r.flags.length);
  const stats = [
    { label: "Tổng dòng", value: scan.total, cls: "text-fg" },
    { label: "Đã có B · bỏ qua", value: scan.withB, cls: "text-fg-muted" },
    { label: "B trống · tạo được", value: scan.rows.length, cls: "text-emerald-300" },
    { label: "Trong đó cần kiểm tra", value: flagged.length, cls: "text-amber-300" },
  ];

  return (
    <section className="panel flex flex-col p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-emerald-500/15 text-emerald-200">
            <FileSpreadsheet className="size-5" />
          </span>
          <div>
            <h2 className="text-[16px] font-semibold">Quét Google Sheet</h2>
            <p className="text-[12.5px] text-fg-muted">
              Tab <b className="text-fg">Phoi US</b> · đọc demo qua Google Sheets API (mô phỏng), đồng bộ 2 phút trước
            </p>
          </div>
        </div>
        <button className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[12.5px] font-medium text-fg-muted hover:border-line-strong hover:text-fg">
          <RefreshCw className="size-3.5" /> Quét lại
        </button>
      </header>

      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-line bg-ink-850/60 px-3.5 py-2.5">
            <div className="text-[11.5px] text-fg-subtle">{s.label}</div>
            <div className={clsx("mt-0.5 text-[22px] font-bold leading-tight", s.cls)}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-fg-subtle">
        <span className="inline-flex items-center gap-1"><ListFilter className="size-3.5" /> Điều kiện:</span>
        <span>Cột B trống</span>
        <span>· Có tên doanh nghiệp (A)</span>
        <span>· Thiếu K / PDF lỗi → đánh dấu kiểm tra, không loại</span>
        <span>· Dòng đủ thông tin xếp trước</span>
      </div>

      <div className="mt-4 rounded-xl border border-line bg-ink-850/50 p-3.5">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-[12.5px] font-semibold">Cách tạo tên miền phụ</span>
          <span className="inline-flex items-center gap-1 rounded-md bg-amber-400/15 px-1.5 py-0.5 text-[10.5px] font-semibold text-amber-300">
            <AlertTriangle className="size-3" /> Chưa chốt — anh chọn
          </span>
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          {(Object.keys(SLUG_RULES) as SlugRule[]).map((k) => (
            <label
              key={k}
              className={clsx(
                "flex cursor-pointer gap-2.5 rounded-lg border px-3 py-2 transition",
                state.rule === k ? "border-brand/50 bg-brand/[0.08]" : "border-line hover:border-line-strong",
              )}
            >
              <input type="radio" name="slug-rule" checked={state.rule === k} onChange={() => dispatch({ type: "rule", rule: k })} className="mt-0.5 accent-[#4f7cff]" />
              <span>
                <span className="block text-[12.5px] font-medium">{SLUG_RULES[k].label}</span>
                <span className="block text-[11px] text-fg-subtle">{SLUG_RULES[k].detail}</span>
              </span>
            </label>
          ))}
        </div>
        <p className="mt-2 flex flex-wrap items-center gap-x-1 text-[11px] text-fg-subtle">
          <Lock className="size-3" /> Cột E chỉ được đọc, không bao giờ bị sửa. Sửa tên từng dòng ở bảng hoặc màn xem trước. Trùng tên → dòng bị chặn, app không tự đổi tên.
        </p>
      </div>

      <button
        onClick={() => setOpen((v) => !v)}
        className="mt-3 flex items-center justify-between rounded-lg px-1 py-1 text-[12.5px] text-fg-muted hover:text-fg"
      >
        <span className="inline-flex items-center gap-1.5">
          <Flag className="size-3.5 text-amber-300" /> {flagged.length} dòng cần kiểm tra (vẫn tạo được miền)
        </span>
        <ChevronDown className={clsx("size-4 transition", open && "rotate-180")} />
      </button>
      {open && (
        <ul className="mt-1 space-y-1.5">
          {flagged.map((r) => (
            <li key={r.row} className="flex items-start justify-between gap-3 rounded-lg bg-white/[0.02] px-3 py-2 text-[12px]">
              <span className="min-w-0">
                <span className="font-medium">{r.company.A}</span> <span className="font-mono text-fg-subtle">#{r.row}</span>
              </span>
              <span className="shrink-0 text-right text-amber-200/80">{r.flags.join(" · ")}</span>
            </li>
          ))}
          {scan.excluded.length > 0 && (
            <li className="px-1 pt-1 text-[11px] text-rose-300">{scan.excluded.length} dòng thiếu tên doanh nghiệp — không tạo được miền.</li>
          )}
        </ul>
      )}
    </section>
  );
}
