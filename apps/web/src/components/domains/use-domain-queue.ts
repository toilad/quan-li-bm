"use client";

/**
 * Domain Manager state, backed by the real backend:
 * - root domains + ticks:  GET /api/domains/roots, POST /api/domains/roots/select
 * - Sheet rows (B empty):  GET /api/domains/rows   (503 "Chưa cấu hình" when Google is not set up)
 * - run:                   POST /api/domains/run   → one job per row; progress from GET /api/jobs?kind=domain_create
 * Only planning (which root / which label per row, which rows are checked) stays in the browser.
 */
import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiError, api, errorText, type Job } from "@/lib/api";
import {
  DOMAIN_STEPS, EXISTING_RECORDS, findRoot, labelIssue, quotaFull, rootIssue, rootPool, slugFor,
  type DomainRow, type DnsHost, type LogLine, type Nick, type RootRef, type RowStatus, type SlugRule,
} from "@/lib/domain-mock";
import type { Company } from "@/lib/mock-data";

export type Strategy = "single" | "roundRobin" | "weighted";

export type DomainState = {
  rows: DomainRow[];
  nicks: Nick[];
  selectedRoots: string[];
  selectionLoaded: boolean;
  lastSync: string;
  rule: SlugRule;
  batchLimit: number;
  running: boolean;
  paused: boolean;
  selected: number | null;
  created: Record<string, string[]>;
  /** Domains already in column B (live Sheet) — a new subdomain must not repeat one. */
  existingB: string[];
  scan: { total: number; withB: number; excluded: number; tab: string } | null;
  loadError: ApiError | null;
  message: string | null;
};

type ServerRoot = { name: string; dns_host: DnsHost; expires: string | null; apex_on_hosting: boolean; suspended: boolean; selected: boolean; busy: boolean };
type ServerNick = { id: string; name: string; ip: string; hosting: string | null; cpanel_host: string; enabled: boolean; roots: ServerRoot[] };
type ScanRow = { row: number; A: string; D: string; E: string; F: string; G: string; H: string; I: string; J: string; K: string; flags: string[]; label: string };
type Scan = { total: number; with_b: number; rows: ScanRow[]; excluded: { row: number }[]; existing_b: string[]; tab: string };

type Action =
  | { type: "server"; nicks?: Nick[]; selected?: string[]; scan?: Scan | null; jobs?: Job[]; error?: ApiError | null }
  | { type: "select"; row: number }
  | { type: "check"; row: number; on: boolean }
  | { type: "checkFirst"; n: number; skipFlagged: boolean }
  | { type: "uncheckAll" }
  | { type: "rule"; rule: SlugRule }
  | { type: "batchLimit"; n: number }
  | { type: "root"; row: number; root: string }
  | { type: "slug"; row: number; value: string }
  | { type: "resetSlug"; row: number }
  | { type: "strategy"; strategy: Strategy; root?: string }
  | { type: "message"; text: string | null }
  // server actions (handled by the hook wrapper)
  | { type: "start" }
  | { type: "retry"; row: number }
  | { type: "retryAll" }
  | { type: "pickRoots"; roots: string[]; on: boolean }
  | { type: "sync" }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "resolveOrphan"; row: number; note: string }
  | { type: "toggleNick"; id: string }
  | { type: "saveNick"; nick: Nick }
  | { type: "testNick"; id: string };

export type DomainDispatch = (a: Action) => void;

export const labelOf = (r: DomainRow, rule: SlugRule) => r.slugOverride ?? slugFor(r.company, rule);
export const fqdnOf = (r: DomainRow, s: Pick<DomainState, "rule">) => `${labelOf(r, s.rule)}.${r.root}`;
export const nickOfRow = (r: DomainRow, nicks: Nick[]): Nick | null => findRoot(r.root, nicks)?.nick ?? null;
export const usablePool = (s: Pick<DomainState, "nicks" | "selectedRoots">): RootRef[] => rootPool(s.nicks, s.selectedRoots);

export const rootBusy = (root: string, rows: DomainRow[]) =>
  rows.some((r) => r.root === root && (r.status === "queued" || r.status === "running" || (r.status === "failed" && r.dnsCreated)));

