"use client";

import { useState } from "react";
import clsx from "clsx";
import { ZoomIn, ZoomOut, FileText, ScanLine, Fingerprint, Loader2, FileX2, Eye } from "lucide-react";
import { MOCK_RESULTS, type FieldKey, type Fields, type PdfFile } from "@/lib/pdf-mock";
import { fmtSize } from "./file-queue";

export function PdfPreview({ file, highlight }: { file: PdfFile | null; highlight: FieldKey | null }) {
  const [zoom, setZoom] = useState(100);

  if (!file)
    return (
      <section className="panel grid min-h-[520px] place-items-center text-[13px] text-fg-subtle">
        Chọn một file trong danh sách để xem trước
      </section>
    );

  const docFields = file.fields ?? (file.status === "processing" ? MOCK_RESULTS[file.id] : undefined);

  return (
    <section className="panel flex min-h-0 flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <Eye className="size-4 shrink-0 text-sky-300" />
          <div className="min-w-0">
            <div className="truncate text-[13.5px] font-semibold" title={file.name}>
              {file.name}
            </div>
            <div className="flex flex-wrap items-center gap-x-2.5 text-[11px] text-fg-subtle">
              <span>{fmtSize(file.sizeKb)}</span>
              {file.pages > 0 && <span>{file.pages} trang</span>}
              {file.local && !file.fields ? (
                <span className="inline-flex items-center gap-1">
                  <FileText className="size-3" /> Chưa phân tích lớp chữ
                </span>
              ) : (
                <span className={clsx("inline-flex items-center gap-1", file.textLayer ? "text-emerald-300/80" : "text-amber-300/90")}>
                  {file.textLayer ? <FileText className="size-3" /> : <ScanLine className="size-3" />}
                  {file.textLayer ? "Có lớp chữ — đọc trực tiếp" : "Bản scan — cần AI đọc"}
                </span>
              )}
              {file.md5 && (
                <span className="inline-flex items-center gap-1 font-mono" title={`md5 ${file.md5}`}>
                  <Fingerprint className="size-3" /> {file.md5.slice(0, 8)}…
                </span>
              )}
            </div>
          </div>
        </div>
        {!file.blobUrl && (
          <div className="flex items-center gap-1 rounded-lg border border-line bg-ink-850/70 p-0.5">
            <IconBtn label="Thu nhỏ" onClick={() => setZoom((z) => Math.max(60, z - 10))}>
              <ZoomOut className="size-4" />
            </IconBtn>
            <span className="w-11 text-center font-mono text-[11.5px] text-fg-muted">{zoom}%</span>
            <IconBtn label="Phóng to" onClick={() => setZoom((z) => Math.min(150, z + 10))}>
              <ZoomIn className="size-4" />
            </IconBtn>
          </div>
        )}
      </header>

      <div className="scroll-thin relative min-h-[520px] flex-1 overflow-auto bg-[#0a0f24] p-5">
        {file.blobUrl ? (
          <iframe title={`Xem trước ${file.name}`} src={file.blobUrl} className="h-full min-h-[600px] w-full rounded-lg bg-white" />
        ) : docFields ? (
          <div style={{ width: `${zoom}%` }} className="mx-auto max-w-none transition-[width]">
            <FakeFiling fields={docFields} scanned={!file.textLayer} highlight={highlight} dim={file.status === "processing"} />
          </div>
        ) : (
          <EmptyDoc file={file} />
        )}
        {file.status === "processing" && (
          <div className="absolute inset-x-0 top-0 flex justify-center pt-4">
            <span className="inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-ink-900/90 px-3 py-1.5 text-[12px] font-medium text-sky-200 shadow-lg backdrop-blur">
              <Loader2 className="size-3.5 animate-spin" /> Đang đọc và trích xuất…
            </span>
          </div>
        )}
      </div>
    </section>
  );
}

function IconBtn({ children, onClick, label }: { children: React.ReactNode; onClick: () => void; label: string }) {
  return (
    <button onClick={onClick} aria-label={label} className="grid size-7 place-items-center rounded-md text-fg-muted hover:bg-white/[0.07] hover:text-fg">
      {children}
    </button>
  );
}

