"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  Building2, Search, SlidersHorizontal, ExternalLink, FileText, MoreHorizontal, ChevronLeft, ChevronRight,
  RefreshCw, Globe2, MonitorCheck, X, Hand, Wand2, Eye, RotateCcw, Shuffle,
} from "lucide-react";
import { COMPANIES, type Company } from "@/lib/mock-data";
import { isEligibleForDomain, isEligibleForWebsite } from "@/lib/sheet-rules";
import { StageChip, StageLegend } from "@/components/ui/stage";

type Filter = "all" | "needDomain" | "needWeb" | "complete" | "attention";

const hasIssue = (c: Company) => Object.values(c.stages).some((s) => s === "error" || s === "conflict");

const FILTERS: { key: Filter; label: string; test: (c: Company) => boolean; hint: string }[] = [
  { key: "all", label: "Tất cả", test: () => true, hint: "Mọi dòng trong Sheet" },
  { key: "needDomain", label: "Chờ tạo miền", test: (c) => isEligibleForDomain(c) && c.stages.pdf === "done", hint: "Cột B trống" },
  { key: "needWeb", label: "Chờ tạo web", test: isEligibleForWebsite, hint: "Cột B có miền, cột C trống" },
  { key: "complete", label: "Hoàn tất", test: (c) => !!c.C, hint: "Đã có website HTTPS ở cột C" },
  { key: "attention", label: "Cần xử lý", test: hasIssue, hint: "Lỗi hoặc xung đột ghi Sheet" },
];

const PAGE = 8;

