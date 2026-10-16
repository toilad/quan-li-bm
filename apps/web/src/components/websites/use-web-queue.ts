"use client";

/**
 * SSL + Website Builder state, backed by the backend:
 * - rows (B filled, C empty): GET /api/websites/rows   (503 "Chưa cấu hình" when Google is not set up)
 * - template choice:          POST /api/websites/choice (saved in the database; the build uses exactly this)
 * - run:                      POST /api/websites/run → one job per row; progress from GET /api/jobs?kind=web_build
 */
import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiError, api, errorText, type Job } from "@/lib/api";
import type { Nick } from "@/lib/domain-mock";
import type { Company } from "@/lib/mock-data";
import { TEMPLATE_BY_ID } from "@/lib/templates";
import { hostOf, type LogLine, type WebRow, type WebStatus } from "@/lib/web-mock";

export type AiProvider = "claude" | "openai";

export type WebState = {
  rows: WebRow[];
  batchLimit: number;
  provider: AiProvider;
  fallback: boolean;
  running: boolean;
  paused: boolean;
  selected: number | null;
  scan: { total: number; noB: number; hasC: number } | null;
  loadError: ApiError | null;
  message: string | null;
};

type ServerRow = { row: number; A: string; domain: string; nick: string | null; ip: string | null; detected: string; keyword: string | null; template: string; source: "auto" | "manual"; issue: string | null };
type Scan = { total: number; no_b: number; has_c: number; rows: ServerRow[] };
type ServerNick = { id: string; name: string; ip: string; hosting: string | null; cpanel_host: string; enabled: boolean; roots: { name: string; dns_host: Nick["roots"][number]["dnsHost"]; expires: string | null; apex_on_hosting: boolean; suspended: boolean }[] };

type Action =
  | { type: "server"; scan?: Scan | null; jobs?: Job[]; nicks?: Nick[]; error?: ApiError | null; paused?: boolean }
  | { type: "select"; row: number }
  | { type: "check"; row: number; on: boolean }
  | { type: "checkAll"; rows: number[]; on: boolean }
  | { type: "batchLimit"; n: number }
  | { type: "provider"; provider: AiProvider }
  | { type: "fallback"; on: boolean }
  | { type: "message"; text: string | null }
  | { type: "template"; rows: number[]; id: string }
  | { type: "resetTemplate"; row: number }
  | { type: "start" }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "retry"; row: number }
  | { type: "retryAll" }
  | { type: "resolveLive"; row: number; note: string };

export type WebDispatch = (a: Action) => void;

export const templateEditable = (r: WebRow) => !r.uploaded && !r.jobId && (r.status === "idle" || r.status === "failed");

export function webIssue(r: WebRow): string | null {
  if (r.status === "done" || r.status === "conflict") return null;
  if (!r.domain.trim()) return "Cột B trống";
  if (!r.host) return "Miền ở B không thuộc miền gốc nào của các nick — không biết hosting nào";
  if (!r.host.nick.enabled) return `Nick ${r.host.nick.name} đang tắt`;
  return null;
}

const STEP: Record<string, number> = {
  "Kiểm tra DNS + document root": 0, "Tạo nội dung bằng AI": 2, "Bật SSL (AutoSSL) + kiểm tra HTTPS": 6, "Đọc lại ô C rồi ghi": 8,
};
const stepOf = (name: string | null) => (name?.startsWith("Dựng HTML") ? 5 : STEP[name ?? ""] ?? 0);

function companyOf(row: number, A: string, domain: string): Company {
  return { row, A, B: domain, C: "", D: "", E: "", F: "", G: "", H: "", I: "", J: "", K: "", L: "" } as Company;
}

function applyJob(base: WebRow, j: Job): WebRow {
  const st = j.state as { doc_root?: string; doc_root_api?: string; uploaded?: boolean; built_template?: string; https_ok?: boolean; written_c?: string; live_not_written?: { url: string; found_c: string } };
  const status: WebStatus = j.status === "queued" ? "queued" : j.status === "running" ? "running" : j.status === "done" ? "done" : j.status === "conflict" ? "conflict" : "failed";
  const log: LogLine[] = (j.logs ?? []).map((l) => ({ t: new Date(l.at).toLocaleTimeString("vi-VN", { hour12: false }), msg: l.message, tone: l.level }));
  return {
    ...base, templateId: String(j.payload.template ?? base.templateId), status, step: stepOf(j.step), progress: status === "running" ? 50 : 100,
    docRoot: st.doc_root, docRootApi: st.doc_root_api, uploaded: !!st.uploaded, contentReady: !!st.uploaded, sslIssued: !!st.https_ok,
    builtTemplate: st.built_template, writtenC: st.written_c,
    liveNotWritten: st.live_not_written ? { url: st.live_not_written.url, foundC: st.live_not_written.found_c, at: "" } : undefined,
    error: status === "failed" ? (j.status === "blocked" ? `Dừng: ${j.error}` : j.error ?? undefined) : status === "conflict" ? j.error ?? undefined : undefined,
    log, checked: false, jobId: j.id,
  };
}

