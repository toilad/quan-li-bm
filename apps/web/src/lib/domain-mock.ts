/**
 * Domain Manager — rules and DEMO DATA for the Phase 1 prototype.
 *
 * What this module does (from the legacy app's own description): for each Sheet
 * row with an empty column B it creates a SUBDOMAIN under a root domain the
 * owner already holds on one iNET account — an A record in iNET DNS plus the
 * domain on that account's cPanel hosting. It never registers a new domain.
 * Nothing here calls iNET or cPanel.
 */
import { COMPANIES, foldAccents, subdomainSlug, type Company } from "./mock-data";

/* ───────── iNET accounts ───────── */

/** A domain the account owns. The real list comes from the iNET API; here it is a static copy. */
export type RootDomain = {
  name: string;
  dnsHost: DnsHost;
  expires: string; // ISO date of the domain registration
  /** The root itself already points at this account's hosting IP. */
  apexOnHosting: boolean;
  suspended?: boolean;
  /** From the last read-only cPanel check: true/false, undefined = not checked yet. */
  onCpanel?: boolean | null;
};

export type Nick = {
  id: string;
  name: string;
  email: string; // shown masked
  /** Every domain on the account — the owner ticks which ones subdomains may be created under. */
  roots: RootDomain[];
  ip: string; // hosting IP the A record points to
  /** Primary domain of the cPanel hosting plan. */
  hosting?: string;
  cpanelHost: string;
  /** Never in source control — entered on the server. */
  cpanelUser: string;
  enabled: boolean;
  status: "ok" | "slow" | "error" | "untested";
  usedToday: number;
  /** Max new subdomains per day. null = not configured (no evidence yet) → not enforced, shown as a warning. */
  dailyLimit: number | null;
  /** Share used by the "theo tỷ trọng" allocation. */
  weight: number;
  subdomains: number;
  lastCheck: string;
  /** API access per capability. Everything runs over API — never browser automation. */
  api: { dns: ApiCap; cpanel: ApiCap };
};

export type DnsHost = "inet" | "cpanel" | "other" | "unknown";

export const DNS_HOST_LABEL: Record<DnsHost, string> = {
  inet: "Nameserver iNET → API DNS iNET",
  cpanel: "Nameserver của host cPanel → DNS API cPanel",
  other: "Nameserver nhà khác (Cloudflare) → API iNET / cPanel không ghi được",
  unknown: "Chưa xác định nameserver",
};

export type ApiCap = { state: "ok" | "blocked" | "untested"; note?: string };

export const API_LABEL = { dns: "API DNS", cpanel: "cPanel API (token)" } as const;

/** First nick-level capability that blocks it, if any — shown as "Bị chặn", never worked around. */
export function apiBlock(n: Nick): string | null {
  for (const k of ["dns", "cpanel"] as const) {
    const c = n.api[k];
    if (c.state === "blocked") return `${API_LABEL[k]}: ${c.note ?? "chưa có quyền"}`;
  }
  return null;
}

/** Days until a root domain's registration expires (negative = expired). */
export function daysLeft(iso: string, today = new Date()): number {
  const ms = new Date(`${iso}T00:00:00`).getTime() - new Date(today.toDateString()).getTime();
  return Math.round(ms / 86_400_000);
}

/** Roots expiring within this many days are flagged — a subdomain dies with its root. */
export const EXPIRY_WARN_DAYS = 60;

/** Why subdomains can't be created under this root right now; null = usable. Blocked roots can't be ticked or run. */
export function rootIssue(r: RootDomain, nick: Nick, today = new Date()): string | null {
  if (r.suspended) return "Miền đang tạm ngưng";
  if (daysLeft(r.expires, today) < 0) return "Miền đã hết hạn";
  if (r.dnsHost === "other") return "DNS ở nhà cung cấp khác (Cloudflare) — API iNET không ghi được";
  if (r.dnsHost === "unknown") return "Chưa xác định nameserver — không biết dùng API DNS nào";
  if (!nick.enabled) return `Nick ${nick.name} đang tắt`;
  const blocked = apiBlock(nick);
  if (blocked) return `${nick.name}: ${blocked}`;
  return null;
}

export type RootRef = { root: RootDomain; nick: Nick };

/** Every root of every nick, in nick order. Root names are unique across accounts. */
export const allRoots = (nicks: Nick[]): RootRef[] => nicks.flatMap((nick) => nick.roots.map((root) => ({ root, nick })));

/** The root and its owning nick; null when the name is empty (row not assigned yet) or unknown. */
export function findRoot(name: string, nicks: Nick[]): RootRef | null {
  for (const nick of nicks) {
    const root = nick.roots.find((r) => r.name === name);
    if (root) return { root, nick };
  }
  return null;
}

/**
 * Ticked, usable roots ordered so consecutive picks alternate between nicks
 * (n1·a, n2·a, n3·a, n1·b, …) — spreads load over accounts and hosting servers.
 */
