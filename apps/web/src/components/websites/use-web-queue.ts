"use client";

import { useEffect, useReducer } from "react";
import { TEMPLATE_BY_ID } from "@/lib/templates";
import { WEB_STEPS, demoDocRootFor, initialWebRows, type LogLine, type WebRow } from "@/lib/web-mock";

export type AiProvider = "claude" | "openai";

export type WebState = {
  rows: WebRow[];
  /** Rows taken per run (legacy: 30/lượt). */
  batchLimit: number;
  provider: AiProvider;
  /** Fall back to the other provider when the main one fails. */
  fallback: boolean;
  running: boolean;
  paused: boolean;
  selected: number | null;
};

type Action =
  | { type: "tick" }
  | { type: "select"; row: number }
  | { type: "check"; row: number; on: boolean }
  | { type: "checkAll"; rows: number[]; on: boolean }
  | { type: "template"; rows: number[]; id: string }
  | { type: "resetTemplate"; row: number }
  | { type: "batchLimit"; n: number }
  | { type: "provider"; provider: AiProvider }
  | { type: "fallback"; on: boolean }
  | { type: "start" }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "retry"; row: number }
  | { type: "retryAll" }
  | { type: "resolveLive"; row: number; note: string };

const MAX_PARALLEL = 2;
const now = () => new Date().toLocaleTimeString("vi-VN", { hour12: false });
const line = (msg: string, tone: LogLine["tone"] = "info"): LogLine => ({ t: now(), msg, tone });

/** Template can change only before anything was uploaded. */
export const templateEditable = (r: WebRow) => !r.uploaded && (r.status === "idle" || r.status === "failed");

/** Problems visible before running — the row can't be queued while one exists. */
export function webIssue(r: WebRow): string | null {
  if (r.status === "done" || r.status === "conflict") return null;
  if (!r.domain.trim()) return "Cột B trống";
  if (r.company.C.trim()) return "Cột C đã có — không xử lý";
  if (!r.host) return "Miền ở B không thuộc miền gốc nào của các nick — không biết hosting nào";
  if (!r.host.nick.enabled) return `Nick ${r.host.nick.name} đang tắt`;
  if (r.host.nick.api.cpanel.state === "blocked") return `Bị chặn — ${r.host.nick.name}: cPanel API chưa có quyền`;
  return null;
}

function advance(r: WebRow, s: WebState): WebRow {
  const fail = (error: string): WebRow => ({ ...r, status: "failed", progress: 100, error, log: [...r.log, line(error, "err")] });
  const next = (msg: string, patch: Partial<WebRow> = {}, tone: LogLine["tone"] = "ok"): WebRow =>
    ({ ...r, ...patch, step: r.step + 1, progress: 0, log: [...r.log, line(msg, tone)] });
  const host = r.host!;
  const t = TEMPLATE_BY_ID[r.templateId];
  const ai = s.provider === "claude" ? "Claude" : "OpenAI";

  switch (r.step) {
    case 0:
      if (r.outcome === "dnsMismatch")
        return fail(`DNS: ${r.domain} không trỏ về ${host.nick.ip} (hosting ${host.nick.name}) — dừng, không upload. Kiểm tra lại ô B.`);
      return next(`DNS ${r.domain} → ${host.nick.ip} (${host.nick.name}) đúng`);
    case 1: {
      if (r.docRoot) return next(`Document root đã đọc: ~/${r.docRoot}`, {}, "info");
      const isSub = r.domain !== host.root.name;
      const api = isSub ? "SubDomain::listsubdomains" : "DomainInfo::single_domain_data";
      if (r.outcome === "notOnCpanel")
        return fail(`cPanel ${api}: không có ${r.domain} trên tài khoản hosting ${host.nick.name} — miền chưa được tạo trên hosting. Dừng, không upload, C giữ trống.`);
      const docRoot = demoDocRootFor(r);
      return next(`cPanel ${api}: document root ~/${docRoot}`, { docRoot, docRootApi: api });
    }
    case 2:
      if (r.contentReady) return next("Nội dung đã có từ lượt trước → bỏ qua, không gọi AI lại", {}, "info");
      return next(`${ai}: viết ${6} trang theo mẫu ${t.name} (ngành: ${r.detection.keyword ?? "chung"})`);
    case 3:
      if (r.contentReady) return next("Nội dung đã kiểm tra từ lượt trước", {}, "info");
      if (r.outcome === "aiRegenerate")
        return {
          ...r, step: 2, progress: 0, outcome: undefined,
          log: [...r.log, line("Kiểm tra: AI thêm “15 năm kinh nghiệm” — không có trong Sheet → loại, tạo lại (lần 2/2)", "warn")],
        };
      return next("Không có giải thưởng / khách hàng / số liệu bịa · liên hệ khớp Sheet (A, D, F–I)", { contentReady: true });
    case 4:
      return next(`Dựng HTML bằng mẫu đã chọn: ${t.name} · 6 trang · bố cục ${t.hero}`, { builtTemplate: t.id });
    case 5:
      if (r.uploaded) return next("Đã upload từ lượt trước → bỏ qua", {}, "info");
      if (!r.docRoot) return fail("Chưa xác minh document root — không upload vào đường dẫn đoán trước.");
      if (r.builtTemplate !== r.templateId) return fail("HTML không khớp mẫu đã chọn — dựng lại trước khi upload.");
      return next(`cPanel ${host.nick.cpanelHost} Fileman::upload_files → ~/${r.docRoot}`, { uploaded: true });
    case 6:
      if (r.sslIssued) return next("Chứng chỉ đã có", {}, "info");
      if (r.outcome === "sslPendingOnce")
        return { ...fail("AutoSSL chưa cấp chứng chỉ — DNS mới trỏ chưa đủ lâu. Website đã upload; C giữ trống. Thử lại sau."), outcome: undefined };
      return next(`AutoSSL: đã cấp chứng chỉ cho ${r.domain}`, { sslIssued: true });
    case 7:
      return next(`HTTPS https://${r.domain} → 200 · chứng chỉ hợp lệ · đúng tiêu đề “${r.company.A}”`);
    default: {
      const url = `https://${r.domain}`;
      if (r.outcome === "conflictAtWrite") {
        const foundC = `https://${r.domain.split(".")[0]}-cu.example.com`;
        return {
          ...r, status: "conflict", progress: 100, outcome: undefined,
          liveNotWritten: { url, foundC, at: now() },
          error: `Ô C dòng #${r.row} đã có “${foundC}” khi ghi — không ghi đè. Website ${url} đang chạy, lưu vào “Website chưa gắn”.`,
          log: [...r.log, line(`Đọc lại ô C: đã có “${foundC}” → xung đột, không ghi`, "warn")],
        };
      }
      return { ...r, status: "done", progress: 100, writtenC: url, error: undefined, log: [...r.log, line(`Ô C vẫn trống → ghi C = ${url} · cột B giữ nguyên`, "ok")] };
    }
  }
}

