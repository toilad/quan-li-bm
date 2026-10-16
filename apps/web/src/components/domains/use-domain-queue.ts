"use client";

import { useEffect, useReducer } from "react";
import { COMPANIES } from "@/lib/mock-data";
import {
  DOMAIN_STEPS, EXISTING_RECORDS, NICKS, allRoots, findRoot, initialRows, labelIssue, quotaFull, rootIssue, rootPool,
  slugFor, type DomainRow, type LogLine, type Nick, type RootRef, type SlugRule,
} from "@/lib/domain-mock";

export type Strategy = "single" | "roundRobin" | "weighted";

export type DomainState = {
  rows: DomainRow[];
  nicks: Nick[];
  /** Root domains the owner ticked. Only these are ever used. Saved between visits. */
  selectedRoots: string[];
  /** The saved selection has been read (until then nothing is written back). */
  selectionLoaded: boolean;
  /** Last (simulated) sync of the domain lists over the iNET API. */
  lastSync: string;
  rule: SlugRule;
  /** Rows taken per run — separate from each nick's daily quota. */
  batchLimit: number;
  running: boolean;
  paused: boolean;
  selected: number | null;
  /** Records created during this session, per root (feeds the duplicate check). */
  created: Record<string, string[]>;
};

type Action =
  | { type: "tick" }
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
  | { type: "start" }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "retry"; row: number }
  | { type: "retryAll" }
  | { type: "resolveOrphan"; row: number; note: string }
  | { type: "toggleNick"; id: string }
  | { type: "saveNick"; nick: Nick }
  | { type: "testNick"; id: string }
  | { type: "pickRoots"; roots: string[]; on: boolean }
  | { type: "loadSelection"; roots: string[] }
  | { type: "sync" };

const MAX_PARALLEL = 2;
const STORAGE_KEY = "qlbm.domains.selectedRoots.v1";

const now = () => new Date().toLocaleTimeString("vi-VN", { hour12: false });
const line = (msg: string, tone: LogLine["tone"] = "info"): LogLine => ({ t: now(), msg, tone });

export const labelOf = (r: DomainRow, rule: SlugRule) => r.slugOverride ?? slugFor(r.company, rule);
export const fqdnOf = (r: DomainRow, s: Pick<DomainState, "rule">) => `${labelOf(r, s.rule)}.${r.root}`;
export const nickOfRow = (r: DomainRow, nicks: Nick[]): Nick | null => findRoot(r.root, nicks)?.nick ?? null;

/**
 * Gate before any DNS/cPanel work for a row that has not created anything yet:
 * the root must be assigned, ticked and usable. Unticked roots never take part.
 */
export function rootGate(r: DomainRow, s: Pick<DomainState, "nicks" | "selectedRoots">): string | null {
  if (r.dnsCreated) return null; // already created under this root — finish it, never move it
  if (!r.root) return "Chưa gán miền gốc — tích chọn miền ở bảng “Miền gốc dùng để tạo miền phụ”";
  const ref = findRoot(r.root, s.nicks);
  if (!ref) return `Không tìm thấy miền gốc ${r.root} trong danh sách đã đồng bộ`;
  if (!s.selectedRoots.includes(r.root)) return `Miền gốc ${r.root} chưa được tích chọn — chọn miền khác`;
  const issue = rootIssue(ref.root, ref.nick);
  return issue ? `Bị chặn — ${r.root}: ${issue}` : null;
}

/** Ticked roots that can be used right now, alternating between nicks. */
export const usablePool = (s: Pick<DomainState, "nicks" | "selectedRoots">): RootRef[] => rootPool(s.nicks, s.selectedRoots);

/**
 * A root is busy while one of its rows is queued/running or holds a DNS record
 * created under it but not yet written to B. A busy root can't be unticked, and
 * such a row can't move to another root.
 */
export const rootBusy = (root: string, rows: DomainRow[]) =>
  rows.some((r) => r.root === root && (r.status === "queued" || r.status === "running" || (r.status === "failed" && r.dnsCreated)));

/** Problems visible before running — the row cannot be queued while one exists. Never auto-renamed. */
export function previewIssue(r: DomainRow, s: DomainState): string | null {
  if (r.status === "done" || r.status === "conflict") return null;
  const label = labelOf(r, s.rule);
  const bad = labelIssue(label);
  if (bad) return s.rule === "columnE" && !r.company.E.trim() ? "Cột E trống — chọn cách tạo khác hoặc sửa tay" : bad;
  const gate = rootGate(r, s);
  if (gate) return gate;
  if (!r.dnsCreated && [...(EXISTING_RECORDS[r.root] ?? []), ...(s.created[r.root] ?? [])].includes(label))
    return `Đã có bản ghi “${label}” trên ${r.root} — đổi miền gốc hoặc sửa tên`;
  const fqdn = fqdnOf(r, s);
  if (COMPANIES.some((c) => c.B === fqdn)) return "Trùng tên miền đã có ở cột B của dòng khác";
  if (s.rows.some((o) => o.row !== r.row && o.status !== "done" && o.status !== "conflict" && fqdnOf(o, s) === fqdn))
    return "Trùng với dòng khác trong danh sách";
  return null;
}