function EmptyDoc({ file }: { file: PdfFile }) {
  const failed = file.status === "failed";
  return (
    <div className="mx-auto max-w-[560px]">
      <div className={clsx("relative aspect-[8.5/11] rounded-sm bg-white p-10 shadow-2xl", failed && "blur-[1.5px] grayscale")}>
        {Array.from({ length: 14 }, (_, i) => (
          <div key={i} className="mb-3 h-2.5 rounded-sm bg-slate-200" style={{ width: `${55 + ((i * 37) % 40)}%` }} />
        ))}
      </div>
      <div className="mt-4 flex items-center justify-center gap-2 text-[12.5px] text-fg-muted">
        {failed ? <FileX2 className="size-4 text-rose-300" /> : <Loader2 className="size-4" />}
        {failed ? "Không đọc được nội dung PDF này" : "Chưa xử lý — bấm Bắt đầu để đọc file"}
      </div>
    </div>
  );
}

/**
 * Stand-in rendering of a Wyoming SOS filing, built from the demo values so
 * hovering a form field can highlight where it was read from.
 */
function FakeFiling({ fields, scanned, highlight, dim }: { fields: Fields; scanned: boolean; highlight: FieldKey | null; dim: boolean }) {
  const H = ({ k, children }: { k: FieldKey | FieldKey[]; children: React.ReactNode }) => {
    const keys = Array.isArray(k) ? k : [k];
    const on = highlight !== null && keys.includes(highlight);
    return (
      <span
        className={clsx(
          "rounded-[3px] px-0.5 transition",
          on ? "bg-yellow-300/70 ring-2 ring-yellow-400" : "bg-sky-200/40",
        )}
      >
        {children}
      </span>
    );
  };
  const v = (k: FieldKey) => fields[k].value || "______";

  return (
    <div
      className={clsx(
        "relative aspect-[8.5/11] w-full rounded-sm bg-white px-[7%] py-[6%] font-serif text-[clamp(9px,1.05vw,13px)] leading-relaxed text-slate-800 shadow-2xl",
        scanned && "rotate-[0.35deg] contrast-[0.9] sepia-[0.15]",
        dim && "opacity-60",
      )}
    >
      {scanned && (
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: "radial-gradient(#000 0.6px, transparent 0.6px)", backgroundSize: "3px 3px" }}
        />
      )}
      <div className="text-center">
        <div className="text-[0.85em] font-bold tracking-[0.2em] text-slate-600">STATE OF WYOMING</div>
        <div className="text-[0.8em] text-slate-500">Office of the Secretary of State · Business Division</div>
        <div className="mt-3 text-[1.35em] font-bold">Articles of Organization</div>
        <div className="text-[0.9em] italic text-slate-600">Limited Liability Company</div>
      </div>
      <div className="mt-4 flex justify-between border-y border-slate-300 py-1.5 text-[0.85em]">
        <span>
          Original ID: <H k="J">{v("J")}</H>
        </span>
        <span>Filed: 06/12/2024 09:41 AM</span>
      </div>

      <ol className="mt-4 space-y-3 [&>li]:pl-1">
        <li>
          <b>1. Name of the limited liability company:</b>
          <div className="mt-0.5 pl-4 text-[1.1em] font-semibold">
            <H k="A">{v("A")}</H>
          </div>
        </li>
        <li>
          <b>2. Registered agent name and physical address:</b>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 pl-4">
            <span className="text-slate-500 line-through decoration-rose-400/70">
              Example Registered Agent LLC · 100 Agent Way, Cheyenne, WY 82001
            </span>
            <span className="rounded bg-rose-100 px-1.5 py-0.5 font-sans text-[0.72em] font-semibold text-rose-600">
              Bỏ qua: địa chỉ Registered Agent
            </span>
          </div>
        </li>
        <li>
          <b>3. Mailing address of the limited liability company:</b>
          <div className="mt-0.5 pl-4">
            <H k="F">{v("F")}</H>
            <br />
            <H k="G">{v("G")}</H>, <H k="H">{v("H")}</H> <H k="I">{v("I")}</H>
          </div>
        </li>
        <li>
          <b>4. Principal office address:</b>
          <div className="mt-0.5 pl-4 text-slate-600">Same as mailing address</div>
        </li>
        <li>
          <b>5. Daytime phone number:</b>
          <div className="mt-0.5 pl-4">
            <H k="D">{v("D")}</H>
          </div>
        </li>
      </ol>

      <div className="absolute inset-x-[7%] bottom-[7%] flex justify-between border-t border-slate-300 pt-2 text-[0.8em] text-slate-500">
        <span>Organizer signature: ____________________</span>
        <span>Page 1</span>
      </div>
    </div>
  );
}