export function rootPool(nicks: Nick[], selected: string[], today = new Date()): RootRef[] {
  const sel = new Set(selected);
  const lanes = nicks.map((nick) => nick.roots.filter((r) => sel.has(r.name) && !rootIssue(r, nick, today)).map((root) => ({ root, nick })));
  const out: RootRef[] = [];
  for (let i = 0; lanes.some((l) => i < l.length); i++) for (const l of lanes) if (i < l.length) out.push(l[i]);
  return out;
}

const inet = (name: string, expires: string, apexOnHosting = false): RootDomain => ({ name, dnsHost: "inet", expires, apexOnHosting });

/*
 * The owner's 3 real iNET accounts, copied from portal.inet.vn on 2026-10-16
 * (domains, hosting, expiry) plus public DNS (nameservers, apex A). Read-only:
 * nothing was changed on the accounts. In the real app this list is synced over
 * the iNET API. No API key has been entered yet, so API access is "untested".
 * cPanel usernames stay out of source control.
 */
export const NICKS: Nick[] = [
  {
    id: "n1", name: "iNET-1", email: "", ip: "103.75.187.26", hosting: "levantoan.000web.com",
    cpanelHost: "turboweb-022607.000nethost.com", cpanelUser: "",
    roots: [
      inet("sustainlife.io.vn", "2027-04-03", true), inet("ganeshabrands.food", "2027-07-06"), inet("huxma.life", "2027-07-06"),
      inet("yhawtunga.diy", "2027-07-06"), inet("yhawt.press", "2027-07-06"), inet("ganeshabrands.space", "2027-06-30"),
      inet("bmglobal.io.vn", "2027-06-29"), inet("woryn.com.vn", "2027-06-25"), inet("vnclick.cloud", "2027-05-27"),
      inet("vnclick.food", "2027-05-27"),
      { name: "vietcart.site", dnsHost: "unknown", expires: "2027-05-27", apexOnHosting: false, suspended: true },
    ],
    enabled: true, status: "untested", usedToday: 0, dailyLimit: null, weight: 1, subdomains: 0, lastCheck: "chưa kiểm tra",
    api: { dns: { state: "untested", note: "chưa nhập khoá API" }, cpanel: { state: "untested", note: "chưa nhập token" } },
  },
  {
    id: "n2", name: "iNET-2", email: "", ip: "103.75.187.26", hosting: "ntp88.com",
    cpanelHost: "turboweb-022607.000nethost.com", cpanelUser: "",
    roots: [inet("ntp88.com", "2027-04-20", true), inet("thanhnam88.com", "2027-07-21", true), inet("convnctnet.com", "2027-07-01")],
    enabled: true, status: "untested", usedToday: 0, dailyLimit: null, weight: 1, subdomains: 0, lastCheck: "chưa kiểm tra",
    api: { dns: { state: "untested", note: "chưa nhập khoá API" }, cpanel: { state: "untested", note: "chưa nhập token" } },
  },
  {
    id: "n3", name: "iNET-3", email: "", ip: "202.92.7.88", hosting: "toandao.site",
    cpanelHost: "turboweb-082302.000nethost.com", cpanelUser: "",
    roots: [
      inet("groupany.id.vn", "2027-03-18", true), inet("zentrivo.my", "2027-03-12", true), inet("a66group.store", "2027-03-02", true),
      inet("a77group.website", "2026-12-25", true), inet("a45group.io.vn", "2026-12-09", true), inet("a69group.io.vn", "2026-12-02", true),
      inet("a66group.io.vn", "2026-11-15", true), inet("namecheapp.site", "2026-11-11", true), inet("toandao.site", "2026-11-08", true),
      inet("starstad.space", "2027-07-03"),
      { name: "167nailspa.com", dnsHost: "other", expires: "2027-08-13", apexOnHosting: false },
    ],
    enabled: true, status: "untested", usedToday: 0, dailyLimit: null, weight: 1, subdomains: 0, lastCheck: "chưa kiểm tra",
    api: { dns: { state: "untested", note: "chưa nhập khoá API" }, cpanel: { state: "untested", note: "chưa nhập token" } },
  },
];


export const quotaFull = (n: Nick) => n.dailyLimit !== null && n.usedToday >= n.dailyLimit;

/**
 * Records already present in each root's DNS zone — used for the duplicate check.
 * The real zones are read over the iNET DNS API once a key is entered; until
 * then only records created in this session are known.
 */
export const EXISTING_RECORDS: Record<string, string[]> = {};

/* ───────── Subdomain naming (rule NOT confirmed yet) ───────── */

export type SlugRule = "columnE" | "legacy" | "short";

const LEGAL = new Set(["llc", "inc", "pllc", "co", "corp", "ltd", "company", "the", "and", "of"]);