function reducer(s: WebState, a: Action): WebState {
  const patch = (row: number, fn: (r: WebRow) => WebRow) => ({ ...s, rows: s.rows.map((r) => (r.row === row ? fn(r) : r)) });
  switch (a.type) {
    case "server": {
      const next = { ...s };
      if (a.error !== undefined) next.loadError = a.error;
      if (a.paused !== undefined) next.paused = a.paused;
      if (a.scan !== undefined || a.jobs) {
        const prev = new Map(s.rows.map((r) => [r.row, r]));
        const latest = new Map<number, Job>();
        for (const j of a.jobs ?? []) {
          const row = Number(j.payload.row);
          if (!latest.has(row) || latest.get(row)!.id < j.id) latest.set(row, j);
        }
        const rows: WebRow[] = [];
        const seen = new Set<number>();
        for (const x of a.scan?.rows ?? []) {
          const old = prev.get(x.row);
          const t = TEMPLATE_BY_ID[x.detected] ?? TEMPLATE_BY_ID["corporate-firm"];
          const base: WebRow = {
            row: x.row, company: companyOf(x.row, x.A, x.domain), domain: x.domain,
            host: a.nicks ? hostOf(x.domain, a.nicks) : old?.host ?? null,
            detection: { template: t, keyword: x.keyword },
            templateId: old && !old.jobId ? old.templateId : x.template, templateSource: old && !old.jobId ? old.templateSource : x.source,
            status: "idle", step: 0, progress: 0, contentReady: false, uploaded: false, sslIssued: false, log: [], checked: old?.checked ?? false,
          };
          const j = latest.get(x.row);
          rows.push(j ? applyJob(base, j) : base);
          seen.add(x.row);
        }
        for (const [row, j] of latest) {
          if (seen.has(row)) continue; // C written → no longer in the scan; keep the result visible
          const domain = String(j.payload.domain ?? "");
          const t = TEMPLATE_BY_ID[String(j.payload.template)] ?? TEMPLATE_BY_ID["corporate-firm"];
          rows.push(applyJob({
            row, company: companyOf(row, "", domain), domain, host: a.nicks ? hostOf(domain, a.nicks) : null,
            detection: { template: t, keyword: null }, templateId: t.id, templateSource: "manual", status: "idle", step: 0, progress: 0,
            contentReady: false, uploaded: false, sslIssued: false, log: [], checked: false,
          }, j));
        }
        next.rows = rows.sort((x, y) => x.row - y.row);
        if (a.scan) next.scan = { total: a.scan.total, noB: a.scan.no_b, hasC: a.scan.has_c };
        next.running = rows.some((r) => r.status === "queued" || r.status === "running");
      }
      return next;
    }
    case "select":
      return { ...s, selected: a.row };
    case "check":
      return patch(a.row, (r) => ({ ...r, checked: a.on && r.status === "idle" && !r.jobId && !webIssue(r) }));
    case "checkAll":
      return { ...s, rows: s.rows.map((r) => (a.rows.includes(r.row) ? { ...r, checked: a.on && r.status === "idle" && !r.jobId && !webIssue(r) } : r)) };
    case "batchLimit":
      return { ...s, batchLimit: a.n };
    case "message":
      return { ...s, message: a.text };
    case "template":
      return { ...s, rows: s.rows.map((r) => (a.rows.includes(r.row) && templateEditable(r) ? { ...r, templateId: a.id, templateSource: a.id === r.detection.template.id ? "auto" : "manual" } : r)) };
    case "resetTemplate":
      return patch(a.row, (r) => (templateEditable(r) ? { ...r, templateId: r.detection.template.id, templateSource: "auto" } : r));
    default:
      return s;
  }
}