export function CompanyTable() {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [menuRow, setMenuRow] = useState<number | null>(null);

  const rows = useMemo(() => {
    const f = FILTERS.find((x) => x.key === filter)!;
    const q = query.trim().toLowerCase();
    return COMPANIES.filter(f.test).filter(
      (c) => !q || [c.A, c.B, c.J, c.G].some((v) => v.toLowerCase().includes(q)),
    );
  }, [filter, query]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const current = Math.min(page, pages);
  const visible = rows.slice((current - 1) * PAGE, current * PAGE);

  const selection = COMPANIES.filter((c) => selected.has(c.row));
  const canDomain = selection.filter((c) => isEligibleForDomain(c) && c.stages.pdf === "done").length;
  const canWeb = selection.filter(isEligibleForWebsite).length;

  const toggle = (row: number) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(row)) n.delete(row);
      else n.add(row);
      return n;
    });
  const allVisibleSelected = visible.length > 0 && visible.every((c) => selected.has(c.row));
  const toggleAllVisible = () =>
    setSelected((s) => {
      const n = new Set(s);
      visible.forEach((c) => (allVisibleSelected ? n.delete(c.row) : n.add(c.row)));
      return n;
    });

  return (
    <section className="panel flex flex-col p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-brand/15 text-sky-300">
            <Building2 className="size-5" />
          </span>
          <div>
            <h2 className="text-[17px] font-semibold">Doanh nghiệp trong Google Sheet</h2>
            <p className="flex items-center gap-1.5 text-[12.5px] text-fg-muted">
              Tab <b className="font-semibold text-fg">Phoi US</b> · {COMPANIES.length} dòng · đồng bộ 2 phút trước
              <button className="ml-1 inline-flex items-center gap-1 text-sky-300 hover:text-sky-200">
                <RefreshCw className="size-3" /> Đồng bộ
              </button>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex h-10 w-[280px] items-center gap-2 rounded-xl border border-line bg-ink-850/70 px-3 focus-within:border-brand/60">
            <Search className="size-4 text-fg-subtle" />
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Tìm công ty, tên miền, mã số…"
              className="w-full bg-transparent text-[13px] outline-none placeholder:text-fg-subtle"
            />
            {query && (
              <button onClick={() => setQuery("")} aria-label="Xoá tìm kiếm">
                <X className="size-3.5 text-fg-subtle" />
              </button>
            )}
          </label>
          <button className="flex h-10 items-center gap-2 rounded-xl border border-line bg-ink-850/70 px-3.5 text-[13px] font-medium text-fg-muted hover:text-fg">
            <SlidersHorizontal className="size-4" /> Bộ lọc
          </button>
        </div>
      </header>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5 rounded-xl border border-line bg-ink-850/60 p-1">
          {FILTERS.map((f) => {
            const n = COMPANIES.filter(f.test).length;
            return (
              <button
                key={f.key}
                title={f.hint}
                onClick={() => {
                  setFilter(f.key);
                  setPage(1);
                }}
                className={clsx(
                  "rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition",
                  filter === f.key ? "bg-white/[0.08] text-fg shadow-sm" : "text-fg-muted hover:text-fg",
                )}
              >
                {f.label}
                <span
                  className={clsx(
                    "ml-1.5 rounded-md px-1.5 py-px text-[11px]",
                    f.key === "attention" && n > 0 ? "bg-rose-500/15 text-rose-300" : "bg-white/[0.06] text-fg-subtle",
                  )}
                >
                  {n}
                </span>
              </button>
            );
          })}
        </div>
        <StageLegend />
      </div>

      {selection.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-brand/30 bg-brand/10 px-4 py-2.5 text-[13px]">
          <span className="font-semibold">Đã chọn {selection.length} dòng</span>
          <span className="text-fg-subtle">·</span>
          <button
            disabled={!canDomain}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1 font-medium text-emerald-200 hover:bg-emerald-500/25 disabled:opacity-40"
          >
            <Globe2 className="size-3.5" /> Xếp hàng tạo miền ({canDomain} đủ điều kiện)
          </button>
          <button
            disabled={!canWeb}
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500/15 px-3 py-1 font-medium text-sky-200 hover:bg-sky-500/25 disabled:opacity-40"
          >
            <MonitorCheck className="size-3.5" /> Xếp hàng tạo web ({canWeb} đủ điều kiện)
          </button>
          <span className="text-[12px] text-fg-subtle">Dòng không đủ điều kiện sẽ tự bỏ qua</span>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-[12px] text-fg-muted hover:text-fg">
            Bỏ chọn
          </button>
        </div>
      )}

      <div className="scroll-thin mt-3 overflow-x-auto">
        <table className="w-full min-w-[820px] text-left text-[13px]">
          <thead>
            <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-fg-subtle">
              <th className="w-9 py-3 pl-2 pr-2">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={toggleAllVisible}
                  aria-label="Chọn tất cả dòng đang hiển thị"
                  className="size-4 accent-[#4f7cff]"
                />
              </th>
              <th className="py-3 font-medium" title="# là số dòng trong Google Sheet">
                Doanh nghiệp <ColTag c="A" />
              </th>
              <th className="py-3 font-medium">
                Tên miền <ColTag c="B" /> · Website <ColTag c="C" />
              </th>
              <th className="py-3 font-medium">Mẫu web</th>
              <th className="py-3 font-medium">Tiến trình</th>
              <th className="py-3 font-medium">Phôi <ColTag c="K" /></th>
              <th className="w-10 py-3" />
            </tr>
          </thead>
          <tbody>
            {visible.map((c) => (
              <tr
                key={c.row}
                className={clsx(
                  "border-b border-line/60 align-top transition-colors hover:bg-white/[0.025]",
                  selected.has(c.row) && "bg-brand/[0.06]",
                )}
              >
                <td className="py-3 pl-2 pr-2">
                  <input
                    type="checkbox"
                    checked={selected.has(c.row)}
                    onChange={() => toggle(c.row)}
                    aria-label={`Chọn ${c.A}`}
                    className="size-4 accent-[#4f7cff]"
                  />
                </td>
                <td className="max-w-[215px] py-3 pr-3">
                  <div className="truncate font-medium text-fg">{c.A}</div>
                  <div className="mt-0.5 truncate text-[11.5px] text-fg-subtle">
                    <span className="font-mono text-fg-muted">#{c.row}</span> · {c.G}, {c.H} · {c.J}
                  </div>
                  {c.note && (
                    <div className={clsx("mt-1 text-[11.5px]", hasIssue(c) ? "text-rose-300/90" : "text-amber-200/90")}>
                      {c.note}
                    </div>
                  )}
                </td>
                <td className="max-w-[205px] py-3 pr-3">
                  <div className="flex items-center gap-1.5">
                    <ColTag c="B" />
                    {c.B ? (
                      <span title={c.B} className="truncate font-mono text-[12px] text-fg-muted">{c.B}</span>
                    ) : (
                      <Empty />
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-1.5">
                    <ColTag c="C" />
                    {c.C ? (
                      <a
                        href={c.C}
                        onClick={(e) => e.preventDefault()}
                        title={c.C}
                        className="inline-flex min-w-0 items-center gap-1 text-[12px] text-sky-300 underline-offset-2 hover:underline"
                      >
                        <span className="truncate">{c.C}</span>
                        <ExternalLink className="size-3 shrink-0" />
                      </a>
                    ) : (
                      <Empty />
                    )}
                  </div>
                </td>
                <td className="py-3 pr-3">
                  <div className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full" style={{ background: c.template.primary }} />
                    <span title={c.template.name} className="max-w-[112px] truncate text-[12px] text-fg-muted">
                      {c.template.name}
                    </span>
                  </div>
                  <span
                    className={clsx(
                      "mt-1 inline-flex items-center gap-1 text-[10.5px]",
                      c.templateSource === "manual" ? "text-violet-300" : "text-fg-subtle",
                    )}
                  >
                    {c.templateSource === "manual" ? <Hand className="size-3" /> : <Wand2 className="size-3" />}
                    {c.templateSource === "manual" ? "Chọn tay" : "Tự nhận diện"}
                  </span>
                </td>
                <td className="py-3 pr-3">
                  <div className="flex gap-1">
                    <StageChip module="pdf" status={c.stages.pdf} />
                    <StageChip module="domain" status={c.stages.domain} />
                    <StageChip module="web" status={c.stages.web} />
                  </div>
                </td>
                <td className="py-3 pr-3">
                  {c.K ? (
                    <a
                      href={c.K}
                      onClick={(e) => e.preventDefault()}
                      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-rose-400/20 bg-rose-500/[0.08] px-2 py-0.5 text-[12px] text-rose-200 hover:bg-rose-500/15"
                    >
                      <FileText className="size-3.5" /> Xem phôi
                    </a>
                  ) : (
                    <span className="text-[12px] text-fg-subtle">Đang tải lên…</span>
                  )}
                </td>
                <td className="relative py-3 pr-2">
                  <button
                    onClick={() => setMenuRow(menuRow === c.row ? null : c.row)}
                    aria-label="Thao tác"
                    className="grid size-7 place-items-center rounded-lg text-fg-subtle hover:bg-white/[0.06] hover:text-fg"
                  >
                    <MoreHorizontal className="size-4" />
                  </button>
                  {menuRow === c.row && <RowMenu c={c} onClose={() => setMenuRow(null)} />}
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={8}className="py-12 text-center text-fg-subtle">
                  Không có dòng nào khớp bộ lọc.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <footer className="mt-4 flex items-center justify-between text-[12.5px] text-fg-muted">
        <span>
          Hiển thị {rows.length ? (current - 1) * PAGE + 1 : 0}–{Math.min(current * PAGE, rows.length)} / {rows.length} dòng
        </span>
        <div className="flex items-center gap-1">
          <PageBtn disabled={current === 1} onClick={() => setPage(current - 1)} label="Trang trước">
            <ChevronLeft className="size-4" />
          </PageBtn>
          {Array.from({ length: pages }, (_, i) => i + 1).map((p) => (
            <PageBtn key={p} active={p === current} onClick={() => setPage(p)} label={`Trang ${p}`}>
              {p}
            </PageBtn>
          ))}
          <PageBtn disabled={current === pages} onClick={() => setPage(current + 1)} label="Trang sau">
            <ChevronRight className="size-4" />
          </PageBtn>
        </div>
      </footer>
    </section>
  );
}

function ColTag({ c }: { c: string }) {
  return (
    <span className="ml-1 rounded bg-white/[0.06] px-1 py-px font-mono text-[10px] normal-case text-fg-subtle">
      {c}
    </span>
  );
}

function Empty() {
  return <span className="text-[12px] text-fg-subtle/70">— trống</span>;
}

function PageBtn({
  children, onClick, active, disabled, label,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={clsx(
        "grid size-8 place-items-center rounded-lg border text-[12.5px] font-medium transition disabled:opacity-35",
        active
          ? "border-transparent bg-gradient-to-br from-brand to-brand-2 text-white"
          : "border-line text-fg-muted hover:border-line-strong hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function RowMenu({ c, onClose }: { c: Company; onClose: () => void }) {
  const items = [
    { icon: Eye, label: "Xem chi tiết dòng", show: true },
    { icon: FileText, label: "Mở phôi PDF gốc", show: !!c.K },
    { icon: Shuffle, label: "Đổi mẫu web (chọn tay)", show: !c.C },
    { icon: RotateCcw, label: "Thử lại bước lỗi", show: hasIssue(c) },
  ].filter((i) => i.show);

  return (
    <>
      <div className="fixed inset-0 z-20" onClick={onClose} />
      <div className="panel absolute right-2 top-10 z-30 w-56 p-1.5">
        {items.map(({ icon: Icon, label }) => (
          <button
            key={label}
            onClick={onClose}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[13px] text-fg-muted hover:bg-white/[0.05] hover:text-fg"
          >
            <Icon className="size-4" /> {label}
          </button>
        ))}
      </div>
    </>
  );
}
