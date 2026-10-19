"use client";

import { useEffect, useReducer } from "react";
import {
  FIELD_META, MOCK_FILES, MOCK_RESULTS, PROCESS_STEPS, RESCAN_SAMPLES, SAVE_STEPS, industryFromName, shortName, validate,
  type DocType, type FieldKey, type Fields, type IndustryKey, type PdfFile, type SHEET_TABS,
} from "@/lib/pdf-mock";

type SheetTab = (typeof SHEET_TABS)[number];

export type QueueState = {
  files: PdfFile[];
  selectedId: string | null;
  running: boolean;
  autoSave: boolean; // default OFF — every file goes through human review unless switched on
  tab: SheetTab;
  nextRow: number;
};

type Action =
  | { type: "add"; files: PdfFile[] }
  | { type: "select"; id: string }
  | { type: "run"; on: boolean }
  | { type: "tick" }
  | { type: "retry"; id: string }
  | { type: "retryAll" }
  | { type: "remove"; id: string }
  | { type: "edit"; id: string; key: FieldKey; value: string }
  | { type: "industry"; id: string; category: IndustryKey }
  | { type: "docType"; id: string; docType: DocType }
  | { type: "confirmMissing"; id: string; on: boolean }
  | { type: "criticalChecked"; id: string; on: boolean }
  | { type: "save"; id: string }
  | { type: "saveAllValid" }
  | { type: "autoSave"; on: boolean }
  | { type: "tab"; tab: SheetTab };

const MAX_PARALLEL = 2;
const SHEET_STEP = SAVE_STEPS.length - 1;

export type Blockers = {
  unknownType: boolean;
  criticalMissing: FieldKey[];
  format: FieldKey[];
  missing: FieldKey[]; // confirmable
  needCriticalCheck: boolean; // A or J read by AI from a scan
  unchecked: FieldKey[]; // read from an image (OCR / AI) and not yet ticked "đã kiểm tra"
};

export function saveBlockers(file: PdfFile): Blockers {
  const empty: Blockers = { unknownType: false, criticalMissing: [], format: [], missing: [], needCriticalCheck: false, unchecked: [] };
  if (!file.fields) return empty;
  const issues = validate(file.fields, file.docType);
  const of = (kind: string) => FIELD_META.map((m) => m.key).filter((k) => issues[k]?.level === "error" && issues[k]?.kind === kind);
  return {
    unknownType: file.docType === "unknown",
    criticalMissing: of("critical"),
    format: of("format"),
    missing: of("missing"),
    needCriticalCheck: (["A", "J"] as FieldKey[]).some((k) => file.fields![k].source === "ai"),
    unchecked: FIELD_META.map((m) => m.key).filter((k) => {
      const fl = file.fields![k];
      // a reading with several possible readings (OCR doubt) the owner has not settled — nothing else blocks
      return !!fl.value && !!fl.suspects?.length && fl.source !== "manual" && !fl.checked;
    }),
  };
}

export function canSave(file: PdfFile) {
  if (file.status !== "review") return false;
  const b = saveBlockers(file);
  return (
    !b.unknownType &&
    b.criticalMissing.length === 0 &&
    b.format.length === 0 &&
    (b.missing.length === 0 || !!file.confirmMissing) &&
    (!b.needCriticalCheck || !!file.criticalChecked) &&
    b.unchecked.length === 0
  );
}

/** Eligible for bulk/auto save: nothing to confirm, no warnings, nothing read by AI. */
const isClean = (file: PdfFile) => {
  if (file.status !== "review" || !file.fields || file.docType === "unknown") return false;
  if (Object.keys(validate(file.fields, file.docType)).length) return false;
  // nothing read from an image goes out unless the owner ticked it "đã kiểm tra"
  return !Object.values(file.fields).some((fl) => !!fl.value && !!fl.suspects?.length && fl.source !== "manual" && !fl.checked);
};

const startSaving = (f: PdfFile): PdfFile => ({ ...f, status: "saving", step: 0, progress: 0 });

function finishProcessing(f: PdfFile): PdfFile {
  if (f.outcome === "failed")
    return {
      ...f, status: "failed", failedAt: "process", progress: 100,
      error: "Bản scan quá mờ — AI không đọc được tên công ty và mã đăng ký. Không tự điền.",
    };
  const r = MOCK_RESULTS[f.id];
  if (r) return { ...f, status: "review", step: PROCESS_STEPS.length - 1, progress: 100, fields: r.fields, industry: r.industry, br: r.br };
  // Local file picked in the browser: this prototype does not read it — type values by hand.
  const blank: Fields = Object.fromEntries(
    FIELD_META.map((m) => [m.key, { value: "", source: "missing" }]),
  ) as Fields;
  return {
    ...f, status: "review", step: PROCESS_STEPS.length - 1, progress: 100, fields: blank,
    detection: f.detection ?? { confidence: 0, reason: "Bản thiết kế chưa đọc nội dung PDF thật — chọn loại phôi thủ công" },
  };
}