const failRow = (r: DomainRow, error: string): DomainRow => ({ ...r, status: "failed", progress: 100, error, log: [...r.log, line(error, "err")] });

function advance(r: DomainRow, s: DomainState, nicks: Nick[], created: DomainState["created"]): DomainRow {
  const fail = (error: string) => failRow(r, error);
  // Re-checked at every step that could create something: a row never works on an unticked root.
  const gate = rootGate(r, { nicks, selectedRoots: s.selectedRoots });
  if (gate) return fail(`Dừng trước khi tạo: ${gate}. B giữ trống.`);
  const nick = nickOfRow(r, nicks)!;
  const label = labelOf(r, s.rule);
  const fqdn = `${label}.${r.root}`;

  switch (r.step) {
    case 0: {
      const issue = previewIssue(r, s);
      if (issue) return fail(`Kiểm tra trùng: ${issue}`);
      return { ...r, step: 1, progress: 0, log: [...r.log, line("Không trùng trên Sheet và vùng DNS", "ok")] };
    }
    case 1: {
      if (nick.api.dns.state === "blocked" && !r.dnsCreated)
        return fail(`Bị chặn: ${nick.name} — API DNS: ${nick.api.dns.note ?? "chưa có quyền"}. Không chuyển sang thao tác tay hay trình duyệt.`);
      if (r.dnsCreated) return { ...r, step: 2, progress: 0, log: [...r.log, line("Bản ghi A đã có từ lượt trước → bỏ qua, không tạo lại")] };
      if ((EXISTING_RECORDS[r.root] ?? []).includes(label))
        return fail(`iNET từ chối: “${label}” đã tồn tại trên ${r.root} — không ghi đè. B giữ trống.`);
      created[r.root] = [...(created[r.root] ?? []), label];
      return { ...r, step: 2, progress: 0, dnsCreated: true, log: [...r.log, line(`Tạo bản ghi A ${label}.${r.root} → ${nick.ip}`, "ok")] };
    }
    case 2: {
      if (nick.api.cpanel.state === "blocked" && !r.hostCreated)
        return fail(`Bị chặn: ${nick.name} — cPanel API: ${nick.api.cpanel.note ?? "chưa có quyền"}. B chưa ghi.`);
      if (r.hostCreated) return { ...r, step: 3, progress: 0, log: [...r.log, line("Miền đã có trên cPanel → bỏ qua")] };
      if (r.outcome === "cpanelTimeoutOnce")
        return { ...fail("cPanel hết thời gian chờ (30s). Bản ghi DNS đã tạo, miền chưa có trên hosting — B chưa ghi."), outcome: undefined };
      return { ...r, step: 3, progress: 0, hostCreated: true, log: [...r.log, line(`cPanel ${nick.cpanelHost}: tạo ${fqdn} · thư mục /public_html/${fqdn}`, "ok")] };
    }
    case 3:
      return { ...r, step: 4, progress: 0, log: [...r.log, line(`NS iNET trả về ${nick.ip} cho ${fqdn}`, "ok")] };
    default: {
      const i = nicks.findIndex((n) => n.id === nick.id);
      nicks[i] = { ...nick, usedToday: nick.usedToday + 1, subdomains: nick.subdomains + 1 };
      if (r.outcome === "conflictAtWrite") {
        const foundB = `${label.slice(0, 10)}.${r.root}`;
        return {
          ...r, status: "conflict", progress: 100, outcome: undefined,
          orphan: { fqdn, nick: nick.name, ip: nick.ip, dns: r.dnsCreated, host: true, foundB, at: now() },
          error: `Ô B dòng #${r.row} đã có “${foundB}” khi ghi (người khác nhập) — không ghi đè. Miền ${fqdn} đã tạo xong, lưu vào “Tài nguyên chưa gắn”.`,
          log: [...r.log, line(`Đọc lại ô B: đã có “${foundB}” → xung đột, không ghi. Lưu tài nguyên đã tạo để xử lý`, "warn")],
        };
      }
      return {
        ...r, status: "done", progress: 100, writtenB: fqdn, error: undefined,
        log: [...r.log, line(`Ô B vẫn trống → ghi B = ${fqdn} · cột C giữ nguyên`, "ok")],
      };
    }
  }
}

