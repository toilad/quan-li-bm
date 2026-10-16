"use client";

import { useEffect, useReducer } from "react";
import {
  MOCK_FILES, MOCK_RESULTS, PROCESS_STEPS, SAVE_STEPS, emptyFields, shortName, validate,
  type FieldKey, type PdfFile, type SHEET_TABS,
} from "@/lib/pdf-mock";

type SheetTab = (typeof SHEET_TABS)[number];

export type QueueState = {
  files: PdfFile[];
  selectedId: string | null;
  running: boolean;
  autoSave: boolean;
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
  | { type: "confirmMissing"; id: string; on: boolean }
  | { type: "save"; id: string }
  | { type: "saveAllValid" }
  | { type: "autoSave"; on: boolean }
  | { type: "tab"; tab: SheetTab };

const MAX_PARALLEL = 2;

/** Blocking problems: wrong format must be fixed; missing values need explicit confirmation. */
export function saveBlockers(file: PdfFile) {
  if (!file.fields) return { format: 0, missing: 0 };
  const issues = Object.entries(validate(file.fields));
  const missing = issues.filter(([k, i]) => i?.level === "error" && !file.fields![k as FieldKey].value.trim()).length;
  const format = issues.filter(([k, i]) => i?.level === "error" && file.fields![k as FieldKey].value.trim()).length;
  return { format, missing };
}

export const canSave = (file: PdfFile) => {
  if (file.status !== "review") return false;
  const b = saveBlockers(file);
  return b.format === 0 && (b.missing === 0 || !!file.confirmMissing);
};

const isClean = (file: PdfFile) => file.status === "review" && !!file.fields && Object.keys(validate(file.fields)).length === 0;

const startSaving = (f: PdfFile): PdfFile => ({ ...f, status: "saving", step: 0, progress: 0, drive: "uploading" });

function finishProcessing(f: PdfFile): PdfFile {
  if (f.outcome === "failed")
    return {
      ...f, status: "failed", progress: 100,
      error: "Bản scan 4 trang, chữ quá mờ — AI không đọc được tên công ty và mã đăng ký. Không tự điền.",
    };
  const fields = MOCK_RESULTS[f.id] ?? emptyFields();
  return { ...f, status: "review", step: PROCESS_STEPS.length - 1, progress: 100, fields };
}

function tick(state: QueueState): QueueState {
  let { nextRow } = state;
  let files = state.files.map((f): PdfFile => {
    if (f.status === "processing") {
      const progress = f.progress + 25;
      if (progress < 100) return { ...f, progress };
      if (f.step < PROCESS_STEPS.length - 1) return { ...f, step: f.step + 1, progress: 0 };
      return finishProcessing(f);
    }
    if (f.status === "saving") {
      const progress = f.progress + 34;
      if (progress < 100) return { ...f, progress };
      if (f.step < SAVE_STEPS.length - 1) return { ...f, step: f.step + 1, progress: 0, drive: "verified" };
      return {
        ...f, status: "saved", progress: 100, drive: "verified",
        sheetRow: nextRow++, driveLink: `https://drive.google.com/file/d/demo-${f.id}/view`,
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
      return patch(a.id, (f) => ({ ...f, status: "queued", step: 0, progress: 0, error: undefined, outcome: "review" }));
    case "retryAll":
      return {
        ...state,
        running: true,
        files: state.files.map((f) =>
          f.status === "failed" ? { ...f, status: "queued", step: 0, progress: 0, error: undefined, outcome: "review" } : f,
        ),
      };
    case "remove": {
      const files = state.files.filter((f) => f.id !== a.id);
      return { ...state, files, selectedId: state.selectedId === a.id ? (files[0]?.id ?? null) : state.selectedId };
    }
    case "edit":
      return patch(a.id, (f) => {
        if (!f.fields) return f;
        const fields = { ...f.fields, [a.key]: { value: a.value, source: a.value ? "manual" : "missing" } };
        // Column E follows A until someone edits E by hand.
        if (a.key === "A" && f.fields.E.source === "auto") fields.E = { value: shortName(a.value), source: "auto" };
        return { ...f, fields };
      });
    case "confirmMissing":
      return patch(a.id, (f) => ({ ...f, confirmMissing: a.on }));
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
