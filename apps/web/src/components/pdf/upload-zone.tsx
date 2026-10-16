"use client";

import { useRef, useState } from "react";
import clsx from "clsx";
import { FileUp, ShieldCheck, Files, Lock, ScanSearch } from "lucide-react";
import type { PdfFile } from "@/lib/pdf-mock";

/**
 * Drag & drop / picker. In this prototype the chosen PDFs never leave the
 * browser — they are only opened locally for preview.
 */
export function UploadZone({
  existing, onAdd, footer,
}: {
  existing: PdfFile[];
  onAdd: (files: PdfFile[], skipped: string[]) => void;
  footer?: React.ReactNode;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const accept = (list: FileList | null) => {
    if (!list?.length) return;
    const skipped: string[] = [];
    const added: PdfFile[] = [];
    Array.from(list).forEach((file, i) => {
      const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
      if (!isPdf) {
        skipped.push(file.name);
        return;
      }
      const sizeKb = Math.max(1, Math.round(file.size / 1024));
      const dup = [...existing, ...added].find((f) => f.name === file.name && f.sizeKb === sizeKb);
      added.push({
        id: `local-${Date.now()}-${i}`,
        name: file.name,
        sizeKb,
        pages: 0,
        md5: "",
        status: dup ? "duplicate" : "queued",
        step: 0,
        progress: 0,
        docType: "unknown",
        detection: null,
        fields: null,
        industry: null,
        textLayer: true,
        outcome: "review",
        local: true,
        blobUrl: URL.createObjectURL(file),
        duplicateOf: dup ? { row: dup.sheetRow ?? 0, name: dup.name, reason: "Cùng tên và dung lượng với file đã có trong danh sách" } : undefined,
      });
    });
    onAdd(added, skipped);
  };

  return (
    <section className="panel flex flex-col gap-3 p-3">
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        accept(e.dataTransfer.files);
      }}
      className={clsx(
        "relative flex flex-1 flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-7 text-center transition",
        over ? "border-brand/60 bg-brand/[0.06]" : "border-line-strong/70",
      )}
    >
      <span className="relative grid size-14 place-items-center rounded-2xl bg-gradient-to-br from-brand/30 to-brand-2/30 text-sky-200 shadow-[0_10px_30px_-10px_rgb(79_124_255/0.7)]">
        <FileUp className="size-7" />
      </span>
      <h2 className="relative mt-4 text-[18px] font-semibold">Kéo thả PDF vào đây</h2>
      <p className="relative mt-1 text-[13px] text-fg-muted">
        hoặc{" "}
        <button onClick={() => input.current?.click()} className="font-semibold text-sky-300 underline-offset-2 hover:underline">
          chọn nhiều file từ máy tính
        </button>{" "}
        · chỉ nhận .pdf
      </p>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(e) => {
          accept(e.target.files);
          e.target.value = "";
        }}
      />
      <div className="relative mt-5 flex flex-wrap justify-center gap-2 text-[12px]">
        <Pill icon={ShieldCheck}>PDF gốc giữ nguyên — không chuyển ảnh, không chỉnh sửa</Pill>
        <Pill icon={Files}>Nhiều file cùng lúc</Pill>
        <Pill icon={ScanSearch}>Tự nhận diện: Wyoming · California · Brazil CNPJ</Pill>
        <Pill icon={Lock}>Bản thiết kế: file chỉ mở xem trên máy, không gửi đi</Pill>
      </div>
    </div>
    {footer}
    </section>
  );
}

function Pill({ icon: Icon, children }: { icon: typeof Lock; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-ink-850/70 px-3 py-1 text-fg-muted">
      <Icon className="size-3.5 text-emerald-300" />
      {children}
    </span>
  );
}