function tick(s: DomainState): DomainState {
  const nicks = [...s.nicks];
  const created = { ...s.created };
  let rows = s.rows.map((r) => {
    if (r.status !== "running") return r;
    if (r.progress < 100) return { ...r, progress: Math.min(100, r.progress + 34) };
    if (s.paused) return r; // finish the current step, then hold
    return advance(r, s, nicks, created);
  });

  // One row at a time per nick (shared API key and hosting), at most MAX_PARALLEL nicks at once.
  if (s.running && !s.paused) {
    const busyNicks = new Set(rows.filter((r) => r.status === "running").map((r) => nickOfRow(r, nicks)?.id));
    let slots = MAX_PARALLEL - busyNicks.size;
    rows = rows.map((r) => {
      if (r.status !== "queued") return r;
      const gate = rootGate(r, { nicks, selectedRoots: s.selectedRoots });
      if (gate) return failRow(r, `Không chạy: ${gate}. B giữ trống.`);
      if (slots <= 0) return r;
      const nick = nickOfRow(r, nicks)!;
      if (busyNicks.has(nick.id) || !nick.enabled || quotaFull(nick)) return r;
      busyNicks.add(nick.id);
      slots--;
      return { ...r, status: "running", progress: 0, log: [...r.log, line(`Bắt đầu trên ${nick.name} · miền gốc ${r.root}`)] };
    });
  }

  const busy = rows.some((r) => r.status === "running" || r.status === "queued");
  return { ...s, rows, nicks, created, running: s.running && busy };
}

/** Resume at the failed step: finished steps (DNS, cPanel) are kept and skipped. */
const retryRow = (r: DomainRow): DomainRow =>
  r.status === "failed"
    ? { ...r, status: "queued", progress: 0, error: undefined, log: [...r.log, line(`Thử lại từ bước “${DOMAIN_STEPS[r.step]}” — các bước đã xong được giữ`)] }
    : r;

/** Split `count` rows over nicks by weight (deterministic), then rotate through each nick's ticked roots. */
function weightedPicks(pool: RootRef[], count: number): string[] {
  const byNick = new Map<string, RootRef[]>();
  for (const ref of pool) byNick.set(ref.nick.id, [...(byNick.get(ref.nick.id) ?? []), ref]);
  const lanes = [...byNick.values()];
  const total = lanes.reduce((s, l) => s + Math.max(0, l[0].nick.weight), 0) || lanes.length;
  const given = lanes.map(() => 0);
  const out: string[] = [];
  for (let k = 0; k < count; k++) {
    let best = 0;
    for (let i = 1; i < lanes.length; i++)
      if (given[i] / (lanes[i][0].nick.weight / total || 1e-9) < given[best] / (lanes[best][0].nick.weight / total || 1e-9)) best = i;
    out.push(lanes[best][given[best] % lanes[best].length].root.name);
    given[best]++;
  }
  return out;
}

/** Rows that still may change root: not started, or failed before any DNS record was created. */
const editable = (r: DomainRow) => !r.dnsCreated && (r.status === "idle" || r.status === "failed");

/** Move editable rows sitting on a root that is no longer ticked onto the ticked ones, in turn. */
function reassignOrphanedRows(s: DomainState): DomainRow[] {
  const pool = usablePool(s);
  if (!pool.length) return s.rows;
  let k = 0;
  return s.rows.map((r) => (editable(r) && !s.selectedRoots.includes(r.root) ? { ...r, root: pool[k++ % pool.length].root.name } : r));
}