export function rootGate(r: DomainRow, s: Pick<DomainState, "nicks" | "selectedRoots">): string | null {
  if (r.dnsCreated) return null;
  if (!r.root) return "Chưa gán miền gốc — tích chọn miền ở bảng “Miền gốc dùng để tạo miền phụ”";
  const ref = findRoot(r.root, s.nicks);
  if (!ref) return `Không tìm thấy miền gốc ${r.root}`;
  if (!s.selectedRoots.includes(r.root)) return `Miền gốc ${r.root} chưa được tích chọn — chọn miền khác`;
  const issue = rootIssue(ref.root, ref.nick);
  return issue ? `Bị chặn — ${r.root}: ${issue}` : null;
}

export function previewIssue(r: DomainRow, s: DomainState): string | null {
  if (r.status === "done" || r.status === "conflict") return null;
  const label = labelOf(r, s.rule);
  const bad = labelIssue(label);
  if (bad) return s.rule === "columnE" && !r.company.E.trim() ? "Cột E trống — chọn cách tạo khác hoặc sửa tay" : bad;
  const gate = rootGate(r, s);
  if (gate) return gate;
  if (!r.dnsCreated && (EXISTING_RECORDS[r.root] ?? []).includes(label)) return `Đã có bản ghi “${label}” trên ${r.root}`;
  const fqdn = fqdnOf(r, s);
  if (s.existingB.includes(fqdn)) return "Trùng tên miền đã có ở cột B của dòng khác";
  if (s.rows.some((o) => o.row !== r.row && o.status !== "done" && o.status !== "conflict" && fqdnOf(o, s) === fqdn)) return "Trùng với dòng khác trong danh sách";
  return null;
}

const editable = (r: DomainRow) => !r.dnsCreated && (r.status === "idle" || r.status === "failed");

const STEP_INDEX: Record<string, number> = {
  "Kiểm tra trước khi tạo": 0, "Tạo bản ghi A": 1, "Tạo miền trên cPanel": 2, "Xác minh DNS trỏ đúng IP": 3, "Đọc lại ô B rồi ghi": 4,
};

function companyOf(x: Partial<ScanRow> & { row: number; A: string }): Company {
  return {
    row: x.row, A: x.A, B: "", C: "", D: x.D ?? "", E: x.E ?? "", F: x.F ?? "", G: x.G ?? "", H: x.H ?? "", I: x.I ?? "", J: x.J ?? "", K: x.K ?? "", L: "",
  } as Company;
}

function fromJob(base: DomainRow, j: Job): DomainRow {
  const st = j.state as { dns_created?: boolean; host_created?: boolean; written_b?: string; orphan?: { fqdn: string; found_b: string } };
  const status: RowStatus =
    j.status === "queued" ? "queued" : j.status === "running" ? "running" : j.status === "done" ? "done" : j.status === "conflict" ? "conflict" : "failed";
  const log: LogLine[] = (j.logs ?? []).map((l) => ({ t: new Date(l.at).toLocaleTimeString("vi-VN", { hour12: false }), msg: l.message, tone: l.level }));
  return {
    ...base,
    root: String(j.payload.root ?? base.root), slugOverride: String(j.payload.label ?? ""),
    status, step: STEP_INDEX[j.step ?? ""] ?? 0, progress: status === "running" ? 50 : 100,
    dnsCreated: !!st.dns_created, hostCreated: !!st.host_created, writtenB: st.written_b,
    error: status === "failed" ? (j.status === "blocked" ? `Dừng: ${j.error}` : j.error ?? undefined) : status === "conflict" ? j.error ?? undefined : undefined,
    orphan: st.orphan ? { fqdn: st.orphan.fqdn, nick: "", ip: "", dns: !!st.dns_created, host: !!st.host_created, foundB: st.orphan.found_b, at: "" } : undefined,
    log, checked: false, jobId: j.id,
  } as DomainRow;
}

