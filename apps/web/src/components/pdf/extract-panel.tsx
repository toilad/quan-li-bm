"use client";

import clsx from "clsx";
import {
  Lock, FileText, Bot, Wand2, PenLine, AlertCircle, AlertTriangle, Save, SkipForward, RotateCcw, Copy, ExternalLink,
  CheckCircle2, Circle, Loader2, HardDrive, Info, Fingerprint, Table2, ScanSearch, ScanText, Star, Database, XCircle, Hash,
} from "lucide-react";
import {
  DOC_TYPES, FIELD_LABEL, FIELD_META, INDUSTRIES, KNOWN_DOC_TYPES, SAVE_STEPS, fieldHint, hasLeadingZero, templateFor, validate,
  type DocType, type FieldKey, type FieldSource, type IndustryKey, type PdfFile,
} from "@/lib/pdf-mock";
import { API_URL, api, errorText } from "@/lib/api";
import { useState } from "react";
import type { AddressCandidate, Region } from "@/lib/pdf-mock";
import { PdfStatusChip } from "./status";
import { canSave, saveBlockers } from "./use-pdf-queue";
import type { QueueDispatch } from "./use-pdf-backend";
import type { HighlightKey } from "./pdf-preview";

const SOURCE: Record<FieldSource, { label: string; icon: typeof Bot; cls: string }> = {
  text: { label: "Lớp chữ PDF", icon: FileText, cls: "text-emerald-300/90" },
  ai: { label: "AI đọc", icon: Bot, cls: "text-sky-300" },
  ocr: { label: "OCR đọc từ ảnh", icon: ScanText, cls: "text-cyan-300" },
  auto: { label: "Tự sinh từ A", icon: Wand2, cls: "text-violet-300" },
  manual: { label: "Đã sửa tay", icon: PenLine, cls: "text-amber-200" },
  missing: { label: "Thiếu", icon: AlertCircle, cls: "text-rose-300" },
  placeholder: { label: "Số tạm", icon: Hash, cls: "text-amber-300" },
  provisioned: { label: "Nhà cung cấp số", icon: Hash, cls: "text-sky-300" },
};

const ROLE: Record<string, string> = {
  principal: "Trụ sở chính", mailing: "Địa chỉ nhận thư của DN", agent: "Registered agent",
  return_to: "Return to (người nộp hồ sơ)", principal_ca: "Văn phòng tại California",
};

/** The part of the page a value was read from (outlined in red), cut out by the server — compare it with the cell. */
function RegionCrop({ docId, region, alt }: { docId: string; region: Region; alt: string }) {
  const src = `${API_URL}/api/pdf/${docId}/crop?page=${region.page}&box=${region.box.join(",")}&rotation=${region.rotation ?? 0}`;
  return (
    <a href={src} target="_blank" rel="noreferrer" title="Mở vùng ảnh lớn hơn" className="block">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} loading="lazy" className="max-h-16 max-w-full rounded border border-line bg-white object-contain" />
    </a>
  );
}