/** First two meaningful words of the company name: "Global Freight Partners LLC" → globalfreight. */
export function shortSlug(name: string): string {
  const words = foldAccents(name.toLowerCase()).replace(/[^a-z0-9\s]/g, " ").split(/\s+/)
    .filter((w) => w && !LEGAL.has(w) && !["ltda", "eireli", "epp"].includes(w));
  return words.slice(0, 2).join("");
}

export const SLUG_RULES: Record<SlugRule, { label: string; detail: string }> = {
  columnE: { label: "Dùng cột E", detail: "Lấy nguyên giá trị cột E: 13570traditionstreetllc" },
  legacy: { label: "Bỏ hậu tố pháp lý", detail: "Như app cũ (_slug_for_subdomain): N Triangle Ranch, Inc. → ntriangleranch" },
  short: { label: "Rút gọn theo tên công ty", detail: "2 từ đầu, bỏ hậu tố: Global Freight Partners LLC → globalfreight" },
};

/** Column E is only READ here — it is never rewritten. */
export function slugFor(c: Company, rule: SlugRule): string {
  if (rule === "columnE") return c.E.trim().toLowerCase();
  if (rule === "short") return shortSlug(c.A);
  return subdomainSlug(c.A);
}

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
  "Tạo bản ghi A qua API DNS",
  "Tạo miền trên cPanel hosting",
  "Xác minh DNS trỏ đúng IP",
  "Đọc lại ô B → ghi B",
] as const;

export type RowStatus = "idle" | "queued" | "running" | "done" | "failed" | "conflict";
export type LogLine = { t: string; msg: string; tone: "ok" | "err" | "info" | "warn" };

/** Resources created for a row that could not be written to B — kept for follow-up. */
export type Orphan = { fqdn: string; nick: string; ip: string; dns: boolean; host: boolean; foundB: string; at: string; resolved?: string };

export type DomainRow = {
  row: number;
  company: Company;
  flags: string[]; // "cần kiểm tra" — shown, never auto-excluded
  /** Root domain the subdomain goes under ("" = not assigned yet); the nick is the one that owns it. */
  root: string;
  slugOverride?: string;
  status: RowStatus;
  step: number;
  progress: number;
  dnsCreated: boolean;
  hostCreated: boolean;
  error?: string;
  writtenB?: string;
  orphan?: Orphan;
  log: LogLine[];
  checked: boolean;
  /** Demo only: scripted failure for this row. */
  outcome?: "cpanelTimeoutOnce" | "conflictAtWrite";
  /** Backend job that owns this row (set once the row was sent to the server). */
  jobId?: number;
};

/**
 * Rows with an empty B. A row is usable when it has a company name; anything
 * else missing (K, PDF still processing or in error, E) is a flag to check,
 * not a reason to drop it. Clean rows come first.
 */
export function scanSheet() {
  const withB = COMPANIES.filter((c) => c.B.trim());
  const emptyB = COMPANIES.filter((c) => !c.B.trim());
  const flagsOf = (c: Company) => {
    const f: string[] = [];
    if (!c.K.trim()) f.push(c.stages.pdf === "running" ? "Chưa có link K (PDF đang xử lý)" : "Chưa có link K");
    if (c.stages.pdf === "error") f.push(`PDF đang lỗi: ${c.note ?? "cần kiểm tra"}`);
    if (!c.E.trim()) f.push("Thiếu cột E");
    return f;
  };
  const usable = emptyB.filter((c) => c.A.trim());
  const excluded = emptyB.filter((c) => !c.A.trim()).map((c) => ({ company: c, reason: "Thiếu tên doanh nghiệp (A)" }));
  const rows = usable.map((c) => ({ company: c, flags: flagsOf(c) })).sort((a, b) => a.flags.length - b.flags.length || a.company.row - b.company.row);
  return { total: COMPANIES.length, withB: withB.length, rows, excluded };
}

/**
 * Rows from the Sheet scan. Nothing is assigned or started on load: rows get a
 * root only from the owner's ticked domains, and run only after the preview.
 */
export function initialRows(): DomainRow[] {
  return scanSheet().rows.map(({ company: c, flags }): DomainRow => {
    const base: DomainRow = {
      row: c.row, company: c, flags, root: "", status: "idle", step: 0, progress: 0,
      dnsCreated: false, hostCreated: false, log: [], checked: false,
    };
    if (c.A.startsWith("Gillette")) base.outcome = "cpanelTimeoutOnce";
    if (c.A.startsWith("Douglas")) base.outcome = "conflictAtWrite";
    switch (c.stages.domain) {
      case "error":
        return {
          ...base, status: "failed", step: 1, progress: 100,
          error: "iNET từ chối: bản ghi đã tồn tại trên miền gốc và đang trỏ IP khác — không ghi đè. Đổi miền gốc hoặc sửa tên rồi thử lại.",
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

