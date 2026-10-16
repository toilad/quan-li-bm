"use client";

import { useEffect, useReducer } from "react";
import { COMPANIES } from "@/lib/mock-data";
import {
  DOMAIN_STEPS, EXISTING_RECORDS, NICKS, initialRows, labelIssue, nickOf, slugFor,
  type DomainRow, type LogLine, type Nick, type SlugRule,
} from "@/lib/domain-mock";

export type Strategy = "keep" | "roundRobin" | "random" | "single";

export type DomainState = {
  rows: DomainRow[];
  nicks: Nick[];
  rule: SlugRule;
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
  | { type: "checkFirst"; n: number }
  | { type: "uncheckAll" }
  | { type: "rule"; rule: SlugRule }
  | { type: "nick"; row: number; nickId: string }
  | { type: "slug"; row: number; value: string }
  | { type: "strategy"; strategy: Strategy; nickId?: string }
  | { type: "start" }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "retry"; row: number }
  | { type: "retryAll" }
  | { type: "toggleNick"; id: string }
  | { type: "saveNick"; nick: Nick }
  | { type: "testNick"; id: string };

const MAX_PARALLEL = 2;

const now = () => new Date().toLocaleTimeString("vi-VN", { hour12: false });
const line = (msg: string, tone: LogLine["tone"] = "info"): LogLine => ({ t: now(), msg, tone });

export const labelOf = (r: DomainRow, rule: SlugRule) => r.slugOverride ?? slugFor(r.company, rule);
export const fqdnOf = (r: DomainRow, s: DomainState) => `${labelOf(r, s.rule)}.${nickOf(r.nickId, s.nicks).root}`;

/** Problems visible before running — the row cannot be queued while one exists. */
export function previewIssue(r: DomainRow, s: DomainState): string | null {
  if (r.status === "done" || r.status === "conflict") return null;
  const label = labelOf(r, s.rule);
  const bad = labelIssue(label);
  if (bad) return bad;
  const nick = nickOf(r.nickId, s.nicks);
  if (!nick.enabled) return `Nick ${nick.name} đang tắt`;
  if (!r.dnsCreated && [...(EXISTING_RECORDS[nick.root] ?? []), ...(s.created[nick.root] ?? [])].includes(label))
    return `Đã có bản ghi “${label}” trên ${nick.root} — đổi nick hoặc sửa tên`;
  const fqdn = fqdnOf(r, s);
  if (COMPANIES.some((c) => c.B === fqdn)) return `Trùng tên miền đã có ở cột B của dòng khác`;
  if (s.rows.some((o) => o.row !== r.row && o.status !== "done" && fqdnOf(o, s) === fqdn)) return "Trùng với dòng khác trong danh sách";
  return null;
}

