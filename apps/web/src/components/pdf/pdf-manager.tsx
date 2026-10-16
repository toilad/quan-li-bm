"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";

import { usePdfQueue } from "./use-pdf-queue";
import { UploadZone } from "./upload-zone";
import { BatchPanel, BatchSettings } from "./batch-panel";
import { FileQueue } from "./file-queue";
import { PdfPreview, type HighlightKey } from "./pdf-preview";
import { ExtractPanel } from "./extract-panel";

export function PdfManager() {
  const { state, dispatch } = usePdfQueue();
  const [hover, setHover] = useState<HighlightKey>(null);
  const [toast, setToast] = useState<string | null>(null);
  const selected = state.files.find((f) => f.id === state.selectedId) ?? null;

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(id);
  }, [toast]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <UploadZone
          existing={state.files}
          footer={<BatchSettings state={state} dispatch={dispatch} />}
          onAdd={(files, skipped) => {
            if (files.length) dispatch({ type: "add", files });
            const dups = files.filter((f) => f.status === "duplicate").length;
            const parts = [
              files.length && `Đã thêm ${files.length} PDF`,
              dups && `${dups} file trùng đã được đánh dấu`,
              skipped.length && `bỏ qua ${skipped.length} file không phải PDF`,
            ].filter(Boolean);
            if (parts.length) setToast(parts.join(" · "));
          }}
        />
        <BatchPanel state={state} dispatch={dispatch} />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[320px_minmax(0,1fr)] min-[1600px]:h-[860px]">
        <FileQueue files={state.files} selectedId={state.selectedId} dispatch={dispatch} />
        <div className="grid min-h-0 grid-cols-1 gap-5 min-[1600px]:grid-cols-[minmax(0,1fr)_440px]">
          <PdfPreview file={selected} highlight={hover} />
          <ExtractPanel file={selected} tab={state.tab} dispatch={dispatch} onHover={setHover} />
        </div>
      </div>

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
          <div className="panel flex items-center gap-3 !rounded-xl px-4 py-3 text-[13px] shadow-2xl">
            <AlertTriangle className="size-4 text-amber-300" />
            {toast}
            <button onClick={() => setToast(null)} aria-label="Đóng thông báo" className="text-fg-subtle hover:text-fg">
              <X className="size-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
