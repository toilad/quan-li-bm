/**
 * Domain Manager — rules and DEMO DATA for the Phase 1 prototype.
 *
 * What this module does (from the legacy app's own description): for each Sheet
 * row with an empty column B it creates a SUBDOMAIN under a root domain the
 * owner already holds on one iNET account — an A record in iNET DNS plus the
 * domain on that account's cPanel hosting. It never registers a new domain.
 * Nothing here calls iNET or cPanel.
 */
import { COMPANIES, subdomainSlug, type Company } from "./mock-data";

/* ───────── iNET accounts ───────── */

export type Nick = {
  id: string;
  name: string;
  email: string; // shown masked
  root: string; // root domain already owned on this account
  ip: string; // hosting IP the A record points to
  cpanelHost: string;
  cpanelUser: string;
  enabled: boolean;
  status: "ok" | "slow" | "error" | "untested";
  usedToday: number;
  dailyLimit: number;
  subdomains: number;
  lastCheck: string;
  demoRoot?: boolean; // root is a placeholder, not from the legacy app
};

// Order matches the dashboard demo (row i uses nick i % 5). IPs are from the
// TEST-NET-3 documentation range so they can never point at a real server.
export const NICKS: Nick[] = [
  { id: "n1", name: "iNET-A", email: "nick-a@example.com", root: "th-ntp.com", ip: "203.0.113.21", cpanelHost: "cpanel.th-ntp.com", cpanelUser: "thntp", enabled: true, status: "ok", usedToday: 7, dailyLimit: 30, subdomains: 128, lastCheck: "2 phút trước" },
  { id: "n2", name: "iNET-B", email: "nick-b@example.com", root: "nick2-demo.com", ip: "203.0.113.37", cpanelHost: "cpanel.nick2-demo.com", cpanelUser: "nick2", enabled: true, status: "ok", usedToday: 4, dailyLimit: 30, subdomains: 61, lastCheck: "2 phút trước", demoRoot: true },
  { id: "n3", name: "iNET-C", email: "nick-c@example.com", root: "nick3-demo.com", ip: "203.0.113.52", cpanelHost: "cpanel.nick3-demo.com", cpanelUser: "nick3", enabled: true, status: "slow", usedToday: 12, dailyLimit: 30, subdomains: 77, lastCheck: "5 phút trước", demoRoot: true },
  { id: "n4", name: "iNET-D", email: "nick-d@example.com", root: "nick4-demo.com", ip: "203.0.113.68", cpanelHost: "cpanel.nick4-demo.com", cpanelUser: "nick4", enabled: true, status: "ok", usedToday: 2, dailyLimit: 30, subdomains: 40, lastCheck: "2 phút trước", demoRoot: true },
  { id: "n5", name: "iNET-E", email: "nick-e@example.com", root: "nick5-demo.com", ip: "203.0.113.84", cpanelHost: "cpanel.nick5-demo.com", cpanelUser: "nick5", enabled: true, status: "ok", usedToday: 29, dailyLimit: 30, subdomains: 93, lastCheck: "3 phút trước", demoRoot: true },
];

/** Records already present in each root's DNS zone (demo) — used for the duplicate check. */
export const EXISTING_RECORDS: Record<string, string[]> = {
  "th-ntp.com": ["www", "mail", "cpanel"],
  "nick5-demo.com": ["www", "rockspringsdigital", "codycreekvineyard"],
};

/* ───────── Subdomain naming (rule NOT confirmed yet) ───────── */

export type SlugRule = "legacy" | "columnE";

export const SLUG_RULES: Record<SlugRule, { label: string; detail: string }> = {
  legacy: {
    label: "Tên công ty bỏ hậu tố pháp lý",
    detail: "Theo hàm _slug_for_subdomain của app cũ: “N Triangle Ranch, Inc.” → ntriangleranch",
  },
  columnE: {
    label: "Dùng nguyên cột E",
    detail: "Giữ cả hậu tố như cột E: “13570 Tradition Street LLC” → 13570traditionstreetllc",
  },
};

export const slugFor = (c: Company, rule: SlugRule) => (rule === "legacy" ? subdomainSlug(c.A) : c.E.toLowerCase());