function advance(r: DomainRow, s: DomainState, nicks: Nick[], created: DomainState["created"]): DomainRow {
  const nick = nickOf(r.nickId, nicks);
  const label = labelOf(r, s.rule);
  const fqdn = `${label}.${nick.root}`;
  const fail = (error: string): DomainRow => ({ ...r, status: "failed", progress: 100, error, log: [...r.log, line(error, "err")] });

  switch (r.step) {
    case 0: {
      const issue = previewIssue(r, s);
      if (issue) return fail(`Kiểm tra trùng: ${issue}`);
      return { ...r, step: 1, progress: 0, log: [...r.log, line("Không trùng trên Sheet và vùng DNS", "ok")] };
    }
    case 1: {
      if (r.dnsCreated) return { ...r, step: 2, progress: 0, log: [...r.log, line("Bản ghi A đã có từ lượt trước → bỏ qua, không tạo lại")] };
      if ((EXISTING_RECORDS[nick.root] ?? []).includes(label))
        return fail(`iNET từ chối: “${label}” đã tồn tại trên ${nick.root} — không ghi đè. B giữ trống.`);
      created[nick.root] = [...(created[nick.root] ?? []), label];
      return { ...r, step: 2, progress: 0, dnsCreated: true, log: [...r.log, line(`Tạo bản ghi A ${label} → ${nick.ip}`, "ok")] };
    }
    case 2: {
      if (r.outcome === "cpanelTimeoutOnce")
        return { ...fail("cPanel hết thời gian chờ (30s). Bản ghi DNS đã tạo, miền chưa có trên hosting — B chưa ghi."), outcome: undefined };
      return { ...r, step: 3, progress: 0, hostCreated: true, log: [...r.log, line(`cPanel ${nick.cpanelHost}: tạo ${fqdn} · thư mục /public_html/${fqdn}`, "ok")] };
    }
    case 3:
      return { ...r, step: 4, progress: 0, log: [...r.log, line(`NS iNET trả về ${nick.ip} cho ${fqdn}`, "ok")] };
    default: {
      if (r.outcome === "conflictAtWrite")
        return {
          ...r, status: "conflict", progress: 100, outcome: undefined,
          error: `Ô B dòng #${r.row} đã có giá trị khi ghi (người khác nhập) — bỏ qua, không ghi đè. Miền ${fqdn} đã tạo, cần anh kiểm tra.`,
          log: [...r.log, line("Đọc lại ô B: đã có dữ liệu → xung đột, không ghi", "warn")],
        };
      const i = nicks.findIndex((n) => n.id === nick.id);
      nicks[i] = { ...nick, usedToday: nick.usedToday + 1, subdomains: nick.subdomains + 1 };
      return {
        ...r, status: "done", progress: 100, writtenB: fqdn, error: undefined,
        log: [...r.log, line(`Ghi B = ${fqdn} · cột C giữ nguyên`, "ok")],
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

  if (s.running && !s.paused) {
    const busyNicks = new Set(rows.filter((r) => r.status === "running").map((r) => r.nickId));
    let slots = MAX_PARALLEL - busyNicks.size;
    rows = rows.map((r) => {
      if (slots <= 0 || r.status !== "queued" || busyNicks.has(r.nickId)) return r;
      const nick = nickOf(r.nickId, nicks);
      if (!nick.enabled || nick.usedToday >= nick.dailyLimit) return r;
      busyNicks.add(r.nickId);
      slots--;
      return { ...r, status: "running", progress: 0, log: [...r.log, line(`Bắt đầu trên ${nick.name} (${nick.root})`)] };
    });
  }

  const busy = rows.some((r) => r.status === "running" || r.status === "queued");
  return { ...s, rows, nicks, created, running: s.running && busy };
}

const retryRow = (r: DomainRow): DomainRow =>
  r.status === "failed"
    ? { ...r, status: "queued", progress: 0, error: undefined, log: [...r.log, line(`Thử lại từ bước “${DOMAIN_STEPS[r.step]}” — các bước đã xong được giữ`)] }
    : r;

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
      return {
        ...s,
        rows: s.rows.map((r) => {
          const ok = r.status === "idle" && !previewIssue(r, s) && left > 0;
          if (ok) left--;
          return r.status === "idle" ? { ...r, checked: ok } : r;
        }),
      };
    }
    case "uncheckAll":
      return { ...s, rows: s.rows.map((r) => ({ ...r, checked: false })) };
    case "rule":
      return { ...s, rule: a.rule };
    case "nick":
      return patch(a.row, (r) => (r.dnsCreated ? r : { ...r, nickId: a.nickId }));
    case "slug":
      return patch(a.row, (r) => (r.dnsCreated ? r : { ...r, slugOverride: a.value.toLowerCase() }));
    case "strategy": {
      const pool = s.nicks.filter((n) => n.enabled && n.usedToday < n.dailyLimit);
      if (!pool.length || a.strategy === "keep") return s;
      let k = 0;
      return {
        ...s,
        rows: s.rows.map((r) => {
          if (r.status !== "idle" || r.dnsCreated || !r.checked) return r;
          const nickId =
            a.strategy === "single" ? (a.nickId ?? pool[0].id)
              : a.strategy === "random" ? pool[(r.row * 7 + 3) % pool.length].id
                : pool[k++ % pool.length].id;
          return { ...r, nickId };
        }),
      };
    }
    case "start":
      return {
        ...s, running: true, paused: false,
        rows: s.rows.map((r) => (r.checked && r.status === "idle" && !previewIssue(r, s) ? { ...r, status: "queued", checked: false } : r)),
      };
    case "pause":
      return { ...s, paused: true };
    case "resume":
      return { ...s, paused: false, running: true };
    case "retry":
      return { ...patch(a.row, retryRow), running: true, paused: false };
    case "retryAll":
      return { ...s, running: true, paused: false, rows: s.rows.map(retryRow) };
    case "toggleNick":
      return { ...s, nicks: s.nicks.map((n) => (n.id === a.id ? { ...n, enabled: !n.enabled } : n)) };
    case "saveNick": {
      const exists = s.nicks.some((n) => n.id === a.nick.id);
      return { ...s, nicks: exists ? s.nicks.map((n) => (n.id === a.nick.id ? a.nick : n)) : [...s.nicks, a.nick] };
    }
    case "testNick":
      return { ...s, nicks: s.nicks.map((n) => (n.id === a.id ? { ...n, status: n.status === "error" ? "error" : "ok", lastCheck: "vừa xong" } : n)) };
  }
}

export function useDomainQueue() {
  const [state, dispatch] = useReducer(reducer, undefined, () => ({
    rows: initialRows(),
    nicks: NICKS,
    rule: "legacy" as SlugRule,
    running: true,
    paused: false,
    selected: null,
    created: {},
  }));

  const active = state.running || state.rows.some((r) => r.status === "running");
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => dispatch({ type: "tick" }), 700);
    return () => clearInterval(id);
  }, [active]);

  return { state, dispatch };
}

export type DomainDispatch = ReturnType<typeof useDomainQueue>["dispatch"];
