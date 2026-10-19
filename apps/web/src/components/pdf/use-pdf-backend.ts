"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, ApiError, api, errorText, type Job } from "@/lib/api";
import {
  INDUSTRIES, templateFor, type BrRaw, type DocType, type FieldKey, type Fields, type IndustryKey, type PdfFile, type PdfStatus,
  type SHEET_TABS,
} from "@/lib/pdf-mock";
import { isCleanForBulk } from "./use-pdf-queue";

type SheetTab = (typeof SHEET_TABS)[number];

/** Same shape the PDF components already use, now filled from the backend. */
export type QueueState = {
  files: PdfFile[];
  selectedId: string | null;
  running: boolean;
  autoSave: boolean;
  tab: SheetTab;
  nextRow: number;
};

type Action =
  | { type: "select"; id: string }
  | { type: "run"; on: boolean }
  | { type: "retry"; id: string }
  | { type: "retryAll" }
  | { type: "remove"; id: string }
  | { type: "edit"; id: string; key: FieldKey; value: string }
  | { type: "industry"; id: string; category: IndustryKey }
  | { type: "emailVerified"; id: string; on: boolean }
  | { type: "docType"; id: string; docType: DocType }
  | { type: "confirmMissing"; id: string; on: boolean }
  | { type: "criticalChecked"; id: string; on: boolean }
  | { type: "save"; id: string }
  | { type: "saveAllValid" }
  | { type: "autoSave"; on: boolean }
  | { type: "tab"; tab: SheetTab }
  | { type: "aiRead"; id: string };

export type QueueDispatch = (a: Action) => void;

type Doc = {
  id: number; name: string; md5: string; size: number; pages: number; has_text: boolean; doc_type: DocType;
  confidence: number; reason: string; fields: Fields | Record<string, never>; extra: Record<string, string> & { email_verified?: boolean };
  industry: { raw?: string; template?: string; source?: string; category?: IndustryKey; note?: string };
  status: string; error: string | null; drive_file_id: string | null; drive_link: string | null; sheet_row: number | null;
};

const SAVE_STEP_INDEX: Record<string, number> = {
  "Kiểm tra trùng": 0, "Upload PDF gốc lên Drive": 1, "Ghi Google Sheet (A, D–K)": 3,
};

function categoryOf(ind: Doc["industry"]): IndustryKey {
  if (ind.category) return ind.category;
  const hit = (Object.keys(INDUSTRIES) as IndustryKey[]).find((k) => templateFor({ raw: "", category: k, source: "name" }).id === ind.template);
  return hit ?? "general";
}

function toFile(d: Doc, job: Job | undefined, aiJob: Job | undefined, local: { confirm?: boolean; checked?: boolean }): PdfFile {
  let status: PdfStatus = "review";
  let step = 0;
  let error = d.error ?? undefined;
  let failedAt: PdfFile["failedAt"];
  let duplicateOf: PdfFile["duplicateOf"];
  if (d.status === "saved") status = "saved";
  else if (d.status === "uploaded") status = "processing";
  else if (d.status === "queued" && job) {
    if (job.status === "queued" || job.status === "running") {
      status = "saving";
      step = SAVE_STEP_INDEX[job.step ?? ""] ?? 0;
    } else if (job.status === "conflict") {
      status = "duplicate";
      duplicateOf = { row: 0, name: "", reason: job.error ?? "Trùng dữ liệu đã có" };
    } else if (job.status === "failed" || job.status === "blocked") {
      status = "failed";
      error = job.status === "blocked" ? `Dừng: ${job.error}` : job.error ?? "Lỗi khi lưu";
      failedAt = d.drive_file_id ? "sheet" : "process";
    }
  } else if (d.status === "failed") {
    status = "failed";
    failedAt = d.drive_file_id ? "sheet" : "process";
  }
  if (d.status === "needs_ai") {
    error = aiJob?.status === "blocked" ? `Chưa đọc được: ${aiJob.error}` : aiJob?.status === "failed" ? aiJob.error ?? undefined : d.error ?? undefined;
  }
  const hasFields = Object.keys(d.fields || {}).length > 0;
  const x = d.extra || {};
  const br: BrRaw | undefined = d.doc_type === "br" && hasFields ? {
    nome: (d.fields as Fields).A?.value ?? "", fantasia: x.nome_fantasia ?? "", porte: x.porte ?? "", abertura: x.data_abertura ?? "",
    cnaePrincipal: x.cnae_principal ?? "", cnaeSecundarias: x.cnae_secundarias ? [x.cnae_secundarias] : [], natureza: x.natureza_juridica ?? "",
    logradouro: x.logradouro ?? "", numero: x.numero ?? "", complemento: x.complemento ?? "", cep: x.cep ?? "", bairro: x.bairro ?? "",
    municipio: x.municipio ?? "", uf: x.uf ?? "", email: x.email ?? "", emailVerified: x.email_verified === true, telefone: x.telefone ?? "", situacao: x.situacao_cadastral ?? "",
    dataSituacao: x.data_situacao ?? "",
  } : undefined;
  return {
    id: String(d.id), name: d.name, sizeKb: Math.max(1, Math.round(d.size / 1024)), pages: d.pages, md5: d.md5,
    status, step, progress: status === "saving" ? 50 : 0, docType: d.doc_type,
    detection: { confidence: Math.round(d.confidence * 100), reason: d.reason, manual: d.reason === "Chọn thủ công" },
    fields: hasFields ? (d.fields as Fields) : null,
    industry: hasFields && d.industry?.template ? { raw: d.industry.raw ?? "", category: categoryOf(d.industry), source: (d.industry.source as "doc" | "name" | "manual") ?? "name" } : null,
    br, textLayer: d.has_text, error, failedAt, duplicateOf,
    sheetRow: d.sheet_row ?? undefined, driveFileId: d.drive_file_id ?? undefined, driveLink: d.drive_link ?? undefined,
    confirmMissing: local.confirm, criticalChecked: local.checked,
    blobUrl: `${API_URL}/api/pdf/${d.id}/file`,
    needsAi: d.status === "needs_ai", aiRunning: aiJob?.status === "queued" || aiJob?.status === "running",
  } as PdfFile;
}