const toNicks = (server: ServerNick[]): Nick[] => server.map((n) => ({
  id: n.id, name: n.name, email: "", ip: n.ip, hosting: n.hosting ?? undefined, cpanelHost: n.cpanel_host, cpanelUser: "",
  enabled: n.enabled, status: "untested", usedToday: 0, dailyLimit: null, weight: 1, subdomains: 0, lastCheck: "—",
  api: { dns: { state: "untested" }, cpanel: { state: "untested" } },
  roots: n.roots.map((r) => ({ name: r.name, dnsHost: r.dns_host, expires: r.expires ?? "2999-01-01", apexOnHosting: r.apex_on_hosting, suspended: r.suspended })),
}));

export function useWebQueue() {
  const [state, local] = useReducer(reducer, undefined, (): WebState => ({
    rows: [], batchLimit: 30, provider: "claude", fallback: true, running: false, paused: false, selected: null, scan: null, loadError: null, message: null,
  }));
  const ref = useRef(state);
  ref.current = state;

  const refresh = useCallback(async () => {
    const [nicks, jobs] = await Promise.all([
      api.get<ServerNick[]>("/api/domains/roots").then(toNicks).catch(() => undefined),
      api.get<Job[]>("/api/jobs?kind=web_build").catch(() => [] as Job[]),
    ]);
    const q = await api.get<{ paused: string[] }>("/api/queue").catch(() => ({ paused: [] as string[] }));
    local({ type: "server", paused: q.paused.includes("*") || q.paused.includes("web_build") });
    try {
      const scan = await api.get<Scan>("/api/websites/rows");
      local({ type: "server", scan, jobs, nicks, error: null });
    } catch (e) {
      local({ type: "server", scan: null, jobs, nicks, error: e instanceof ApiError ? e : new ApiError("error", errorText(e)) });
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, state.running ? 3000 : 15000);
    return () => clearInterval(id);
  }, [refresh, state.running]);

  const say = (text: string) => local({ type: "message", text });

  const dispatch: WebDispatch = useCallback((a: Action) => {
    const s = ref.current;
    switch (a.type) {
      case "template": {
        local(a);
        s.rows.filter((r) => a.rows.includes(r.row) && templateEditable(r)).forEach((r) =>
          api.post("/api/websites/choice", { domain: r.domain, template: a.id, detected: r.detection.template.id }).catch((e) => say(errorText(e))));
        return;
      }
      case "resetTemplate": {
        local(a);
        const r = s.rows.find((x) => x.row === a.row);
        if (r) api.post("/api/websites/choice", { domain: r.domain, template: r.detection.template.id, detected: r.detection.template.id }).catch((e) => say(errorText(e)));
        return;
      }
      case "start": {
        const items = s.rows.filter((r) => r.checked && r.status === "idle" && !r.jobId && !webIssue(r)).slice(0, s.batchLimit)
          .map((r) => ({ row: r.row, domain: r.domain, company: r.company.A, template: r.templateId }));
        api.post<{ queued: unknown[]; refused: Record<string, string> }>("/api/websites/run", { items })
          .then((r) => say(`Đã đưa ${r.queued.length} site vào hàng đợi backend${Object.keys(r.refused).length ? ` · từ chối: ${Object.values(r.refused).join("; ")}` : ""}`))
          .catch((e) => say(errorText(e)))
          .finally(refresh);
        return;
      }
      case "retry": {
        const r = s.rows.find((x) => x.row === a.row);
        if (r?.jobId) api.post(`/api/jobs/${r.jobId}/retry`).catch((e) => say(errorText(e))).finally(refresh);
        return;
      }
      case "retryAll":
        s.rows.filter((r) => r.status === "failed" && r.jobId).forEach((r) => api.post(`/api/jobs/${r.jobId}/retry`).catch(() => {}));
        setTimeout(refresh, 500);
        return;
      case "pause":
      case "resume":
        api.post("/api/queue/pause", { kind: "web_build", on: a.type === "pause" })
          .then(() => say(a.type === "pause" ? "Đã tạm dừng: bước đang chạy xong rồi dừng, các bước đã xong được giữ" : "Đã tiếp tục hàng đợi"))
          .catch((e) => say(errorText(e))).finally(refresh);
        return;
      case "resolveLive":
        say("Chưa khả dụng trong bản này — thao tác này cần làm ở server");
        return;
      case "provider":
      case "fallback":
        return; // Claude only; refusal fallback is always on (server-side)
      default:
        local(a);
    }
  }, [refresh]);

  return { state, dispatch };
}