function tick(state: QueueState): QueueState {
  let { nextRow } = state;
  let files = state.files.map((f): PdfFile => {
    if (f.status === "processing") {
      const progress = f.progress + 34;
      if (progress < 100) return { ...f, progress };
      if (f.step < PROCESS_STEPS.length - 1) return { ...f, step: f.step + 1, progress: 0 };
      return finishProcessing(f);
    }
    if (f.status === "saving") {
      const progress = f.progress + 34;
      if (progress < 100) return { ...f, progress };
      if (f.step < SHEET_STEP) {
        // The Drive id is recorded once the upload is verified (end of step 2).
        const driveFileId = f.step === 2 ? f.driveFileId ?? `1Dv${f.id}${f.md5.slice(0, 6)}` : f.driveFileId;
        return { ...f, step: f.step + 1, progress: 0, driveFileId };
      }
      if (f.outcome === "sheetFail")
        return {
          ...f, status: "failed", failedAt: "sheet", progress: 100, outcome: undefined,
          error: "Google Sheets hết thời gian chờ khi ghi. PDF đã nằm trên Drive và đã lưu ID — thử lại chỉ ghi Sheet, không upload lại.",
        };
      return {
        ...f, status: "saved", progress: 100, sheetRow: nextRow++, error: undefined, failedAt: undefined,
        driveLink: `https://drive.google.com/file/d/${f.driveFileId}/view`,
      };
    }
    return f;
  });

  if (state.running) {
    let slots = MAX_PARALLEL - files.filter((f) => f.status === "processing").length;
    files = files.map((f) => (slots > 0 && f.status === "queued" ? (slots--, { ...f, status: "processing", step: 0, progress: 0 }) : f));
  }
  if (state.autoSave) files = files.map((f) => (isClean(f) ? startSaving(f) : f));

  const busy = files.some((f) => f.status === "queued" || f.status === "processing");
  return { ...state, files, nextRow, running: state.running && busy };
}

/** Retry resumes where it failed: a Sheet failure skips straight to the Sheet write. */
const retryFile = (f: PdfFile): PdfFile =>
  f.failedAt === "sheet" && f.driveFileId
    ? { ...f, status: "saving", step: SHEET_STEP, progress: 0, error: undefined }
    : { ...f, status: "queued", step: 0, progress: 0, error: undefined, failedAt: undefined, outcome: "review" };

function reducer(state: QueueState, a: Action): QueueState {
  const patch = (id: string, fn: (f: PdfFile) => PdfFile) => ({
    ...state, files: state.files.map((f) => (f.id === id ? fn(f) : f)),
  });

  switch (a.type) {
    case "add":
      return { ...state, files: [...a.files, ...state.files], selectedId: a.files[0]?.id ?? state.selectedId };
    case "select":
      return { ...state, selectedId: a.id };
    case "run":
      return { ...state, running: a.on };
    case "tick":
      return tick(state);
    case "retry":
      return patch(a.id, retryFile);
    case "retryAll":
      return { ...state, running: true, files: state.files.map((f) => (f.status === "failed" ? retryFile(f) : f)) };
    case "remove": {
      const files = state.files.filter((f) => f.id !== a.id);
      return { ...state, files, selectedId: state.selectedId === a.id ? (files[0]?.id ?? null) : state.selectedId };
    }
    case "edit":
      return patch(a.id, (f) => {
        if (!f.fields) return f;
        // Values stay plain text — never parsed as numbers, so leading zeros are kept.
        const fields = { ...f.fields, [a.key]: { value: a.value, source: a.value ? "manual" : "missing" } };
        if (a.key === "A" && f.fields.E.source === "auto") fields.E = { value: shortName(a.value), source: "auto" };
        const industry = a.key === "A" && (!f.industry || f.industry.source === "name") ? industryFromName(a.value) : f.industry;
        return { ...f, fields, industry };
      });
    case "industry":
      return patch(a.id, (f) => ({
        ...f,
        industry: { raw: f.industry?.raw ?? "", code: f.industry?.code, category: a.category, source: "manual" },
      }));
    case "docType":
      return patch(a.id, (f) => {
        const detection = { confidence: 100, reason: "Chọn thủ công", manual: true };
        // An unrecognised demo file is re-read with the chosen template.
        if (f.docType === "unknown" && !f.local && a.docType !== "unknown") {
          const r = RESCAN_SAMPLES[a.docType];
          return { ...f, docType: a.docType, detection, fields: r.fields, industry: r.industry, br: r.br };
        }
        return { ...f, docType: a.docType, detection };
      });
    case "confirmMissing":
      return patch(a.id, (f) => ({ ...f, confirmMissing: a.on }));
    case "criticalChecked":
      return patch(a.id, (f) => ({ ...f, criticalChecked: a.on }));
    case "save":
      return patch(a.id, (f) => (canSave(f) ? startSaving(f) : f));
    case "saveAllValid":
      return { ...state, files: state.files.map((f) => (isClean(f) ? startSaving(f) : f)) };
    case "autoSave":
      return { ...state, autoSave: a.on };
    case "tab":
      return { ...state, tab: a.tab };
  }
}

export const isCleanForBulk = isClean;

export function usePdfQueue() {
  const [state, dispatch] = useReducer(reducer, {
    files: MOCK_FILES,
    selectedId: "p5",
    running: true,
    autoSave: false,
    tab: "Phoi US",
    nextRow: 46,
  });

  const active = state.files.some((f) => f.status === "processing" || f.status === "saving") || state.running;
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => dispatch({ type: "tick" }), 650);
    return () => clearInterval(id);
  }, [active]);

  return { state, dispatch };
}

export type QueueDispatch = ReturnType<typeof usePdfQueue>["dispatch"];
