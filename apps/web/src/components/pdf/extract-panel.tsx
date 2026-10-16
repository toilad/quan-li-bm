"use client";

import clsx from "clsx";
import {
  Lock, FileText, Bot, Wand2, PenLine, AlertCircle, AlertTriangle, Save, SkipForward, RotateCcw, Copy, ExternalLink,
  CheckCircle2, Circle, Loader2, HardDrive, Info, Fingerprint, Table2,
} from "lucide-react";
import { FIELD_META, SAVE_STEPS, validate, type FieldKey, type FieldSource, type PdfFile } from "@/lib/pdf-mock";
import { PdfStatusChip } from "./status";
import { canSave, saveBlockers, type QueueDispatch } from "./use-pdf-queue";

const SOURCE: Record<FieldSource, { label: string; icon: typeof Bot; cls: string }> = {
  text: { label: "Lớp chữ PDF", icon: FileText, cls: "text-emerald-300/90" },
  ai: { label: "AI đọc", icon: Bot, cls: "text-sky-300" },
  auto: { label: "Tự sinh từ A", icon: Wand2, cls: "text-violet-300" },
  manual: { label: "Đã sửa tay", icon: PenLine, cls: "text-amber-200" },
  missing: { label: "Thiếu", icon: AlertCircle, cls: "text-rose-300" },
};