function reducer(s: DomainState, a: Action): DomainState {
  const patch = (row: number, fn: (r: DomainRow) => DomainRow) => ({ ...s, rows: s.rows.map((r) => (r.row === row ? fn(r) : r)) });

  switch (a.type) {
    case "tick":
      return tick(s);
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
      // Only a ticked, usable root may be picked for a row.
      if (!usablePool(s).some((p) => p.root.name === a.root)) return s;
      return patch(a.row, (r) => (editable(r) ? { ...r, root: a.root } : r));
    case "slug":
      return patch(a.row, (r) => (editable(r) ? { ...r, slugOverride: a.value.toLowerCase() } : r));
    case "resetSlug":
      return patch(a.row, (r) => (editable(r) ? { ...r, slugOverride: undefined } : r));
    case "strategy": {
      const pool = usablePool(s).filter((p) => !quotaFull(p.nick));
      if (!pool.length) return s;
      const targets = s.rows.filter((r) => r.checked && editable(r));
      const picks =
        a.strategy === "single" ? targets.map(() => (pool.some((p) => p.root.name === a.root) ? a.root! : pool[0].root.name))
          : a.strategy === "weighted" ? weightedPicks(pool, targets.length)
            : targets.map((_, k) => pool[k % pool.length].root.name);
      const byRow = new Map(targets.map((r, k) => [r.row, picks[k]]));
      return { ...s, rows: s.rows.map((r) => (byRow.has(r.row) ? { ...r, root: byRow.get(r.row)! } : r)) };
    }
    case "start": {
      if (!usablePool(s).length) return s; // nothing ticked → never start
      let left = s.batchLimit;
      return {
        ...s, running: true, paused: false,
        rows: s.rows.map((r) => {
          if (!r.checked || r.status !== "idle" || previewIssue(r, s) || left <= 0) return r;
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
    case "resolveOrphan":
      return patch(a.row, (r) => (r.orphan ? { ...r, orphan: { ...r.orphan, resolved: a.note }, log: [...r.log, line(`Đánh dấu đã xử lý: ${a.note}`)] } : r));
    case "toggleNick":
      return { ...s, nicks: s.nicks.map((n) => (n.id === a.id ? { ...n, enabled: !n.enabled } : n)) };
    case "saveNick": {
      const exists = s.nicks.some((n) => n.id === a.nick.id);
      return { ...s, nicks: exists ? s.nicks.map((n) => (n.id === a.nick.id ? a.nick : n)) : [...s.nicks, a.nick] };
    }
    case "testNick":
      return { ...s, nicks: s.nicks.map((n) => (n.id === a.id ? { ...n, status: n.status === "error" ? "error" : "ok", lastCheck: "vừa xong" } : n)) };
    case "pickRoots": {
      const refs = allRoots(s.nicks).filter((x) => a.roots.includes(x.root.name));
      // Ticking: only usable roots. Unticking: never a root with work in progress on it.
      const change = refs
        .filter((x) => (a.on ? !rootIssue(x.root, x.nick) : !rootBusy(x.root.name, s.rows)))
        .map((x) => x.root.name);
      const sel = new Set(s.selectedRoots);
      change.forEach((n) => (a.on ? sel.add(n) : sel.delete(n)));
      // Keep nick/list order so the pool is stable; rows left on an unticked root move to the ticked ones.
      const next = { ...s, selectedRoots: allRoots(s.nicks).map((x) => x.root.name).filter((n) => sel.has(n)) };
      return { ...next, rows: reassignOrphanedRows(next) };
    }
    case "loadSelection": {
      // Restore exactly the saved choice. A queued row on a root that isn't ticked fails its first check — never run on an unticked root.
      const sel = new Set(a.roots);
      const next = { ...s, selectionLoaded: true, selectedRoots: allRoots(s.nicks).map((x) => x.root.name).filter((n) => sel.has(n)) };
      return { ...next, rows: reassignOrphanedRows(next) };
    }
    case "sync":
      return { ...s, lastSync: `hôm nay ${now()}` };
  }
}

function readSaved(): string[] | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const v = raw ? JSON.parse(raw) : null;
    return Array.isArray(v) && v.every((x) => typeof x === "string") ? v : null;
  } catch {
    return null;
  }
}

export function useDomainQueue() {
  const [state, dispatch] = useReducer(reducer, undefined, (): DomainState => {
    return {
      nicks: NICKS,
      // Nothing ticked until the owner ticks it (or the saved choice loads) — never a default.
      selectedRoots: [],
      rows: initialRows(),
      selectionLoaded: false,
      lastSync: "16/10/2026 (bản sao đọc từ portal)",
      rule: "legacy",
      batchLimit: 30,
      // Nothing runs on open/reload — only after "Xác nhận chạy".
      running: false,
      paused: false,
      selected: null,
      created: {},
    };
  });

  // Saved choice of root domains — browser storage in this prototype, the database in the real app.
  useEffect(() => {
    const saved = readSaved();
    dispatch({ type: "loadSelection", roots: saved ?? [] });
  }, []);
  useEffect(() => {
    if (!state.selectionLoaded) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.selectedRoots));
    } catch {
      /* storage unavailable — the choice just isn't remembered */
    }
  }, [state.selectedRoots, state.selectionLoaded]);

  const active = state.running || state.rows.some((r) => r.status === "running");
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => dispatch({ type: "tick" }), 700);
    return () => clearInterval(id);
  }, [active]);

  return { state, dispatch };
}

export type DomainDispatch = ReturnType<typeof useDomainQueue>["dispatch"];