function reducer(s: DomainState, a: Action): DomainState {
  const patch = (row: number, fn: (r: DomainRow) => DomainRow) => ({ ...s, rows: s.rows.map((r) => (r.row === row ? fn(r) : r)) });
  switch (a.type) {
    case "server": {
      const next = { ...s };
      if (a.nicks) next.nicks = a.nicks;
      if (a.selected) { next.selectedRoots = a.selected; next.selectionLoaded = true; }
      if (a.error !== undefined) next.loadError = a.error;
      if (a.scan !== undefined || a.jobs) {
        const scan = a.scan === undefined ? null : a.scan;
        const prev = new Map(s.rows.map((r) => [r.row, r]));
        const latest = new Map<number, Job>();
        for (const j of a.jobs ?? []) {
          const row = Number(j.payload.row);
          if (!latest.has(row) || latest.get(row)!.id < j.id) latest.set(row, j);
        }
        const rows: DomainRow[] = [];
        const seen = new Set<number>();
        const scanRows = scan ? scan.rows : s.rows.filter((r) => !r.jobId).map((r) => ({ ...r.company, flags: r.flags, label: "" } as unknown as ScanRow));
        for (const x of scanRows) {
          const old = prev.get(x.row);
          const base: DomainRow = old && !old.jobId
            ? { ...old, company: companyOf(x), flags: x.flags }
            : { row: x.row, company: companyOf(x), flags: x.flags, root: "", status: "idle", step: 0, progress: 0, dnsCreated: false, hostCreated: false, log: [], checked: false };
          const j = latest.get(x.row);
          rows.push(j ? fromJob(base, j) : base);
          seen.add(x.row);
        }
        // Rows whose B was just written are no longer in the scan: keep showing the job result.
        for (const [row, j] of latest) {
          if (seen.has(row)) continue;
          const company = companyOf({ row, A: String(j.payload.company ?? "") });
          rows.push(fromJob({ row, company, flags: [], root: "", status: "idle", step: 0, progress: 0, dnsCreated: false, hostCreated: false, log: [], checked: false }, j));
        }
        rows.sort((x, y) => x.flags.length - y.flags.length || x.row - y.row);
        next.rows = rows;
        if (scan) {
          next.existingB = scan.existing_b;
          next.scan = { total: scan.total, withB: scan.with_b, excluded: scan.excluded.length, tab: scan.tab };
        }
        next.running = rows.some((r) => r.status === "queued" || r.status === "running");
        next.lastSync = new Date().toLocaleTimeString("vi-VN", { hour12: false });
      }
      // Rows without a usable root get the ticked roots in turn (planning only).
      const pool = usablePool(next);
      let k = 0;
      next.rows = next.rows.map((r) => (editable(r) && !r.jobId && !next.selectedRoots.includes(r.root) && pool.length ? { ...r, root: pool[k++ % pool.length].root.name } : r));
      return next;
    }
    case "select":
      return { ...s, selected: a.row };
    case "check":
      return patch(a.row, (r) => ({ ...r, checked: a.on }));
    case "checkFirst": {
      let left = a.n;
      const picked = new Set<number>();
      for (const r of s.rows) {
        if (left <= 0) break;
        if (r.status !== "idle" || previewIssue(r, s) || (a.skipFlagged && r.flags.length)) continue;
        picked.add(r.row);
        left--;
      }
      return { ...s, rows: s.rows.map((r) => (r.status === "idle" ? { ...r, checked: picked.has(r.row) } : r)) };
    }
    case "uncheckAll":
      return { ...s, rows: s.rows.map((r) => ({ ...r, checked: false })) };
    case "rule":
      return { ...s, rule: a.rule };
    case "batchLimit":
      return { ...s, batchLimit: a.n };
    case "root":
      if (!usablePool(s).some((p) => p.root.name === a.root)) return s;
      return patch(a.row, (r) => (editable(r) && !r.jobId ? { ...r, root: a.root } : r));
    case "slug":
      return patch(a.row, (r) => (editable(r) && !r.jobId ? { ...r, slugOverride: a.value.toLowerCase() } : r));
    case "resetSlug":
      return patch(a.row, (r) => (editable(r) && !r.jobId ? { ...r, slugOverride: undefined } : r));
    case "strategy": {
      const pool = usablePool(s).filter((p) => !quotaFull(p.nick));
      if (!pool.length) return s;
      const targets = s.rows.filter((r) => r.checked && editable(r) && !r.jobId);
      const picks = a.strategy === "single"
        ? targets.map(() => (pool.some((p) => p.root.name === a.root) ? a.root! : pool[0].root.name))
        : targets.map((_, k) => pool[k % pool.length].root.name); // weighted = round robin while every nick has weight 1
      const byRow = new Map(targets.map((r, k) => [r.row, picks[k]]));
      return { ...s, rows: s.rows.map((r) => (byRow.has(r.row) ? { ...r, root: byRow.get(r.row)! } : r)) };
    }
    case "message":
      return { ...s, message: a.text };
    default:
      return s;
  }
}