function tick(s: WebState): WebState {
  let rows = s.rows.map((r) => {
    if (r.status !== "running") return r;
    if (r.progress < 100) return { ...r, progress: Math.min(100, r.progress + 50) };
    if (s.paused) return r;
    return advance(r, s);
  });
  // One site at a time per hosting account, at most MAX_PARALLEL accounts at once.
  if (s.running && !s.paused) {
    const busy = new Set(rows.filter((r) => r.status === "running").map((r) => r.host?.nick.id));
    let slots = MAX_PARALLEL - busy.size;
    rows = rows.map((r) => {
      if (slots <= 0 || r.status !== "queued" || !r.host || busy.has(r.host.nick.id)) return r;
      busy.add(r.host.nick.id);
      slots--;
      return { ...r, status: "running", progress: 0, log: [...r.log, line(`Bắt đầu · hosting ${r.host.nick.name} (${r.host.nick.ip})`)] };
    });
  }
  const active = rows.some((r) => r.status === "running" || r.status === "queued");
  return { ...s, rows, running: s.running && active };
}

const retryRow = (r: WebRow): WebRow =>
  r.status === "failed" && !webIssue(r)
    ? { ...r, status: "queued", progress: 0, error: undefined, log: [...r.log, line(`Thử lại từ bước “${WEB_STEPS[r.step]}” — bước đã xong được giữ`)] }
    : r;

function reducer(s: WebState, a: Action): WebState {
  const patch = (row: number, fn: (r: WebRow) => WebRow) => ({ ...s, rows: s.rows.map((r) => (r.row === row ? fn(r) : r)) });
  switch (a.type) {
    case "tick":
      return tick(s);
    case "select":
      return { ...s, selected: a.row };
    case "check":
      return patch(a.row, (r) => ({ ...r, checked: a.on && r.status === "idle" && !webIssue(r) }));
    case "checkAll":
      return { ...s, rows: s.rows.map((r) => (a.rows.includes(r.row) ? { ...r, checked: a.on && r.status === "idle" && !webIssue(r) } : r)) };
    case "template":
      return { ...s, rows: s.rows.map((r) => (a.rows.includes(r.row) && templateEditable(r) ? { ...r, templateId: a.id, templateSource: a.id === r.detection.template.id ? "auto" : "manual", contentReady: false, builtTemplate: undefined } : r)) };
    case "resetTemplate":
      return patch(a.row, (r) => (templateEditable(r) ? { ...r, templateId: r.detection.template.id, templateSource: "auto", contentReady: false, builtTemplate: undefined } : r));
    case "batchLimit":
      return { ...s, batchLimit: a.n };
    case "provider":
      return { ...s, provider: a.provider };
    case "fallback":
      return { ...s, fallback: a.on };
    case "start": {
      let left = s.batchLimit;
      return {
        ...s, running: true, paused: false,
        rows: s.rows.map((r) => {
          if (!r.checked || r.status !== "idle" || webIssue(r) || left <= 0) return r;
          left--;
          return { ...r, status: "queued", checked: false };
        }),
      };
    }
    case "pause":
      return { ...s, paused: true };
    case "resume":
      return { ...s, paused: false, running: true };
    case "retry":
      return { ...patch(a.row, retryRow), running: true, paused: false };
    case "retryAll":
      return { ...s, running: true, paused: false, rows: s.rows.map(retryRow) };
    case "resolveLive":
      return patch(a.row, (r) => (r.liveNotWritten ? { ...r, liveNotWritten: { ...r.liveNotWritten, resolved: a.note }, log: [...r.log, line(`Đánh dấu đã xử lý: ${a.note}`)] } : r));
  }
}

export function useWebQueue() {
  const [state, dispatch] = useReducer(reducer, undefined, (): WebState => ({
    rows: initialWebRows(),
    batchLimit: 30,
    provider: "claude",
    fallback: true,
    running: false, // nothing runs on open — only after "Xác nhận chạy"
    paused: false,
    selected: null,
  }));
  const active = state.running || state.rows.some((r) => r.status === "running");
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => dispatch({ type: "tick" }), 600);
    return () => clearInterval(id);
  }, [active]);
  return { state, dispatch };
}

export type WebDispatch = ReturnType<typeof useWebQueue>["dispatch"];