function Candidates({ file, dispatch, editable }: { file: PdfFile; dispatch: QueueDispatch; editable: boolean }) {
  const list = file.candidates ?? [];
  if (!list.length) return null;
  return (
    <div className="col-span-2 rounded-xl border border-sky-400/25 bg-sky-500/[0.05] p-3">
      <div className="text-[12px] font-semibold text-sky-200">Địa chỉ khác in trên phôi — chưa dùng cho F–I</div>
      <p className="mt-0.5 text-[11px] leading-snug text-fg-subtle">
        Không phải địa chỉ doanh nghiệp tự khai (registered agent, “Return to”, văn phòng khác). App không tự dùng; anh chỉ chọn khi
        chắc đây là địa chỉ cần điền.
      </p>
      {list.map((c: AddressCandidate, i: number) => (
        <div key={i} className="mt-2.5 flex flex-wrap items-start gap-3 border-t border-sky-400/15 pt-2.5">
          {c.region && <RegionCrop docId={file.id} region={c.region} alt={c.label} />}
          <div className="min-w-0 flex-1">
            <div className="text-[10.5px] font-semibold uppercase tracking-wide text-sky-300">{ROLE[c.role] ?? c.role} · {c.label}</div>
            <div className="text-[13px]">{[c.street, c.city, `${c.state} ${c.zip}`.trim()].filter(Boolean).join(", ")}</div>
            {c.region && <div className="text-[10.5px] text-fg-subtle">Trang {c.region.page}{c.confidence !== undefined && ` · OCR ${c.confidence}%`}</div>}
            {c.suspects?.map((x, j) => (
              <div key={j} className="mt-1 flex items-start gap-1 text-[11px] text-amber-200"><AlertTriangle className="mt-px size-3 shrink-0" />{x.message}</div>
            ))}
          </div>
          {editable && (
            <button type="button" onClick={() => dispatch({ type: "useCandidate", id: file.id, index: i })}
              className="rounded-md border border-sky-400/40 px-2.5 py-1 text-[11.5px] font-medium text-sky-100 hover:bg-sky-500/15">
              Dùng cho F–I
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

const PHONE_SOURCE: Record<string, { label: string; cls: string }> = {
  source_pdf: { label: "Số in trên PDF", cls: "text-emerald-300" },
  provisioned: { label: "Số cấp từ nhà cung cấp của anh", cls: "text-sky-300" },
  needs_setup: { label: "Chưa có số — cần cấp", cls: "text-amber-300" },
  manual: { label: "Anh nhập tay", cls: "text-amber-200" },
  placeholder: { label: "Số TẠM đúng mã vùng bang (555-01xx, không phải số của ai) — anh thay sau", cls: "text-amber-300" },
};

type PhoneOption = { number: string; display: string; in_use?: boolean; problems?: string[]; locality?: string; cost?: boolean };
type PhoneOptions = { state: string; provider: string | null; owned: PhoneOption[]; available: PhoneOption[]; message: string };

/** No number on the PDF: one of the owner's own numbers with the state's area code — never a made-up one. */
function PhoneSetup({ file, dispatch, editable }: { file: PdfFile; dispatch: QueueDispatch; editable: boolean }) {
  const [opts, setOpts] = useState<PhoneOptions | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const load = async () => {
    setBusy(true); setErr("");
    try { setOpts(await api.get<PhoneOptions>(`/api/pdf/${file.id}/phone`)); } catch (e) { setErr(errorText(e)); }
    setBusy(false);
  };
  const buy = (o: PhoneOption) => {
    const ok = window.confirm(`Mua số ${o.display} là bước CÓ PHÍ trên tài khoản ${opts?.provider} của anh.\n` +
      "Cần mở “Mua số điện thoại (có phí)” ở Cài đặt › Ghi thật trước; mua xong app tự khoá lại.\nAnh xác nhận mua số này?");
    if (ok) dispatch({ type: "phoneAssign", id: file.id, number: o.number, buy: true });
  };
  const usable = (opts?.owned ?? []).filter((o) => !o.in_use && !o.problems?.length);
  return (
    <div className="mt-1 rounded-lg border border-amber-400/30 bg-amber-500/[0.05] p-2.5 text-[11.5px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-amber-100">Phôi không có số (đang dùng số tạm nếu có). Cấp số thật có mã vùng đúng bang của doanh nghiệp từ nhà cung cấp của anh — không tự điền số.{opts?.state && ` Bang: ${opts.state} (theo ${(opts as PhoneOptions & { state_from?: string }).state_from}).`}</span>
        {editable && (
          <button type="button" onClick={load} disabled={busy}
            className="shrink-0 rounded border border-amber-400/40 px-2 py-0.5 text-[11px] text-amber-100 hover:bg-amber-500/15 disabled:opacity-60">
            {busy ? "Đang tìm…" : "Tìm số (miễn phí)"}
          </button>
        )}
      </div>
      {err && <div className="mt-1 text-rose-300">{err}</div>}
      {opts && (
        <div className="mt-2 space-y-1.5">
          {opts.message && <div className="text-amber-200">{opts.message}</div>}
          {usable.map((o) => (
            <div key={o.number} className="flex items-center justify-between gap-2">
              <span className="font-mono">{o.display} <span className="font-sans text-fg-subtle">· đã có trong tài khoản (không tốn phí)</span></span>
              <button type="button" onClick={() => dispatch({ type: "phoneAssign", id: file.id, number: o.number, buy: false })}
                className="rounded border border-sky-400/40 px-2 py-0.5 text-[11px] text-sky-100 hover:bg-sky-500/15">Dùng số này</button>
            </div>
          ))}
          {(opts.owned ?? []).filter((o) => o.in_use || o.problems?.length).map((o) => (
            <div key={o.number} className="text-fg-subtle"><span className="font-mono">{o.display}</span> · {o.in_use ? "đã dùng cho doanh nghiệp khác" : o.problems?.[0]}</div>
          ))}
          {(opts.available ?? []).map((o) => (
            <div key={o.number} className="flex items-center justify-between gap-2">
              <span className="font-mono">{o.display} <span className="font-sans text-fg-subtle">· {o.locality} · đang bán (CÓ PHÍ)</span></span>
              <button type="button" onClick={() => buy(o)}
                className="rounded border border-rose-400/40 px-2 py-0.5 text-[11px] text-rose-100 hover:bg-rose-500/15">Mua số này…</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type SheetMatch = {
  status: "new" | "same_name" | "name_differs" | "ambiguous" | "no_key"; pdf_name: string; j: string; h: string;
  name_verified: boolean; why: string; rows: { row: number; A: string; B: string; C: string }[]; evidence?: Region | null;
};

/** Column A = the legal name verified on the PDF: compare with the Sheet row of the same number + state (read-only);
 *  a different name is rewritten in that one cell only after the owner confirms. */
function SheetMatchBox({ file, editable }: { file: PdfFile; editable: boolean }) {
  const [m, setM] = useState<SheetMatch | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const load = async () => {
    setBusy(true); setMsg("");
    try { setM(await api.get<SheetMatch>(`/api/pdf/${file.id}/sheet-match`)); } catch (e) { setMsg(errorText(e)); }
    setBusy(false);
  };
  const rename = async (row: number, old: string) => {
    if (!m) return;
    if (!window.confirm(`Đổi cột A dòng ${row} trên Google Sheet:\n\n  Cũ:  ${old}\n  Mới: ${m.pdf_name}\n\n` +
      "Chỉ ô A của dòng này thay đổi (B–K giữ nguyên). Anh xác nhận tên mới đúng như trên PDF?")) return;
    setBusy(true);
    try {
      await api.post(`/api/pdf/${file.id}/rename`, { row, expected_old: old, confirm: true });
      setMsg(`Đã cập nhật A${row} thành “${m.pdf_name}” (đã ghi nhật ký tên cũ).`);
      setM(await api.get<SheetMatch>(`/api/pdf/${file.id}/sheet-match`));
    } catch (e) { setMsg(errorText(e)); }
    setBusy(false);
  };
  return (
    <div className="col-span-2 rounded-xl border border-violet-400/25 bg-violet-500/[0.05] p-3 text-[12px]">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-violet-200">Đối chiếu tên với Google Sheet (theo mã J + bang H)</span>
        <button type="button" onClick={load} disabled={busy}
          className="rounded border border-violet-400/40 px-2 py-0.5 text-[11px] text-violet-100 hover:bg-violet-500/15 disabled:opacity-60">
          {busy ? "Đang đọc…" : "Đối chiếu (chỉ đọc)"}
        </button>
      </div>
      {msg && <div className="mt-1.5 text-sky-200">{msg}</div>}
      {m && (
        <div className="mt-2 space-y-1.5">
          {m.status === "no_key" && <div className="text-amber-200">{m.why}</div>}
          {m.status === "new" && <div className="text-fg-muted">Chưa có dòng nào cùng mã {m.j} ({m.h}) — khi lưu sẽ thêm dòng mới với A = “{m.pdf_name}”.</div>}
          {m.status === "same_name" && <div className="text-emerald-300">Đã có ở dòng {m.rows[0].row}, tên khớp với PDF — không cần cập nhật.</div>}
          {m.status === "ambiguous" && (
            <div className="text-amber-200">Sheet có {m.rows.length} dòng cùng mã {m.j} ({m.h}): {m.rows.map((r) => `dòng ${r.row} “${r.A}”`).join(", ")} — anh xử lý tay, app không chọn hộ.</div>
          )}
          {m.status === "name_differs" && m.rows[0] && (
            <>
              <div>Dòng <b>{m.rows[0].row}</b> (cùng mã {m.j}, bang {m.h}) đang ghi tên khác PDF:</div>
              <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
                <span className="text-fg-subtle">Cột A hiện tại</span><span className="font-medium text-rose-200">{m.rows[0].A || "(trống)"}</span>
                <span className="text-fg-subtle">Tên trên PDF</span><span className="font-medium text-emerald-200">{m.pdf_name}</span>
              </div>
              {m.evidence && <RegionCrop docId={file.id} region={m.evidence} alt="Tên công ty trên phôi" />}
              {!m.name_verified ? (
                <div className="text-amber-200">{m.why}</div>
              ) : editable && (
                <button type="button" onClick={() => rename(m.rows[0].row, m.rows[0].A)} disabled={busy}
                  className="rounded-md border border-violet-400/50 px-2.5 py-1 text-[11.5px] font-medium text-violet-100 hover:bg-violet-500/15 disabled:opacity-60">
                  Cập nhật tên dòng {m.rows[0].row}…
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ScanFacts({ file }: { file: PdfFile }) {
  const s = file.scan;
  if (!s?.version && !s?.warning && !s?.note) return null;
  const facts = [
    s.version && `Mẫu ${s.version}${s.versionVerified === false ? " (chưa kiểm chứng)" : ""}`,
    s.pagesRead && `đọc ${s.pagesRead} trang`,
    s.filedDate && `ngày nộp ${s.filedDate}`,
    (s.formationState || s.formationDate) && `thành lập ${[s.formationState, s.formationDate].filter(Boolean).join(" · ")} (không ghi vào Sheet)`,
  ].filter(Boolean);
  return (
    <div className="col-span-2 space-y-1 rounded-lg border border-line bg-ink-850/50 px-3 py-2 text-[11.5px] text-fg-muted">
      {facts.length > 0 && <div>{facts.join(" · ")}</div>}
      {s.warning && <div className="flex items-start gap-1 text-amber-300"><AlertTriangle className="mt-px size-3 shrink-0" />{s.warning}</div>}
      {s.note && <div className="flex items-start gap-1 text-sky-200"><Info className="mt-px size-3 shrink-0" />{s.note}</div>}
    </div>
  );
}

const list = (keys: FieldKey[]) => keys.map((k) => `${k} (${FIELD_LABEL[k]})`).join(", ");

export function ExtractPanel({
  file, tab, dispatch, onHover,
}: {
  file: PdfFile | null;
  tab: string;
  dispatch: QueueDispatch;
  onHover: (k: HighlightKey) => void;
}) {
  if (!file) return <section className="panel p-6 text-[13px] text-fg-subtle">Chưa chọn file.</section>;

  const editable = file.status === "review";
  const issues = file.fields ? validate(file.fields, file.docType) : {};
  const b = saveBlockers(file);
  const awaitingType = file.docType === "unknown" && !file.local;

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
        {(file.detection || file.docType !== "unknown") && <DocTypeCard file={file} dispatch={dispatch} editable={editable} />}

        <ColumnStrip file={file} />

        {file.status === "duplicate" && file.duplicateOf && (
          <Notice tone="orange" icon={Copy} title="Phát hiện trùng — không tạo dòng mới, không upload Drive">
            {file.duplicateOf.reason}
            {file.duplicateOf.row > 0 && <> với <b>dòng #{file.duplicateOf.row}</b> ({file.duplicateOf.name}).</>}
            <div className="mt-2.5 flex gap-2">
              <SmallBtn onClick={() => dispatch({ type: "remove", id: file.id })} icon={SkipForward}>Bỏ file này</SmallBtn>
              {file.duplicateOf.row > 0 && <SmallBtn icon={ExternalLink}>Mở dòng #{file.duplicateOf.row}</SmallBtn>}
            </div>
          </Notice>
        )}

        {file.status === "failed" && (
          <Notice tone="rose" icon={AlertCircle} title={file.failedAt === "sheet" ? "Ghi Google Sheet thất bại" : "Xử lý thất bại"}>
            {file.error}
            {file.failedAt === "sheet" && file.driveFileId && (
              <div className="mt-2 flex items-center gap-1.5 font-mono text-[11px] text-rose-100/80">
                <HardDrive className="size-3.5" /> Drive ID đã lưu: {file.driveFileId}
              </div>
            )}
            <div className="mt-2.5">
              <SmallBtn onClick={() => dispatch({ type: "retry", id: file.id })} icon={RotateCcw}>
                {file.failedAt === "sheet" ? "Ghi lại Sheet (dùng file Drive đã có)" : "Thử lại file này"}
              </SmallBtn>
            </div>
          </Notice>
        )}

        {file.local && file.status === "review" && (
          <Notice tone="sky" icon={Info} title="Bản thiết kế chưa đọc nội dung PDF thật">
            Nhận diện loại phôi và trích xuất làm ở giai đoạn 4 (backend). Ở bản này anh chọn loại phôi và nhập tay để thử luồng lưu.
          </Notice>
        )}

        {file.needsAi && (
          <Notice tone="sky" icon={Info} title={file.aiRunning ? "Bản scan — đang đọc bằng OCR trên máy (miễn phí)…" : "Bản scan — chưa đọc được"}>
            PDF không có lớp chữ. App đọc chữ trong ảnh bằng OCR chạy trên máy (California LLC-1, LLC-5); mọi ô đọc bằng OCR phải được anh đối chiếu với phôi trước khi lưu.
            {file.error && <span className="mt-1 block text-rose-200">{file.error}</span>}
            <div className="mt-2.5">
              <SmallBtn onClick={() => dispatch({ type: "aiRead", id: file.id })} icon={RotateCcw}>
                {file.aiRunning ? "Đang đọc…" : "AI đọc phôi"}
              </SmallBtn>
            </div>
          </Notice>
        )}

        {(file.status === "queued" || file.status === "processing") && (
          <div className="rounded-xl border border-line bg-ink-850/50 p-6 text-center text-[12.5px] text-fg-muted">
            {file.status === "queued" ? "File đang chờ trong hàng đợi." : "Đang nhận diện loại phôi và trích xuất — dữ liệu sẽ hiện ở đây để anh kiểm tra."}
          </div>
        )}

        {awaitingType && file.status === "review" && (
          <div className="rounded-xl border border-dashed border-rose-400/40 bg-rose-500/[0.05] p-5 text-center text-[12.5px] text-rose-100/90">
            Chưa đọc dữ liệu vì không chắc loại phôi. Chọn đúng loại ở trên để đọc lại theo mẫu tương ứng — app không đoán bừa.
          </div>
        )}

        {file.fields && !awaitingType && (
          <div className="grid grid-cols-2 gap-x-3 gap-y-3.5">
            <ScanFacts file={file} />
            {FIELD_META.map((m) => {
              const fld = file.fields![m.key];
              const issue = issues[m.key];
              // a source this screen does not know yet must never break the page
              const src = SOURCE[fld.source] ?? { label: String(fld.source || "—"), icon: Info, cls: "text-fg-subtle" };
              const origin = DOC_TYPES[file.docType].origin[m.key];
              const keepZero = (m.key === "I" || m.key === "J") && !issue && hasLeadingZero(fld.value);
              return (
                <div
                  key={m.key}
                  className={clsx("block", m.wide && "col-span-2")}
                  onMouseEnter={() => onHover(m.key)}
                  onMouseLeave={() => onHover(null)}
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-1.5 text-[12px] font-medium text-fg-muted">
                      <ColBadge c={m.key} />
                      <span className="truncate">{m.label}</span>
                      {m.critical && (
                        <span title="Trường quan trọng: bắt buộc có và phải đối chiếu kỹ" className="inline-flex shrink-0 items-center gap-0.5 rounded bg-amber-400/15 px-1 text-[10px] font-semibold text-amber-300">
                          <Star className="size-2.5" /> Quan trọng
                        </span>
                      )}
                    </span>
                    <span className={clsx("inline-flex shrink-0 items-center gap-1 text-[10.5px]", src.cls)}>
                      <src.icon className="size-3" />
                      {src.label}
                      {(fld.source === "ai" || fld.source === "ocr") && fld.confidence !== undefined && ` ${fld.confidence}%`}
                    </span>
                  </div>
                  <input
                    value={fld.value}
                    disabled={!editable}
                    inputMode="text"
                    onFocus={() => onHover(m.key)}
                    onBlur={() => onHover(null)}
                    onChange={(e) => dispatch({ type: "edit", id: file.id, key: m.key, value: e.target.value })}
                    placeholder={fieldHint(m.key, file.docType) || "—"}
                    className={clsx(
                      "h-9 w-full rounded-lg border bg-ink-850/80 px-3 text-[13px] outline-none transition placeholder:text-fg-subtle/60 disabled:cursor-not-allowed disabled:opacity-70",
                      ["E", "I", "J"].includes(m.key) && "font-mono text-[12.5px]",
                      issue?.level === "error"
                        ? "border-rose-400/50 focus:border-rose-400"
                        : issue?.level === "warn"
                          ? "border-amber-400/45 focus:border-amber-400"
                          : "border-line focus:border-brand/60",
                    )}
                  />
                  <div className="mt-1 space-y-0.5">
                    {issue ? (
                      <span className={clsx("flex items-start gap-1 text-[11px] leading-snug", issue.level === "error" ? "text-rose-300" : "text-amber-300")}>
                        {issue.level === "error" ? <AlertCircle className="mt-px size-3 shrink-0" /> : <AlertTriangle className="mt-px size-3 shrink-0" />}
                        {issue.msg}
                      </span>
                    ) : keepZero ? (
                      <span className="flex items-center gap-1 text-[11px] text-emerald-300/80">
                        <Hash className="size-3" /> Lưu dạng văn bản · giữ nguyên số 0
                      </span>
                    ) : fld.note && fld.source !== "manual" ? (
                      <span className="flex items-center gap-1 text-[11px] text-fg-subtle">
                        <Info className="size-3 shrink-0" /> {fld.note}
                      </span>
                    ) : null}
                    {origin && m.key !== "E" && <span className="block text-[10.5px] text-fg-subtle/80">trên phôi: {origin}</span>}
                    {fld.suspects?.map((x, i) => (
                      <div key={i} className="flex items-start gap-1.5 rounded-md border border-amber-400/30 bg-amber-500/[0.06] px-2 py-1 text-[11px] text-amber-200">
                        <AlertTriangle className="mt-px size-3 shrink-0" />
                        <span className="flex-1">{x.message}</span>
                        {x.suggestion && editable && (
                          <button type="button" onClick={() => dispatch({ type: "edit", id: file.id, key: m.key, value: x.suggestion })}
                            className="shrink-0 rounded border border-amber-400/40 px-1.5 text-[10.5px] hover:bg-amber-500/15" title={x.suggestion}>
                            Dùng gợi ý
                          </button>
                        )}
                      </div>
                    ))}
                    {m.key === "D" && fld.phone_source && (
                      <span className={clsx("block text-[10.5px]", PHONE_SOURCE[fld.phone_source]?.cls)}>
                        Nguồn số: {PHONE_SOURCE[fld.phone_source]?.label ?? fld.phone_source}
                        {fld.phone_source === "provisioned" && !fld.verified_active && " · chưa xác minh đang hoạt động"}
                      </span>
                    )}
                    {m.key === "D" && (fld.phone_source === "placeholder" || (!fld.value && (fld.phone_source ?? "needs_setup") === "needs_setup")) && file.fields && (
                      <PhoneSetup file={file} dispatch={dispatch} editable={editable} />
                    )}
                    {fld.region && fld.value && (
                      <div className="flex items-end gap-2 pt-0.5">
                        <RegionCrop docId={file.id} region={fld.region} alt={`Vùng đọc ô ${m.key}`} />
                        <span className="text-[10.5px] text-fg-subtle">Trang {fld.region.page}</span>
                      </div>
                    )}
                    {fld.value && m.key !== "E" && (
                      <label className={clsx("inline-flex items-center gap-1.5 text-[11px]",
                        fld.checked ? "text-emerald-300" : fld.source === "ocr" || fld.source === "ai" ? "text-amber-200" : "text-fg-subtle")}>
                        <input type="checkbox" checked={!!fld.checked} disabled={!editable}
                          onChange={(e) => dispatch({ type: "check", id: file.id, key: m.key, on: e.target.checked })} />
                        {fld.checked ? "Đã kiểm tra với ảnh" : fld.source === "ocr" || fld.source === "ai" ? "Chưa kiểm tra — bắt buộc trước khi lưu" : "Chưa kiểm tra"}
                      </label>
                    )}
                  </div>
                </div>
              );
            })}
            <Candidates file={file} dispatch={dispatch} editable={editable} />
            <SheetMatchBox file={file} editable={editable} />

            {(["B", "C"] as const).map((c) => (
              <div key={c}>
                <div className="mb-1 flex items-center gap-1.5 text-[12px] font-medium text-fg-subtle">
                  <ColBadge c={c} muted />
                  {c === "B" ? "Tên miền" : "Website HTTPS"}
                </div>
                <div
                  title={c === "B" ? "Module Tạo miền ghi cột này" : "Module SSL + Tạo web ghi cột này"}
                  className="flex h-9 items-center gap-2 rounded-lg border border-dashed border-line bg-white/[0.015] px-3 text-[12px] text-fg-subtle"
                >
                  <Lock className="size-3.5 shrink-0" />
                  <span className="truncate">Để trống ({c === "B" ? "Tạo miền" : "SSL + web"})</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {file.industry && !awaitingType && <IndustryCard file={file} dispatch={dispatch} editable={editable} onHover={onHover} />}

        {file.br && <BrExtraCard file={file} dispatch={dispatch} />}

        {file.fields && !awaitingType && <DriveStatus file={file} />}
      </div>

      {file.status === "review" && (
        <footer className="space-y-2.5 border-t border-line px-5 py-4 text-[12px]">
          {b.unknownType && <Blocker>Chưa xác định loại phôi — chọn loại trước khi lưu</Blocker>}
          {b.criticalMissing.length > 0 && !awaitingType && (
            <Blocker>Thiếu trường quan trọng {list(b.criticalMissing)} — không thể lưu, nhập theo đúng phôi</Blocker>
          )}
          {b.format.length > 0 && <Blocker>Sai định dạng: {list(b.format)} — sửa trước khi lưu</Blocker>}
          {b.unchecked.length > 0 && (
            <Blocker>
              Có nhiều cách đọc: {list(b.unchecked)} — xem vùng ảnh bên cạnh rồi sửa ô hoặc bấm “Dùng gợi ý”.
            </Blocker>
          )}

          {b.needCriticalCheck && !b.unknownType && (
            <label className="flex cursor-pointer items-start gap-2 text-sky-100/90">
              <input
                type="checkbox"
                checked={!!file.criticalChecked}
                onChange={(e) => dispatch({ type: "criticalChecked", id: file.id, on: e.target.checked })}
                className="mt-0.5 size-4 accent-[#4f7cff]"
              />
              <span>
                Đã đối chiếu <b>tên doanh nghiệp (A)</b> và <b>mã đăng ký (J)</b> với PDF gốc — các trường này do AI đọc từ bản scan
              </span>
            </label>
          )}
          {b.missing.length > 0 && (
            <label className="flex cursor-pointer items-start gap-2 text-amber-200/90">
              <input
                type="checkbox"
                checked={!!file.confirmMissing}
                onChange={(e) => dispatch({ type: "confirmMissing", id: file.id, on: e.target.checked })}
                className="mt-0.5 size-4 accent-amber-400"
              />
              <span>
                Phôi không có: <b>{list(b.missing)}</b>. Đồng ý để trống các ô này trên Sheet (không tự điền).
              </span>
            </label>
          )}

          <div className="flex gap-2 pt-1">
            <button
              onClick={() => dispatch({ type: "save", id: file.id })}
              disabled={!canSave(file)}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand to-brand-2 px-4 py-2.5 text-[13px] font-semibold text-white shadow-[0_10px_24px_-12px_rgb(79_124_255/0.8)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Save className="size-4" /> Xác nhận & lưu (Drive → Sheet)
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

function DocTypeCard({ file, dispatch, editable }: { file: PdfFile; dispatch: QueueDispatch; editable: boolean }) {
  const meta = DOC_TYPES[file.docType];
  const det = file.detection;
  const conf = det?.confidence ?? 0;
  const unknown = file.docType === "unknown";
  return (
    <div className={clsx("rounded-xl border p-3.5", unknown ? "border-rose-400/35 bg-rose-500/[0.06]" : "border-line bg-ink-850/50")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[12px] font-medium text-fg-muted">
            <ScanSearch className="size-4 text-sky-300" /> Loại phôi
            <span className={clsx("rounded border px-1.5 text-[10.5px] font-bold", meta.tagCls)}>{meta.short}</span>
          </div>
          <div className="mt-1 text-[14px] font-semibold">{meta.label}</div>
          <div className="text-[11.5px] text-fg-subtle">{meta.form}</div>
        </div>
        <select
          value={file.docType}
          disabled={!editable}
          onChange={(e) => dispatch({ type: "docType", id: file.id, docType: e.target.value as DocType })}
          aria-label="Đổi loại phôi"
          className="shrink-0 rounded-lg border border-line bg-ink-850 px-2 py-1 text-[12px] outline-none focus:border-brand/60 disabled:opacity-60"
        >
          {unknown && <option value="unknown">Chọn loại…</option>}
          {KNOWN_DOC_TYPES.map((t) => (
            <option key={t} value={t}>{DOC_TYPES[t].label}</option>
          ))}
        </select>
      </div>
      {det && (
        <div className="mt-2.5">
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className={clsx("h-full rounded-full", conf >= 90 ? "bg-emerald-400" : conf >= 70 ? "bg-amber-400" : "bg-rose-400")}
                style={{ width: `${conf}%` }}
              />
            </div>
            <span className="font-mono text-[11px] text-fg-muted">{det.manual ? "thủ công" : `${conf}%`}</span>
          </div>
          <p className="mt-1.5 text-[11.5px] text-fg-muted">{det.reason}</p>
        </div>
      )}
    </div>
  );
}

function IndustryCard({
  file, dispatch, editable, onHover,
}: {
  file: PdfFile;
  dispatch: QueueDispatch;
  editable: boolean;
  onHover: (k: HighlightKey) => void;
}) {
  const ind = file.industry!;
  const tpl = templateFor(ind);
  const source = { doc: "Đọc từ phôi (CNAE)", name: "Suy từ tên công ty", manual: "Đã chọn tay" }[ind.source];
  const badge = {
    doc: { text: "Đã xác minh trên phôi", cls: "bg-emerald-400/10 text-emerald-300" },
    name: { text: "Gợi ý · chưa xác minh", cls: "bg-amber-400/15 text-amber-300" },
    manual: { text: "Anh đã chọn", cls: "bg-sky-400/10 text-sky-300" },
  }[ind.source];
  return (
    <div
      className="rounded-xl border border-line bg-ink-850/50 p-4"
      onMouseEnter={() => ind.source === "doc" && onHover("industry")}
      onMouseLeave={() => onHover(null)}
    >
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          <Database className="size-4 text-violet-300" /> Ngành nghề
          <span className={clsx("rounded-md px-1.5 py-0.5 text-[10.5px] font-semibold", badge.cls)}>{badge.text}</span>
        </span>
        <span className="text-[10.5px] text-fg-subtle">Lưu database · không ghi Sheet</span>
      </div>
      {ind.source === "name" && (
        <p className="mb-2.5 text-[11.5px] text-amber-200/80">
          Phôi không ghi ngành nghề — đây chỉ là gợi ý từ tên công ty. Chọn lại nếu chưa đúng; lưu kèm trạng thái “chưa xác minh”.
        </p>
      )}
      {ind.source === "doc" && (
        <div className="mb-2.5 rounded-lg bg-white/[0.03] px-3 py-2 text-[12px]">
          <span className="font-mono text-sky-200">{ind.code}</span> <span className="text-fg-muted">· {ind.raw}</span>
        </div>
      )}
      <div className="flex items-center justify-between gap-3">
        <select
          value={ind.category}
          disabled={!editable}
          onChange={(e) => dispatch({ type: "industry", id: file.id, category: e.target.value as IndustryKey })}
          className="min-w-0 flex-1 rounded-lg border border-line bg-ink-850 px-2 py-1.5 text-[12.5px] outline-none focus:border-brand/60 disabled:opacity-70"
          aria-label="Nhóm ngành"
        >
          {(Object.keys(INDUSTRIES) as IndustryKey[]).map((k) => (
            <option key={k} value={k}>{INDUSTRIES[k].label}</option>
          ))}
        </select>
        <span className="text-[11px] text-fg-subtle">{source}</span>
      </div>
      <div className="mt-3 flex items-center gap-2.5 border-t border-line pt-3 text-[12px]">
        <span className="size-3 shrink-0 rounded-full" style={{ background: tpl.primary }} />
        <span className="text-fg-muted">Mẫu web gợi ý:</span>
        <span className="truncate font-semibold">{tpl.name}</span>
        <span className="ml-auto shrink-0 text-[10.5px] text-fg-subtle">dùng ở bước SSL + Tạo web</span>
      </div>
    </div>
  );
}

/** Other comprovante boxes: not sheet columns, kept in the database exactly as printed. */
function BrExtraCard({ file, dispatch }: { file: PdfFile; dispatch: QueueDispatch }) {
  const r = file.br!;
  const rows: [string, string][] = [
    ["Nome de fantasia", r.fantasia],
    ["Natureza jurídica", r.natureza],
    ["Porte", r.porte],
    ["Data de abertura", r.abertura],
    ["CNAE secundários", r.cnaeSecundarias.join(" · ") || "Não informada"],
    ["Endereço eletrônico", r.email || "— (phôi để trống)"],
    ["Logradouro / Número / Complemento", `${r.logradouro} / ${r.numero} / ${r.complemento}`],
    ["Bairro", r.bairro],
  ];
  const active = r.situacao === "ATIVA";
  return (
    <div className="rounded-xl border border-line bg-ink-850/50 p-4">
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          <Database className="size-4 text-emerald-300" /> Ô khác trên CNPJ
        </span>
        <span
          className={clsx(
            "rounded-md px-2 py-0.5 text-[11px] font-semibold",
            active ? "bg-emerald-400/10 text-emerald-300" : "bg-rose-500/15 text-rose-300",
          )}
        >
          Situação: {r.situacao} · {r.dataSituacao}
        </span>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[11.5px]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-fg-subtle">{k}</dt>
            <dd className="truncate text-fg-muted" title={v}>{v}</dd>
          </div>
        ))}
      </dl>
      {r.email && (
        <label className="mt-2.5 flex cursor-pointer items-start gap-2 border-t border-line pt-2.5 text-[11.5px] text-fg-muted">
          <input
            type="checkbox"
            checked={!!r.emailVerified}
            onChange={(e) => dispatch({ type: "emailVerified", id: file.id, on: e.target.checked })}
            className="mt-0.5 accent-brand"
          />
          <span>
            Đây là email liên hệ chính thức của doanh nghiệp (đã xác minh)
            <span className="block text-[10.5px] text-fg-subtle">Chưa tick → web ẩn email và form gửi thư</span>
          </span>
        </label>
      )}
      {!active && <p className="mt-2 text-[11.5px] text-rose-300">Doanh nghiệp không còn ATIVA — kiểm tra trước khi tạo miền / web.</p>}
      <p className="mt-2 text-[10.5px] text-fg-subtle">Lưu database đúng như in trên phôi · không ghi Sheet</p>
    </div>
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
    return v ? "ok" : file.fields && file.docType !== "unknown" ? "missing" : "pending";
  };
  const cls = {
    ok: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    missing: "border-rose-400/40 bg-rose-500/10 text-rose-300",
    pending: "border-line bg-white/[0.02] text-fg-subtle",
    locked: "border-dashed border-line bg-transparent text-fg-subtle/60",
    keep: "border-dashed border-line bg-transparent text-fg-subtle/60",
  } as const;
  const title = { ok: "Có dữ liệu", missing: "Thiếu", pending: "Chưa có", locked: "Không ghi — thuộc module khác", keep: "Giữ nguyên" } as const;

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
        <span><Lock className="mr-0.5 inline size-2.5" /> B, C: không bao giờ ghi</span>
        <span>K: link “Xem phôi” sau khi upload</span>
        <span>L: giữ nguyên</span>
      </div>
    </div>
  );
}

function DriveStatus({ file }: { file: PdfFile }) {
  const lastStep = SAVE_STEPS.length - 1;
  const stepState = (i: number): "done" | "run" | "todo" | "fail" => {
    if (file.status === "saved") return "done";
    if (file.status === "failed" && file.failedAt === "sheet") return i < lastStep ? "done" : "fail";
    if (file.status !== "saving") return "todo";
    return i < file.step ? "done" : i === file.step ? "run" : "todo";
  };

  return (
    <div className="rounded-xl border border-line bg-ink-850/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          <HardDrive className="size-4 text-sky-300" /> Lưu trữ · Drive trước, Sheet sau
        </span>
        {file.driveFileId && (
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
              ) : st === "fail" ? (
                <XCircle className="size-4 text-rose-400" />
              ) : (
                <Circle className="size-4 text-fg-subtle/50" />
              )}
              <span className={st === "todo" ? "text-fg-subtle" : st === "fail" ? "text-rose-300" : "text-fg"}>{s}</span>
            </li>
          );
        })}
      </ol>
      <div className="mt-3.5 space-y-2 border-t border-line pt-3 text-[12px]">
        <div className="flex items-center justify-between gap-2">
          <span className="text-fg-muted">Drive file ID</span>
          <span className="truncate font-mono text-[11.5px] text-fg-muted">{file.driveFileId ?? "—"}</span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-fg-muted"><ColBadge c="K" /> Liên kết</span>
          {file.driveLink ? (
            <a
              href={file.driveLink}
              onClick={(e) => e.preventDefault()}
              className="inline-flex items-center gap-1.5 rounded-md border border-rose-400/25 bg-rose-500/[0.08] px-2.5 py-1 font-medium text-rose-200 hover:bg-rose-500/15"
            >
              <FileText className="size-3.5" /> Xem phôi <ExternalLink className="size-3" />
            </a>
          ) : (
            <span className="text-fg-subtle">Ghi cùng dòng sau khi upload xong</span>
          )}
        </div>
      </div>
    </div>
  );
}

function Blocker({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-rose-300">
      <AlertCircle className="mt-px size-3.5 shrink-0" /> <span>{children}</span>
    </p>
  );
}

function ColBadge({ c, muted }: { c: string; muted?: boolean }) {
  return (
    <span
      className={clsx(
        "inline-grid size-5 shrink-0 place-items-center rounded font-mono text-[10.5px] font-bold",
        muted ? "bg-white/[0.04] text-fg-subtle" : "bg-brand/20 text-sky-200",
      )}
    >
      {c}
    </span>
  );
}

function Notice({ tone, icon: Icon, title, children }: { tone: "rose" | "orange" | "sky"; icon: typeof Info; title: string; children: React.ReactNode }) {
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
    <button onClick={onClick} className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.08] px-2.5 py-1 text-[12px] font-medium text-fg hover:bg-white/[0.13]">
      <Icon className="size-3.5" /> {children}
    </button>
  );
}