function toNicks(server: ServerNick[]): Nick[] {
  return server.map((n) => ({
    id: n.id, name: n.name, email: "", ip: n.ip, hosting: n.hosting ?? undefined, cpanelHost: n.cpanel_host, cpanelUser: "",
    enabled: n.enabled, status: "untested", usedToday: 0, dailyLimit: null, weight: 1, subdomains: 0, lastCheck: "—",
    api: { dns: { state: "untested", note: "tạo bản ghi A qua API iNET: chưa khả dụng" }, cpanel: { state: "untested" } },
    roots: n.roots.map((r) => ({ name: r.name, dnsHost: r.dns_host, expires: r.expires ?? "2999-01-01", apexOnHosting: r.apex_on_hosting, suspended: r.suspended })),
  }));
}

export function useDomainQueue() {
  const [state, dispatchLocal] = useReducer(reducer, undefined, (): DomainState => ({
    rows: [], nicks: [], selectedRoots: [], selectionLoaded: false, lastSync: "—", rule: "legacy", batchLimit: 30,
    running: false, paused: false, selected: null, created: {}, existingB: [], scan: null, loadError: null, message: null,
  }));
  const stateRef = useRef(state);
  stateRef.current = state;

  const refresh = useCallback(async () => {
    try {
      const roots = await api.get<ServerNick[]>("/api/domains/roots");
      dispatchLocal({ type: "server", nicks: toNicks(roots), selected: roots.flatMap((n) => n.roots.filter((r) => r.selected).map((r) => r.name)) });
    } catch (e) {
      dispatchLocal({ type: "server", error: e instanceof ApiError ? e : new ApiError("error", errorText(e)) });
      return;
    }
    const jobs = await api.get<Job[]>("/api/jobs?kind=domain_create").catch(() => [] as Job[]);
    try {
      const scan = await api.get<Scan>("/api/domains/rows");
      dispatchLocal({ type: "server", scan, jobs, error: null });
    } catch (e) {
      dispatchLocal({ type: "server", scan: null, jobs, error: e instanceof ApiError ? e : new ApiError("error", errorText(e)) });
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, state.running ? 3000 : 15000);
    return () => clearInterval(id);
  }, [refresh, state.running]);

  const say = (text: string) => dispatchLocal({ type: "message", text });

  const dispatch: DomainDispatch = useCallback((a: Action) => {
    const s = stateRef.current;
    switch (a.type) {
      case "pickRoots": {
        // Show the tick at once; the backend decides (refused roots snap back on refresh).
        const set = new Set(s.selectedRoots);
        a.roots.forEach((n) => {
          const ref = findRoot(n, s.nicks);
          if (a.on && ref && !rootIssue(ref.root, ref.nick)) set.add(n);
          if (!a.on && !rootBusy(n, s.rows)) set.delete(n);
        });
        dispatchLocal({ type: "server", selected: s.nicks.flatMap((x) => x.roots.map((r) => r.name)).filter((n) => set.has(n)) });
      }
        api.post<{ changed: string[]; refused: Record<string, string> }>("/api/domains/roots/select", { names: a.roots, on: a.on })
          .then((r) => { const why = Object.entries(r.refused); if (why.length && a.roots.length === 1) say(`${why[0][0]}: ${why[0][1]}`); })
          .catch((e) => say(errorText(e)))
          .finally(refresh);
        return;
      case "start": {
        const items = s.rows.filter((r) => r.checked && r.status === "idle" && !r.jobId && !previewIssue(r, s)).slice(0, s.batchLimit)
          .map((r) => ({ row: r.row, company: r.company.A, root: r.root, label: labelOf(r, s.rule) }));
        api.post<{ queued: unknown[]; refused: Record<string, string> }>("/api/domains/run", { items })
          .then((r) => say(`Đã đưa ${r.queued.length} dòng vào hàng đợi backend${Object.keys(r.refused).length ? ` · từ chối ${Object.keys(r.refused).length}: ${Object.values(r.refused).join("; ")}` : ""}`))
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
      case "sync":
        refresh();
        return;
      case "pause":
      case "resume":
      case "resolveOrphan":
      case "toggleNick":
      case "saveNick":
      case "testNick":
        say("Chưa khả dụng trong bản này — thao tác này cần làm ở server");
        return;
      default:
        dispatchLocal(a);
    }
  }, [refresh]);

  return { state, dispatch };
}

export { DOMAIN_STEPS };