/** DNS label rules (RFC 1035): a-z 0-9 -, 1–63 chars, no leading/trailing hyphen. */
export function labelIssue(label: string): string | null {
  if (!label) return "Tên miền phụ trống";
  if (!/^[a-z0-9-]+$/.test(label)) return "Chỉ dùng a–z, 0–9 và dấu “-”";
  if (label.startsWith("-") || label.endsWith("-")) return "Không bắt đầu / kết thúc bằng “-”";
  if (label.length > 63) return `Dài ${label.length} ký tự — tối đa 63`;
  return null;
}

/* ───────── Pipeline ───────── */

export const DOMAIN_STEPS = [
  "Kiểm tra trùng (Sheet + DNS)",
  "Tạo bản ghi A · iNET DNS",
  "Tạo miền trên cPanel hosting",
  "Xác minh DNS trỏ đúng IP",
  "Đọc lại ô B → ghi B",
] as const;

export type RowStatus = "idle" | "queued" | "running" | "done" | "failed" | "conflict";
export type LogLine = { t: string; msg: string; tone: "ok" | "err" | "info" | "warn" };

export type DomainRow = {
  row: number;
  company: Company;
  nickId: string;
  slugOverride?: string;
  status: RowStatus;
  step: number;
  progress: number;
  dnsCreated: boolean;
  hostCreated: boolean;
  error?: string;
  writtenB?: string;
  log: LogLine[];
  checked: boolean;
  /** Demo only: scripted failure for this row. */
  outcome?: "cpanelTimeoutOnce" | "conflictAtWrite";
};

/** Rows with an empty B — split into eligible and excluded (with the reason). */
export function scanSheet() {
  const withB = COMPANIES.filter((c) => c.B.trim());
  const emptyB = COMPANIES.filter((c) => !c.B.trim());
  const reason = (c: Company): string | null => {
    if (c.stages.pdf === "error") return `PDF đang lỗi: ${c.note ?? "cần kiểm tra"}`;
    if (c.stages.pdf !== "done" || !c.K) return "PDF chưa lưu xong (chưa có link cột K)";
    if (!c.A.trim() || !c.E.trim()) return "Thiếu tên doanh nghiệp (A) hoặc tên rút gọn (E)";
    return null;
  };
  const eligible = emptyB.filter((c) => !reason(c));
  const excluded = emptyB.filter((c) => reason(c)).map((c) => ({ company: c, reason: reason(c)! }));
  return { total: COMPANIES.length, withB: withB.length, eligible, excluded };
}

export function initialRows(): DomainRow[] {
  return scanSheet().eligible.map((c, idx): DomainRow => {
    const i = c.row - 3;
    const base: DomainRow = {
      row: c.row, company: c, nickId: NICKS[i % NICKS.length].id, status: "idle", step: 0, progress: 0,
      dnsCreated: false, hostCreated: false, log: [], checked: false,
    };
    if (c.A.startsWith("Gillette")) base.outcome = "cpanelTimeoutOnce";
    if (c.A.startsWith("Douglas")) base.outcome = "conflictAtWrite";
    switch (c.stages.domain) {
      case "running":
        return {
          ...base, status: "running", step: idx === 0 ? 2 : 1, progress: 30, dnsCreated: idx === 0,
          log: [{ t: "14:31:02", msg: "Bắt đầu — nick đã chọn", tone: "info" }],
        };
      case "queued":
        return { ...base, status: "queued", checked: true };
      case "error":
        return {
          ...base, status: "failed", step: 1, progress: 100,
          error: "iNET từ chối: bản ghi đã tồn tại trên miền gốc và đang trỏ IP khác — không ghi đè. Đổi nick hoặc sửa tên rồi thử lại.",
          log: [
            { t: "14:25:10", msg: "Kiểm tra trùng trên Sheet: không trùng", tone: "ok" },
            { t: "14:25:14", msg: "iNET DNS: bản ghi đã tồn tại → dừng, B giữ trống", tone: "err" },
          ],
        };
      default:
        return base;
    }
  });
}

export const nickOf = (id: string, nicks: Nick[]) => nicks.find((n) => n.id === id)!;