export function ExtractPanel({
  file, tab, dispatch, onHover,
}: {
  file: PdfFile | null;
  tab: string;
  dispatch: QueueDispatch;
  onHover: (k: FieldKey | null) => void;
}) {
  if (!file) return <section className="panel p-6 text-[13px] text-fg-subtle">Chưa chọn file.</section>;

  const editable = file.status === "review";
  const issues = file.fields ? validate(file.fields) : {};
  const blockers = saveBlockers(file);

  return (
    <section className="panel flex min-h-0 flex-col">
      <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h2 className="flex items-center gap-2 text-[15px] font-semibold">
            <Table2 className="size-4 text-sky-300" /> Dữ liệu ghi Google Sheet
          </h2>
          <p className="mt-0.5 text-[12px] text-fg-muted">
            Tab <b className="text-fg">{tab}</b> ·{" "}
            {file.sheetRow ? <>đã ghi <b className="text-emerald-300">dòng #{file.sheetRow}</b></> : "sẽ thêm dòng mới (append)"}
          </p>
        </div>
        <PdfStatusChip status={file.status} />
      </header>

      <div className="scroll-thin min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <ColumnStrip file={file} />

        {file.status === "duplicate" && file.duplicateOf && (
          <Notice tone="orange" icon={Copy} title="Phát hiện trùng — không tạo dòng mới">
            {file.duplicateOf.reason}
            {file.duplicateOf.row > 0 && (
              <>
                {" "}với <b>dòng #{file.duplicateOf.row}</b> ({file.duplicateOf.name}).
              </>
            )}
            <div className="mt-2.5 flex gap-2">
              <SmallBtn onClick={() => dispatch({ type: "remove", id: file.id })} icon={SkipForward}>
                Bỏ file này
              </SmallBtn>
              {file.duplicateOf.row > 0 && <SmallBtn icon={ExternalLink}>Mở dòng #{file.duplicateOf.row}</SmallBtn>}
            </div>
          </Notice>
        )}

        {file.status === "failed" && (
          <Notice tone="rose" icon={AlertCircle} title="Xử lý thất bại">
            {file.error}
            <div className="mt-2.5">
              <SmallBtn onClick={() => dispatch({ type: "retry", id: file.id })} icon={RotateCcw}>
                Thử lại file này
              </SmallBtn>
            </div>
          </Notice>
        )}

        {file.local && file.status === "review" && (
          <Notice tone="sky" icon={Info} title="Bản thiết kế chưa đọc nội dung PDF thật">
            Phần trích xuất làm ở giai đoạn 4 (backend). Ở bản này anh có thể nhập tay để thử luồng lưu.
          </Notice>
        )}

        {(file.status === "queued" || file.status === "processing") && (
          <div className="rounded-xl border border-line bg-ink-850/50 p-6 text-center text-[12.5px] text-fg-muted">
            {file.status === "queued" ? "File đang chờ trong hàng đợi." : "Đang trích xuất — dữ liệu sẽ hiện ở đây để anh kiểm tra."}
          </div>
        )}

        {file.fields && (
          <div className="grid grid-cols-2 gap-x-3 gap-y-3.5">
            {FIELD_META.map((m) => {
              const fld = file.fields![m.key];
              const issue = issues[m.key];
              const src = SOURCE[fld.source];
              return (
                <label
                  key={m.key}
                  className={clsx("block", m.wide && "col-span-2")}
                  onMouseEnter={() => onHover(m.key)}
                  onMouseLeave={() => onHover(null)}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[12px] font-medium text-fg-muted">
                      <ColBadge c={m.key} />
                      {m.label}
                    </span>
                    <span className={clsx("inline-flex items-center gap-1 text-[10.5px]", src.cls)}>
                      <src.icon className="size-3" />
                      {src.label}
                      {fld.source === "ai" && fld.confidence !== undefined && ` ${fld.confidence}%`}
                    </span>
                  </div>
                  <input
                    value={fld.value}
                    disabled={!editable}
                    onFocus={() => onHover(m.key)}
                    onBlur={() => onHover(null)}
                    onChange={(e) => dispatch({ type: "edit", id: file.id, key: m.key, value: e.target.value })}
                    placeholder={m.hint || "—"}
                    className={clsx(
                      "h-9 w-full rounded-lg border bg-ink-850/80 px-3 text-[13px] outline-none transition placeholder:text-fg-subtle/60 disabled:cursor-not-allowed disabled:opacity-70",
                      m.key === "J" || m.key === "E" ? "font-mono text-[12.5px]" : "",
                      issue?.level === "error"
                        ? "border-rose-400/50 focus:border-rose-400"
                        : issue?.level === "warn"
                          ? "border-amber-400/45 focus:border-amber-400"
                          : "border-line focus:border-brand/60",
                    )}
                  />
                  {issue && (
                    <span
                      className={clsx(
                        "mt-1 flex items-center gap-1 text-[11px]",
                        issue.level === "error" ? "text-rose-300" : "text-amber-300",
                      )}
                    >
                      {issue.level === "error" ? <AlertCircle className="size-3" /> : <AlertTriangle className="size-3" />}
                      {issue.msg}
                    </span>
                  )}
                </label>
              );
            })}

            {(["B", "C"] as const).map((c) => (
              <div key={c} className="col-span-1">
                <div className="mb-1 flex items-center gap-1.5 text-[12px] font-medium text-fg-subtle">
                  <ColBadge c={c} muted />
                  {c === "B" ? "Tên miền" : "Website HTTPS"}
                </div>
                <div className="flex h-9 items-center gap-2 rounded-lg border border-dashed border-line bg-white/[0.015] px-3 text-[12px] text-fg-subtle">
                  <Lock className="size-3.5 shrink-0" />
                  <span className="truncate" title={c === "B" ? "Module Tạo miền ghi cột này" : "Module SSL + Tạo web ghi cột này"}>
                    Để trống ({c === "B" ? "Tạo miền" : "SSL + web"})
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {file.fields && <DriveStatus file={file} />}
      </div>

      {file.status === "review" && (
        <footer className="border-t border-line px-5 py-4">
          {blockers.missing > 0 && (
            <label className="mb-3 flex cursor-pointer items-start gap-2 text-[12px] text-amber-200/90">
              <input
                type="checkbox"
                checked={!!file.confirmMissing}
                onChange={(e) => dispatch({ type: "confirmMissing", id: file.id, on: e.target.checked })}
                className="mt-0.5 size-4 accent-amber-400"
              />
              Thiếu {blockers.missing} trường — vẫn lưu và để trống các ô đó trên Sheet (không tự điền)
            </label>
          )}
          {blockers.format > 0 && (
            <p className="mb-3 flex items-center gap-1.5 text-[12px] text-rose-300">
              <AlertCircle className="size-3.5" /> Sửa {blockers.format} trường sai định dạng trước khi lưu
            </p>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => dispatch({ type: "save", id: file.id })}
              disabled={!canSave(file)}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand to-brand-2 px-4 py-2.5 text-[13px] font-semibold text-white shadow-[0_10px_24px_-12px_rgb(79_124_255/0.8)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Save className="size-4" /> Xác nhận & lưu vào Sheet + Drive
            </button>
            <button
              onClick={() => dispatch({ type: "remove", id: file.id })}
              className="inline-flex items-center gap-1.5 rounded-xl border border-line px-4 py-2.5 text-[13px] font-medium text-fg-muted hover:border-line-strong hover:text-fg"
            >
              <SkipForward className="size-4" /> Bỏ qua
            </button>
          </div>
        </footer>
      )}
    </section>
  );
}

/** A..L strip showing which columns this module writes, and which it never touches. */
function ColumnStrip({ file }: { file: PdfFile }) {
  const cols = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"];
  const state = (c: string) => {
    if (c === "B" || c === "C") return "locked";
    if (c === "L") return "keep";
    if (c === "K") return file.driveLink ? "ok" : "pending";
    const v = file.fields?.[c as FieldKey]?.value;
    return v ? "ok" : file.fields ? "missing" : "pending";
  };
  const cls = {
    ok: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    missing: "border-rose-400/40 bg-rose-500/10 text-rose-300",
    pending: "border-line bg-white/[0.02] text-fg-subtle",
    locked: "border-dashed border-line bg-transparent text-fg-subtle/60",
    keep: "border-dashed border-line bg-transparent text-fg-subtle/60",
  } as const;
  const title = {
    ok: "Có dữ liệu",
    missing: "Thiếu — để trống",
    pending: "Chưa có",
    locked: "Không ghi — thuộc module khác",
    keep: "Giữ nguyên",
  } as const;

  return (
    <div>
      <div className="mb-1.5 text-[11px] font-medium text-fg-subtle">Các cột module PDF sẽ ghi</div>
      <div className="grid grid-cols-12 gap-1">
        {cols.map((c) => {
          const s = state(c);
          return (
            <div key={c} title={`Cột ${c}: ${title[s]}`} className={clsx("grid h-8 place-items-center rounded-md border font-mono text-[11.5px] font-semibold", cls[s])}>
              {s === "locked" ? <Lock className="size-3" /> : c}
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 text-[10.5px] text-fg-subtle">
        <span>
          <Lock className="mr-0.5 inline size-2.5" /> B, C: không bao giờ ghi
        </span>
        <span>K: link “Xem phôi” sau khi upload</span>
        <span>L: giữ nguyên</span>
      </div>
    </div>
  );
}

function DriveStatus({ file }: { file: PdfFile }) {
  const stepState = (i: number): "done" | "run" | "todo" => {
    if (file.status === "saved") return "done";
    if (file.status !== "saving") return "todo";
    return i < file.step ? "done" : i === file.step ? "run" : "todo";
  };

  return (
    <div className="rounded-xl border border-line bg-ink-850/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          <HardDrive className="size-4 text-sky-300" /> Google Drive · cột K
        </span>
        {file.status === "saved" && (
          <span className="inline-flex items-center gap-1 text-[11px] text-emerald-300">
            <Fingerprint className="size-3" /> md5 khớp bản gốc
          </span>
        )}
      </div>
      <ol className="space-y-2">
        {SAVE_STEPS.map((s, i) => {
          const st = stepState(i);
          return (
            <li key={s} className="flex items-center gap-2.5 text-[12.5px]">
              {st === "done" ? (
                <CheckCircle2 className="size-4 text-emerald-400" />
              ) : st === "run" ? (
                <Loader2 className="size-4 animate-spin text-violet-300" />
              ) : (
                <Circle className="size-4 text-fg-subtle/50" />
              )}
              <span className={st === "todo" ? "text-fg-subtle" : "text-fg"}>{s}</span>
            </li>
          );
        })}
      </ol>
      <div className="mt-3.5 flex items-center justify-between gap-2 border-t border-line pt-3">
        <span className="text-[12px] text-fg-muted">
          <ColBadge c="K" /> Liên kết
        </span>
        {file.driveLink ? (
          <a
            href={file.driveLink}
            onClick={(e) => e.preventDefault()}
            className="inline-flex items-center gap-1.5 rounded-md border border-rose-400/25 bg-rose-500/[0.08] px-2.5 py-1 text-[12px] font-medium text-rose-200 hover:bg-rose-500/15"
          >
            <FileText className="size-3.5" /> Xem phôi <ExternalLink className="size-3" />
          </a>
        ) : (
          <span className="text-[12px] text-fg-subtle">Chưa có — tạo sau khi upload</span>
        )}
      </div>
    </div>
  );
}

function ColBadge({ c, muted }: { c: string; muted?: boolean }) {
  return (
    <span
      className={clsx(
        "inline-grid size-5 place-items-center rounded font-mono text-[10.5px] font-bold",
        muted ? "bg-white/[0.04] text-fg-subtle" : "bg-brand/20 text-sky-200",
      )}
    >
      {c}
    </span>
  );
}

function Notice({
  tone, icon: Icon, title, children,
}: {
  tone: "rose" | "orange" | "sky";
  icon: typeof Info;
  title: string;
  children: React.ReactNode;
}) {
  const cls = {
    rose: "border-rose-400/30 bg-rose-500/[0.08] text-rose-100",
    orange: "border-orange-400/30 bg-orange-500/[0.08] text-orange-100",
    sky: "border-sky-400/25 bg-sky-500/[0.07] text-sky-100",
  }[tone];
  return (
    <div className={clsx("rounded-xl border p-3.5 text-[12.5px] leading-relaxed", cls)}>
      <div className="mb-1 flex items-center gap-1.5 font-semibold">
        <Icon className="size-4" /> {title}
      </div>
      <div className="text-[12px] opacity-90">{children}</div>
    </div>
  );
}

function SmallBtn({ children, icon: Icon, onClick }: { children: React.ReactNode; icon: typeof Info; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.08] px-2.5 py-1 text-[12px] font-medium text-fg hover:bg-white/[0.13]"
    >
      <Icon className="size-3.5" /> {children}
    </button>
  );
}