export function usePdfBackend(onMessage: (msg: string) => void) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [flags, setFlags] = useState<Record<string, { confirm?: boolean; checked?: boolean }>>({});
  const [autoSave, setAutoSave] = useState(false);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const editTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const refresh = useCallback(async () => {
    try {
      const [d, j1, j2] = await Promise.all([
        api.get<Doc[]>("/api/pdf"), api.get<Job[]>("/api/jobs?kind=pdf_save"), api.get<Job[]>("/api/jobs?kind=pdf_ai_read"),
        api.get<Job[]>("/api/jobs?kind=pdf_ocr_read"),
      ]).then(([a, b, c, o]) => [a, b, [...c, ...o]] as const);
      setDocs(d);
      setJobs([...j1, ...j2]);
      const q = await api.get<{ paused: string[] }>("/api/queue");
      setPaused(q.paused.includes("*") || q.paused.includes("pdf_save"));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("error", errorText(e)));
    }
  }, []);

  // the scan reader: free OCR first, the AI only when a key is set and OCR does not know the form
  const latestRead = (docId: number) => jobs.filter((j) => (j.kind === "pdf_ocr_read" || j.kind === "pdf_ai_read") && j.payload.doc_id === docId).sort((a, b) => b.id - a.id)[0];
  const latest = (kind: string, docId: number) => jobs.filter((j) => j.kind === kind && j.payload.doc_id === docId).sort((a, b) => b.id - a.id)[0];
  const files = docs.filter((d) => !hidden.has(String(d.id))).map((d) => toFile(d, latest("pdf_save", d.id), latestRead(d.id), flags[String(d.id)] ?? {}));
  const busy = files.some((f) => f.status === "processing" || f.status === "saving" || (f as PdfFile & { aiRunning?: boolean }).aiRunning);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, busy ? 2000 : 10000);
    return () => clearInterval(id);
  }, [refresh, busy]);

  const save = useCallback(async (id: string) => {
    const f = flags[id] ?? {};
    try {
      await api.post(`/api/pdf/${id}/save`, { confirm_missing: !!f.confirm, critical_checked: !!f.checked });
      onMessage("Đã đưa vào hàng đợi lưu: Drive → kiểm tra md5 → ghi Sheet");
    } catch (e) {
      onMessage(e instanceof ApiError && e.reasons.length ? `Chưa lưu được: ${e.reasons.join(" · ")}` : errorText(e));
    }
    refresh();
  }, [flags, onMessage, refresh]);

  // Auto-save (off by default): only clean files — no warnings, nothing read by AI.
  useEffect(() => {
    if (!autoSave) return;
    files.filter((f) => isCleanForBulk(f)).forEach((f) => save(f.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSave, docs]);

  const upload = useCallback(async (list: File[]) => {
    try {
      const res = await api.upload<(Doc & { duplicate?: boolean; status: string; error?: string })[]>("/api/pdf/upload", list);
      const dups = res.filter((r) => r.duplicate).length;
      const rejected = res.filter((r) => r.status === "rejected");
      const parts = [
        res.length - dups - rejected.length && `Đã nhận ${res.length - dups - rejected.length} PDF`,
        dups && `${dups} file đã có (cùng nội dung) — không thêm trùng`,
        rejected.length && `từ chối ${rejected.length}: ${rejected.map((r) => r.error).join("; ")}`,
      ].filter(Boolean);
      if (parts.length) onMessage(parts.join(" · "));
      const first = res.find((r) => r.id);
      if (first) {
        setHidden((h) => { const n = new Set(h); n.delete(String(first.id)); return n; });
        setSelectedId(String(first.id));
      }
    } catch (e) {
      onMessage(errorText(e));
    }
    refresh();
  }, [onMessage, refresh]);

  const dispatch: QueueDispatch = useCallback((a: Action) => {
    const call = async (fn: () => Promise<unknown>, ok?: string) => {
      try {
        await fn();
        if (ok) onMessage(ok);
      } catch (e) {
        onMessage(errorText(e));
      }
      refresh();
    };
    switch (a.type) {
      case "select":
        return setSelectedId(a.id);
      case "remove":
        // Hidden from this list only — nothing is deleted from the database, Drive or the Sheet.
        return setHidden((h) => new Set(h).add(a.id));
      case "edit": {
        setDocs((ds) => ds.map((d) => (String(d.id) === a.id ? { ...d, fields: { ...d.fields, [a.key]: { value: a.value, source: a.value ? "manual" : "missing" } } as Fields } : d)));
        clearTimeout(editTimers.current[a.id + a.key]);
        editTimers.current[a.id + a.key] = setTimeout(() => call(() => api.patch(`/api/pdf/${a.id}`, { fields: { [a.key]: a.value } })), 500);
        return;
      }
      case "industry":
        return void call(() => api.patch(`/api/pdf/${a.id}`, { industry: a.category }));
      case "emailVerified":
        return void call(() => api.patch(`/api/pdf/${a.id}`, { email_verified: a.on }), a.on ? "Đã xác minh email — web sẽ hiện email này" : "Đã bỏ xác minh — web sẽ ẩn email và form");
      case "docType":
        return void call(() => api.patch(`/api/pdf/${a.id}`, { doc_type: a.docType }), "Đã đọc lại theo loại phôi đã chọn");
      case "aiRead":
        return void call(() => api.post(`/api/pdf/${a.id}/ai-read`), "Đã gửi cho AI đọc bản scan");
      case "confirmMissing":
        return setFlags((fl) => ({ ...fl, [a.id]: { ...fl[a.id], confirm: a.on } }));
      case "criticalChecked":
        return setFlags((fl) => ({ ...fl, [a.id]: { ...fl[a.id], checked: a.on } }));
      case "save":
        return void save(a.id);
      case "saveAllValid":
        files.filter((f) => isCleanForBulk(f)).forEach((f) => save(f.id));
        return;
      case "retry": {
        const j = latest("pdf_save", Number(a.id));
        if (j) return void call(() => api.post(`/api/jobs/${j.id}/retry`), "Đã đưa lại vào hàng đợi — bước đã xong được giữ");
        return;
      }
      case "retryAll":
        files.filter((f) => f.status === "failed").forEach((f) => dispatch({ type: "retry", id: f.id }));
        return;
      case "autoSave":
        return setAutoSave(a.on);
      case "run":
        // running → pause saving (current step finishes); paused → resume
        return void call(() => api.post("/api/queue/pause", { kind: "pdf_save", on: !a.on }), a.on ? "Đã tiếp tục lưu" : "Đã tạm dừng lưu — bước đang chạy xong rồi dừng");
      case "tab":
        return; // the Sheet tab is server configuration (SHEET_TAB)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, jobs, onMessage, refresh, save]);

  const state: QueueState = {
    files, selectedId: selectedId ?? files[0]?.id ?? null, running: busy && !paused, autoSave, tab: "Phoi US",
    nextRow: 0,
  };
  return { state, dispatch, upload, error, refresh };
}
