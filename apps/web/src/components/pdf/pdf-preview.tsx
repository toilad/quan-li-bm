"use client";

import { useState } from "react";
import clsx from "clsx";
import { ZoomIn, ZoomOut, FileText, ScanLine, Fingerprint, Loader2, FileX2, Eye } from "lucide-react";
import { DOC_TYPES, MOCK_RESULTS, type FieldKey, type Fields, type Industry, type PdfFile } from "@/lib/pdf-mock";
import { fmtSize } from "./file-queue";

export type HighlightKey = FieldKey | "industry" | null;

export function PdfPreview({ file, highlight }: { file: PdfFile | null; highlight: HighlightKey }) {
  const [zoom, setZoom] = useState(100);

  if (!file)
    return (
      <section className="panel grid min-h-[520px] place-items-center text-[13px] text-fg-subtle">
        Chọn một file trong danh sách để xem trước
      </section>
    );

  const pending = file.status === "processing" ? MOCK_RESULTS[file.id] : undefined;
  const fields = file.fields ?? pending?.fields;
  const industry = file.industry ?? pending?.industry ?? null;
  const hasContent = fields && Object.values(fields).some((f) => f.value);

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
        ) : hasContent ? (
          <div style={{ width: `${zoom}%` }} className={clsx("mx-auto transition-[width]", file.status === "processing" && "opacity-60")}>
            <Paper scanned={!file.textLayer}>
              {file.docType === "br" ? (
                <BrazilCnpj file={file} fields={fields} industry={industry} hl={highlight} />
              ) : file.docType === "ca" ? (
                <CaliforniaLlc1 fields={fields} hl={highlight} />
              ) : (
                <WyomingArticles fields={fields} hl={highlight} />
              )}
            </Paper>
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
        {!file.blobUrl && hasContent && (
          <p className="mx-auto mt-3 max-w-[560px] text-center text-[11px] text-fg-subtle">
            Bản giả lập phôi {DOC_TYPES[file.docType].label} từ dữ liệu mẫu · rê chuột vào ô bên phải để xem vị trí đọc
          </p>
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
  const unknown = file.docType === "unknown" && !!file.detection;
  return (
    <div className="mx-auto max-w-[560px]">
      <div className={clsx("relative aspect-[8.5/11] rounded-sm bg-white p-10 shadow-2xl", (failed || unknown) && "blur-[1.5px] grayscale")}>
        {unknown && <div className="absolute inset-x-0 top-0 h-[16%] bg-gradient-to-b from-slate-400/70 to-transparent" />}
        {Array.from({ length: 14 }, (_, i) => (
          <div key={i} className="mb-3 h-2.5 rounded-sm bg-slate-200" style={{ width: `${55 + ((i * 37) % 40)}%` }} />
        ))}
      </div>
      <div className="mt-4 flex items-center justify-center gap-2 text-[12.5px] text-fg-muted">
        {failed || unknown ? <FileX2 className="size-4 text-rose-300" /> : <Loader2 className="size-4" />}
        {failed
          ? "Không đọc được nội dung PDF này"
          : unknown
            ? "Không nhận diện được loại phôi — chọn loại ở bảng bên phải"
            : "Chưa xử lý — bấm Bắt đầu để đọc file"}
      </div>
    </div>
  );
}

/* ───────── Simulated originals (demo data only) ───────── */

function Paper({ scanned, children }: { scanned: boolean; children: React.ReactNode }) {
  return (
    <div
      className={clsx(
        "relative aspect-[8.5/11] w-full overflow-hidden rounded-sm bg-white px-[7%] py-[6%] text-[clamp(9px,1.05vw,13px)] leading-relaxed text-slate-800 shadow-2xl",
        scanned && "rotate-[0.4deg] contrast-[0.88] sepia-[0.18]",
      )}
    >
      {scanned && (
        <div
          className="pointer-events-none absolute inset-0 z-10 opacity-[0.08]"
          style={{ backgroundImage: "radial-gradient(#000 0.6px, transparent 0.6px)", backgroundSize: "3px 3px" }}
        />
      )}
      {children}
    </div>
  );
}

type HlProps = { k: FieldKey | "industry"; hl: HighlightKey; children: React.ReactNode; className?: string };
function H({ k, hl, children, className }: HlProps) {
  return (
    <span className={clsx("rounded-[3px] px-0.5 transition", hl === k ? "bg-yellow-300/70 ring-2 ring-yellow-400" : "bg-sky-200/40", className)}>
      {children}
    </span>
  );
}

const val = (fields: Fields, k: FieldKey) => fields[k].value || "______";

function Skipped({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-rose-100 px-1.5 py-0.5 font-sans text-[0.72em] font-semibold text-rose-600">{children}</span>
  );
}

function WyomingArticles({ fields, hl }: { fields: Fields; hl: HighlightKey }) {
  const v = (k: FieldKey) => val(fields, k);
  return (
    <div className="font-serif">
      <div className="text-center">
        <div className="text-[0.85em] font-bold tracking-[0.2em] text-slate-600">STATE OF WYOMING</div>
        <div className="text-[0.8em] text-slate-500">Office of the Secretary of State · Business Division</div>
        <div className="mt-3 text-[1.35em] font-bold">Articles of Organization</div>
        <div className="text-[0.9em] italic text-slate-600">Limited Liability Company</div>
      </div>
      <div className="mt-4 flex justify-between border-y border-slate-300 py-1.5 text-[0.85em]">
        <span>
          Original ID: <H k="J" hl={hl}>{v("J")}</H>
        </span>
        <span>Filed: 06/12/2024 09:41 AM</span>
      </div>
      <ol className="mt-4 space-y-3">
        <li>
          <b>1. Name of the limited liability company:</b>
          <div className="mt-0.5 pl-4 text-[1.1em] font-semibold">
            <H k="A" hl={hl}>{v("A")}</H>
          </div>
        </li>
        <li>
          <b>2. Registered agent name and physical address:</b>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 pl-4">
            <span className="text-slate-500 line-through decoration-rose-400/70">Example Registered Agent LLC · 100 Agent Way, Cheyenne, WY 82001</span>
            <Skipped>Bỏ qua: Registered Agent</Skipped>
          </div>
        </li>
        <li>
          <b>3. Mailing address of the limited liability company:</b>
          <div className="mt-0.5 pl-4">
            <H k="F" hl={hl}>{v("F")}</H>
            <br />
            <H k="G" hl={hl}>{v("G")}</H>, <H k="H" hl={hl}>{v("H")}</H> <H k="I" hl={hl}>{v("I")}</H>
          </div>
        </li>
        <li>
          <b>4. Daytime phone number:</b>
          <div className="mt-0.5 pl-4">
            <H k="D" hl={hl}>{v("D")}</H>
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

/** Layout follows the owner's sample: LLC-1 (REV 01/2013), entity number top-right, sections ①–⑤. */
function CaliforniaLlc1({ fields, hl }: { fields: Fields; hl: HighlightKey }) {
  const v = (k: FieldKey) => val(fields, k);
  const Line = ({ children, label }: { children: React.ReactNode; label: string }) => (
    <div>
      <div className="border-b border-slate-700 pb-0.5">{children}</div>
      <div className="text-[0.62em] italic text-slate-600">{label}</div>
    </div>
  );
  return (
    <div className="font-sans text-[0.88em]">
      <div className="grid grid-cols-[1.45fr_1fr] gap-3">
        <div className="border border-slate-700">
          <div className="flex border-b border-slate-700">
            <div className="border-r border-slate-700 px-2 py-1 text-[1.15em] font-bold">LLC-1</div>
            <div className="px-2 py-1 font-bold leading-tight">Articles of Organization of a Limited Liability Company (LLC)</div>
          </div>
          <div className="space-y-1 px-2 py-1.5 text-[0.72em] leading-snug text-slate-700">
            <p>To form a limited liability company in California, you can fill out this form, and submit for filing along with a $70 filing fee.</p>
            <p><b>Important!</b> LLCs in California may have to pay a minimum $800 yearly tax to the California Franchise Tax Board.</p>
          </div>
        </div>
        <div className="flex flex-col items-center justify-between py-1 text-center">
          <div className="font-serif text-[1.35em] font-bold tracking-[0.12em]">
            <H k="J" hl={hl}>{v("J")}</H>
          </div>
          <div className="leading-tight">
            <div className="text-[1.2em] font-black">FILED</div>
            <div className="text-[0.75em] font-semibold">Secretary of State</div>
            <div className="text-[0.75em] font-semibold">State of California</div>
            <div className="mt-1 font-bold">JUN 0 3 2024</div>
          </div>
          <div className="text-[0.6em] text-slate-500">This Space For Office Use Only</div>
        </div>
      </div>

      <div className="mt-3 space-y-2.5">
        <div>
          <div className="font-bold">LLC Name</div>
          <div className="flex gap-2 pl-1">
            <span>①</span>
            <div className="flex-1">
              <Line label="Proposed LLC Name">
                <span className="font-serif text-[1.08em]">
                  <H k="A" hl={hl}>{v("A")}</H>
                </span>
              </Line>
            </div>
          </div>
        </div>
        <div>
          <div className="font-bold">Purpose</div>
          <p className="pl-1 text-[0.8em] text-slate-600">② The purpose of the limited liability company is to engage in any lawful act or activity…</p>
        </div>
        <div>
          <div className="font-bold">LLC Addresses</div>
          <div className="flex gap-2 pl-1">
            <span>③ a.</span>
            <div className="grid flex-1 grid-cols-[1.6fr_1.2fr] gap-3">
              <Line label="Initial Street Address of LLC">
                <span className="font-serif">
                  <H k="F" hl={hl}>{v("F")}</H>
                </span>
              </Line>
              <Line label="City (no abbreviations) · State · Zip">
                <span className="font-serif">
                  <H k="G" hl={hl}>{v("G")}</H>, <H k="H" hl={hl}>California</H> <H k="I" hl={hl}>{v("I")}</H>
                </span>
              </Line>
            </div>
          </div>
          <div className="mt-1 flex gap-2 pl-1 text-slate-500">
            <span>&nbsp; b.</span>
            <div className="flex-1">
              <Line label="Initial Mailing Address of LLC, if different from 3a">&nbsp;</Line>
            </div>
          </div>
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-2 font-bold">
            Service of Process <Skipped>Bỏ qua: địa chỉ Agent</Skipped>
          </div>
          <div className="pl-1 font-serif text-slate-500 line-through decoration-rose-400/70">④ a. Example Agent · b. 100 Agent St, Sacramento CA 95814</div>
        </div>
        <div>
          <div className="font-bold">Management</div>
          <div className="pl-1 text-[0.85em]">⑤ ☐ One Manager &nbsp; ☐ More Than One Manager &nbsp; ☑ All LLC Member(s)</div>
        </div>
      </div>
      <div className="mt-2 rounded bg-amber-100 px-2 py-1 text-[0.8em] font-semibold text-amber-800">
        Mẫu LLC-1 không có ô điện thoại → cột D để trống, chờ anh xác nhận
      </div>
      <div className="absolute inset-x-[7%] bottom-[5%] flex justify-between border-t border-slate-400 pt-1.5 text-[0.68em] text-slate-600">
        <span>LLC-1 (REV 01/2013)</span>
        <span>Trang 2: Attachment — lặp lại số 12 chữ số</span>
      </div>
    </div>
  );
}

/** Box layout follows the owner's comprovante samples (IN RFB nº 2.119/2022). */
function BrazilCnpj({ file, fields, industry, hl }: { file: PdfFile; fields: Fields; industry: Industry | null; hl: HighlightKey }) {
  const r = file.br ?? MOCK_RESULTS[file.id]?.br;
  const v = (k: FieldKey) => val(fields, k);
  const Cell = ({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) => (
    <div className={clsx("border border-slate-700 px-1.5 py-0.5", className)}>
      <div className="text-[0.55em] uppercase text-slate-600">{label}</div>
      <div className="min-h-[1.3em] text-[0.82em] font-bold uppercase">{children}</div>
    </div>
  );
  const addr = (k: "F", text: string) => (hl === k ? <H k={k} hl={hl}>{text}</H> : text);
  return (
    <div className="font-sans">
      <div className="border-2 border-slate-600 p-[3%]">
        <div className="text-center">
          <div className="text-[0.95em] font-bold">REPÚBLICA FEDERATIVA DO BRASIL</div>
          <div className="mt-1 text-[0.9em] font-bold">CADASTRO NACIONAL DA PESSOA JURÍDICA</div>
        </div>
        <div className="mt-2 space-y-1">
          <div className="grid grid-cols-[1.1fr_1.7fr_0.9fr] gap-1">
            <Cell label="Número de inscrição">
              <span className="whitespace-nowrap font-mono text-[0.92em]"><H k="J" hl={hl}>{v("J")}</H></span>
              <div>MATRIZ</div>
            </Cell>
            <div className="grid place-items-center border border-slate-700 px-1 text-center text-[0.75em] font-bold leading-tight">
              COMPROVANTE DE INSCRIÇÃO E DE SITUAÇÃO CADASTRAL
            </div>
            <Cell label="Data de abertura">{r?.abertura ?? "—"}</Cell>
          </div>
          <Cell label="Nome empresarial"><H k="A" hl={hl}>{v("A")}</H></Cell>
          <div className="grid grid-cols-[4fr_1fr] gap-1">
            <Cell label="Título do estabelecimento (nome de fantasia)">{r?.fantasia ?? "********"}</Cell>
            <Cell label="Porte">{r?.porte ?? "ME"}</Cell>
          </div>
          <Cell label="Código e descrição da atividade econômica principal">
            <span className="normal-case">
              <H k="industry" hl={hl}>{industry?.code ?? "—"} - {industry?.raw ?? "—"}</H>
            </span>
          </Cell>
          <Cell label="Código e descrição das atividades econômicas secundárias">
            <span className="normal-case">{r?.cnaeSecundarias.length ? r.cnaeSecundarias.join(" · ") : "Não informada"}</span>
          </Cell>
          <Cell label="Código e descrição da natureza jurídica"><span className="normal-case">{r?.natureza ?? "—"}</span></Cell>
          <div className={clsx("grid grid-cols-[2.4fr_0.6fr_1.6fr] gap-1 rounded-sm", hl === "F" && "ring-2 ring-yellow-400")}>
            <Cell label="Logradouro">{addr("F", r?.logradouro ?? v("F"))}</Cell>
            <Cell label="Número">{addr("F", r?.numero ?? "")}</Cell>
            <Cell label="Complemento">{addr("F", r?.complemento ?? "")}</Cell>
          </div>
          <div className="grid grid-cols-[1fr_1.6fr_1.8fr_0.4fr] gap-1">
            <Cell label="CEP"><span className="font-mono"><H k="I" hl={hl}>{v("I")}</H></span></Cell>
            <Cell label="Bairro/Distrito"><span className={clsx(hl === "F" && "bg-yellow-300/70")}>{r?.bairro ?? ""}</span></Cell>
            <Cell label="Município"><H k="G" hl={hl}>{v("G")}</H></Cell>
            <Cell label="UF"><H k="H" hl={hl}>{v("H")}</H></Cell>
          </div>
          <div className="grid grid-cols-[1.4fr_1fr] gap-1">
            <Cell label="Endereço eletrônico">{r?.email ?? ""}</Cell>
            <Cell label="Telefone">{fields.D.value ? <H k="D" hl={hl}>{fields.D.value}</H> : ""}</Cell>
          </div>
          <div className="grid grid-cols-[3fr_1fr] gap-1">
            <Cell label="Situação cadastral">{r?.situacao ?? "ATIVA"}</Cell>
            <Cell label="Data da situação cadastral">{r?.dataSituacao ?? "—"}</Cell>
          </div>
        </div>
      </div>
      <p className="mt-3 text-[0.72em] text-slate-600">Aprovado pela Instrução Normativa RFB nº 2.119, de 06 de dezembro de 2022.</p>
    </div>
  );
}
