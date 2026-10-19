/**
 * PDF Manager — document types, validation rules and DEMO DATA for the
 * Phase 1 prototype. Nothing here reads a real PDF or touches Google.
 *
 * All identifiers (CNPJ, entity numbers, ZIP/CEP) are kept as TEXT end to end
 * so leading zeros survive; the Sheet write will use RAW input with a text format.
 */
import { detectTemplate, type SiteTemplate } from "./templates";

export type FieldKey = "A" | "D" | "E" | "F" | "G" | "H" | "I" | "J";
export type FieldSource = "text" | "ai" | "ocr" | "auto" | "manual" | "missing";
/** `note` explains a normalisation, e.g. "California" → "CA" or how a BR address was assembled. */
export type Region = { page: number; rotation?: number; box: [number, number, number, number] };
export type Suspect = { message: string; suggestion: string };
export type Field = {
  value: string; source: FieldSource; confidence?: number; note?: string;
  /** California: the same box read again from a later page (null match = not printed again) */
  check?: { other: string; match: boolean | null };
  /** Where on the document the value was read (page + normalised box) — shown next to the cell. */
  region?: Region;
  /** Possible OCR misreadings: shown with a suggestion, never corrected silently. */
  suspects?: Suspect[];
  /** Owner compared the cell with the page ("đã kiểm tra"). Cells read from an image cannot be saved before. */
  checked?: boolean;
  /** Address cells: principal | mailing | agent | return_to | principal_ca */
  role?: string;
  warning?: string;
  /** Column D only: source_pdf (printed on the PDF) | provisioned (from the owner's provider) | needs_setup | manual */
  phone_source?: "source_pdf" | "provisioned" | "needs_setup" | "manual" | "placeholder";
  provider?: string;
  verified_active?: boolean;
};
/** An address printed on the form that is not the company's own (agent, Return to, a second office): offered only. */
export type AddressCandidate = {
  role: string; label: string; street: string; city: string; state: string; zip: string; confidence?: number;
  region?: Region; suspects?: Suspect[];
};
export type ScanInfo = {
  form?: string; version?: string; versionVerified?: boolean; pagesRead?: number; filedDate?: string;
  formationState?: string; formationDate?: string; warning?: string; note?: string; addressSource?: string;
};
export type Fields = Record<FieldKey, Field>;

/* ───────────────────────── Document types ───────────────────────── */

export type DocType = "wa" | "wy" | "ca" | "br" | "unknown";

type DocTypeMeta = {
  label: string;
  short: string;
  form: string;
  tagCls: string;
  /** Label printed on the original document for each sheet column. */
  origin: Partial<Record<FieldKey, string>>;
};

export const DOC_TYPES: Record<DocType, DocTypeMeta> = {
  wa: {
    label: "Washington",
    short: "WA",
    form: "Certificate of Formation / Annual Report · Washington Secretary of State",
    tagCls: "border-indigo-400/30 bg-indigo-500/15 text-indigo-200",
    origin: { A: "Business Name", D: "Principal Office · Phone", F: "Principal Office · Street Address (hoặc Registered Agent)", G: "City", H: "State", I: "ZIP", J: "UBI Number" },
  },
  wy: {
    label: "Wyoming LLC",
    short: "WY",
    form: "Articles of Organization · Wyoming Secretary of State",
    tagCls: "border-sky-400/30 bg-sky-500/15 text-sky-200",
    origin: { A: "Name of the LLC", D: "Daytime phone", F: "Mailing address", G: "City", H: "State", I: "Zip", J: "Original ID" },
  },
  ca: {
    label: "California LLC",
    short: "CA",
    form: "Articles of Organization (LLC-1) · California Secretary of State",
    tagCls: "border-amber-400/30 bg-amber-500/15 text-amber-200",
    origin: { A: "① LLC Name", D: "LLC-1 không có ô SĐT", F: "③a Initial Street Address", G: "③a City", H: "③a State", I: "③a Zip", J: "Số 12 chữ số góc phải" },
  },
  br: {
    label: "Brazil CNPJ",
    short: "BR",
    form: "Comprovante de Inscrição / Ficha cadastral · Receita Federal",
    tagCls: "border-emerald-400/30 bg-emerald-500/15 text-emerald-200",
    origin: { A: "Nome empresarial", D: "Telefone (số đầu)", F: "Logradouro, Número, Complemento, Bairro, Município, UF CEP", G: "Município", H: "UF", I: "CEP (chỉ số)", J: "Número de inscrição (CNPJ)" },
  },
  unknown: {
    label: "Chưa nhận diện",
    short: "?",
    form: "Không khớp mẫu phôi nào đã biết",
    tagCls: "border-rose-400/35 bg-rose-500/15 text-rose-200",
    origin: {},
  },
};

export const KNOWN_DOC_TYPES: DocType[] = ["wa", "br", "wy", "ca"];

export type Detection = { confidence: number; reason: string; manual?: boolean };

/* ───────────────────────── Sheet fields ───────────────────────── */

export const FIELD_META: { key: FieldKey; label: string; critical?: boolean; wide?: boolean }[] = [
  { key: "A", label: "Tên doanh nghiệp", critical: true, wide: true },
  { key: "D", label: "Số điện thoại" },
  { key: "E", label: "Tên rút gọn" },
  { key: "F", label: "Địa chỉ", wide: true },
  { key: "G", label: "Thành phố" },
  { key: "H", label: "Bang / UF" },
  { key: "I", label: "ZIP / CEP" },
  { key: "J", label: "Mã đăng ký / CNPJ", critical: true },
];

export const FIELD_LABEL = Object.fromEntries(FIELD_META.map((m) => [m.key, m.label])) as Record<FieldKey, string>;

export function fieldHint(key: FieldKey, t: DocType): string {
  const br = t === "br";
  switch (key) {
    case "A": return br ? "Đúng như Nome empresarial" : "Giữ LLC / Inc.";
    case "D": return br ? "(11) 0000-0000 — số đầu tiên" : "(XXX) XXX-XXXX";
    case "E": return "Tự sinh từ A";
    case "F": return br ? "ĐƯỜNG, SỐ, PHỤ, KHU, THÀNH PHỐ, UF CEP" : "ĐƯỜNG, THÀNH PHỐ, BANG ZIP";
    case "G": return "";
    case "H": return br ? "SP" : t === "ca" ? "CA" : t === "wa" ? "WA" : "WY";
    case "I": return br ? "8 chữ số" : "5 số (hoặc 5+4)";
    case "J": return br ? "00.000.000/0000-00" : t === "ca" ? "12 số" : t === "wa" ? "UBI 9 số" : "2024-000000000";
  }
}

/** Legacy column E rule: lowercase, keep the legal suffix, strip accents and symbols. */
export const shortName = (a: string) =>
  a.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");

/* ───────────────────────── Industry (DB only, not a sheet column) ───────────────────────── */

export type IndustryKey =
  | "construction" | "tech" | "dental" | "health" | "beauty" | "legal" | "finance" | "education"
  | "travel" | "retail" | "agriculture" | "environment" | "media" | "hr" | "logistics" | "general";

/** `keyword` feeds the legacy industry detector to pick the website template. */
export const INDUSTRIES: Record<IndustryKey, { label: string; keyword: string }> = {
  construction: { label: "Xây dựng", keyword: "construction" },
  tech: { label: "Công nghệ", keyword: "software" },
  dental: { label: "Nha khoa", keyword: "dental" },
  health: { label: "Y tế", keyword: "clinic" },
  beauty: { label: "Làm đẹp / Spa", keyword: "spa" },
  legal: { label: "Pháp lý", keyword: "law" },
  finance: { label: "Bảo hiểm / Tài chính", keyword: "insurance" },
  education: { label: "Giáo dục", keyword: "academy" },
  travel: { label: "Du lịch", keyword: "travel" },
  retail: { label: "Thương mại / Bán lẻ", keyword: "shop" },
  agriculture: { label: "Nông nghiệp / Chăn nuôi", keyword: "ranch" },
  environment: { label: "Môi trường", keyword: "waste" },
  media: { label: "Truyền thông", keyword: "media" },
  hr: { label: "Nhân sự", keyword: "staffing" },
  logistics: { label: "Vận tải / Logistics", keyword: "freight" },
  general: { label: "Dịch vụ chung", keyword: "consulting" },
};

export type Industry = {
  raw: string; // as printed (CNAE description) or the words it was inferred from
  code?: string; // CNAE code, kept as text: "01.51-2-01"
  category: IndustryKey;
  source: "doc" | "name" | "manual";
};

export const templateFor = (ind: Industry): SiteTemplate => detectTemplate(INDUSTRIES[ind.category].keyword);

const NAME_HINTS: [RegExp, IndustryKey][] = [
  [/roof|build|construct|construtora|concrete|carpent/, "construction"],
  [/software|digital|tech|sistema|data|labs/, "tech"],
  [/dental|odonto|dds/, "dental"],
  [/clinic|medic|health|saude/, "health"],
  [/salon|spa|beauty|estetica/, "beauty"],
  [/legal|law|attorney|advoca/, "legal"],
  [/insur|seguro|capital|financ/, "finance"],
  [/media|studio|film/, "media"],
  [/freight|logist|transport/, "logistics"],
  [/ranch|farm|cattle|agro|agropec/, "agriculture"],
  [/shop|store|comercio|loja/, "retail"],
];

/** Wyoming / California filings print no industry — infer from the company name. */
export function industryFromName(name: string): Industry {
  const n = shortName(name);
  const hit = NAME_HINTS.find(([re]) => re.test(n));
  return { raw: name, category: hit?.[1] ?? "general", source: "name" };
}

/* ───────────────────────── Validation ───────────────────────── */

export type Issue = { level: "error" | "warn"; kind: "missing" | "critical" | "format" | "review"; msg: string };

const UF = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

export function isValidCnpj(v: string): boolean {
  const d = v.replace(/\D/g, "");
  if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
  const n = d.split("").map(Number);
  return checkDigits(n.slice(0, 12)).join("") === d.slice(12);
}

function checkDigits(base12: number[]): [number, number] {
  const w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const calc = (arr: number[], w: number[]) => {
    const r = arr.reduce((s, x, i) => s + x * w[i], 0) % 11;
    return r < 2 ? 0 : 11 - r;
  };
  const d1 = calc(base12, w1);
  return [d1, calc([...base12, d1], [6, ...w1])];
}

const LEGAL_SUFFIX_US = /\b(llc|l\.l\.c\.?|inc\.?|corp\.?|pllc|co\.?|ltd\.?)$/i;

export function validate(fields: Fields, t: DocType): Partial<Record<FieldKey, Issue>> {
  const out: Partial<Record<FieldKey, Issue>> = {};
  const br = t === "br";

  for (const m of FIELD_META) {
    const fld = fields[m.key];
    const v = fld.value.trim();
    const digits = v.replace(/\D/g, "");
    const set = (level: Issue["level"], kind: Issue["kind"], msg: string) => (out[m.key] = { level, kind, msg });

    if (!v) {
      if (m.critical) set("error", "critical", "Trường quan trọng — bắt buộc có, không được để trống");
      else set("error", "missing", "Không tìm thấy trong PDF — không tự điền");
      continue;
    }

    switch (m.key) {
      case "A":
        // Brazilian names legitimately lack a suffix (funds, associations) — the legal form
        // comes from "Natureza jurídica", so only US filings are checked here.
        if (!br && !LEGAL_SUFFIX_US.test(v)) set("warn", "review", "Tên chưa có hậu tố LLC / Inc. — đối chiếu lại phôi");
        break;
      case "D": {
        // A comprovante can print several numbers ("(55) 3223-1635 / (55) 3217-0922"): kept as printed.
        // A country code is fine: +55 (Brazil) or +1 (US) in front of the 10–11 digits.
        const parts = v.split("/").map((x) => x.replace(/\D/g, "").replace(/^55(?=\d{10,11}$)/, "").replace(/^1(?=\d{10}$)/, ""));
        if (parts.some((d) => d.length !== 10 && d.length !== 11)) set("error", "format", "Mỗi số điện thoại phải có 10–11 chữ số");
        else if (parts.length > 1) set("warn", "review", `Phôi có ${parts.length} số — giữ nguyên như phôi`);
        break;
      }
      case "H":
        if (t === "wa" && !/^[A-Z]{2}$/.test(v)) set("warn", "review", "Không phải mã bang Mỹ 2 chữ (trụ sở ở nước ngoài?) — đối chiếu phôi");
        else if (br ? !UF.includes(v) : !/^[A-Z]{2}$/.test(v)) set("error", "format", br ? "UF không hợp lệ (vd: SP, RJ, MG)" : "Bang phải là 2 chữ in hoa");
        else if ((t === "wy" && v !== "WY") || (t === "ca" && v !== "CA"))
          set("warn", "review", `Phôi ${DOC_TYPES[t].short} nhưng bang là ${v} — kiểm tra lại`);
        break;
      case "I":
        if (br) {
          // The Sheet keeps the CEP digits ("39100000"); "00.000-000" as printed is accepted too.
          if (!/^\d{8}$/.test(v) && !/^\d{2}\.?\d{3}-\d{3}$/.test(v))
            set("error", "format", digits.length === 7 ? "CEP còn 7 số — có thể đã mất số 0 ở đầu" : "CEP phải dạng 00.000-000");
        } else if (t === "wa" && !/^\d{5}(-\d{4})?$/.test(v)) set("warn", "review", "Không phải ZIP Mỹ (trụ sở ở nước ngoài?) — đối chiếu phôi");
        else if (!/^\d{5}(-\d{4})?$/.test(v))
          set("error", "format", digits.length === 4 ? "ZIP còn 4 số — có thể đã mất số 0 ở đầu" : "ZIP phải có 5 số");
        break;
      case "J":
        if (br) {
          if (digits.length === 13) set("error", "format", "CNPJ còn 13 số — có thể đã mất số 0 ở đầu");
          else if (digits.length !== 14) set("error", "format", "CNPJ phải có đủ 14 số");
          else if (!isValidCnpj(v)) set("error", "format", "Sai số kiểm tra CNPJ — đọc nhầm số, đối chiếu lại phôi");
        } else if (t === "ca") {
          // Structure of CA entity numbers is NOT confirmed (one sample only):
          // basic check, warn on doubt, never block saving.
          if (!/^\d{12}$/.test(v)) set("warn", "review", "Khác dạng thường gặp (12 chữ số) — đối chiếu lại phôi; vẫn được lưu");
        } else if (t === "wa") {
          if (!/^\d{9}$/.test(v)) set("warn", "review", "UBI thường có 9 chữ số — đối chiếu lại phôi");
        } else if (t === "wy" && !/^\d{4}-\d{9}$/.test(v)) set("error", "format", "Original ID Wyoming dạng 2024-000000000");
        break;
    }

    // California: compare with the copy printed on a later page (gone once the owner edits the box)
    if (fld.check && out[m.key]?.level !== "error") {
      if (fld.check.match === false && m.key === "J")
        set("error", "format", `Khác số in lại ở trang sau (${fld.check.other}) — đối chiếu PDF rồi sửa tay`);
      else if (fld.check.match === false) set("warn", "review", `Tên ở trang sau ghi “${fld.check.other}” — đối chiếu lại`);
      else if (fld.check.match === null && m.key === "J")
        set("warn", "review", "Không thấy số in lại ở trang sau để đối chiếu — kiểm tra bằng mắt");
    }

    if (!out[m.key] && fld.suspects?.length) set("warn", "review", `Có thể đọc nhầm: ${fld.suspects[0].message}`);
    else if (!out[m.key] && fld.warning) set("warn", "review", fld.warning);
    if (!out[m.key] && (fld.source === "ai" || fld.source === "ocr") && (fld.confidence ?? 100) < (m.critical ? 95 : 85))
      set("warn", "review", `${fld.source === "ocr" ? "OCR" : "AI"} đọc với độ tin cậy ${fld.confidence}% — cần đối chiếu`);
  }
  return out;
}

/** Leading zero present: the value must stay text (shown as a hint in the form). */
export const hasLeadingZero = (v: string) => /^0/.test(v.trim()) || /(^|[^\d])0\d/.test(v.trim());

/* ───────────────────────── Files & pipeline ───────────────────────── */

export type PdfStatus = "queued" | "processing" | "review" | "saving" | "saved" | "failed" | "duplicate";

export const PROCESS_STEPS = ["Đọc PDF", "Nhận diện loại phôi", "Trích xuất", "Kiểm tra trùng"] as const;
/**
 * Drive first. The Drive file id is stored as soon as the upload is verified,
 * so a failed Sheet write is retried without uploading the PDF again.
 */
export const SAVE_STEPS = [
  "Kiểm tra trùng: mã số + md5 trên Drive",
  "Upload PDF gốc lên Drive",
  "Xác minh md5 bản trên Drive",
  "Ghi dòng A, D–K vào Sheet",
] as const;

/**
 * Raw boxes of a CNPJ comprovante, exactly as printed (uppercase, no accents,
 * "********" for empty). Column F is assembled from these; everything else is
 * stored in the database for later use.
 */
export type BrRaw = {
  nome: string;
  fantasia: string;
  porte: string;
  abertura: string;
  cnaePrincipal: string;
  cnaeSecundarias: string[];
  natureza: string;
  logradouro: string;
  numero: string;
  complemento: string;
  cep: string;
  bairro: string;
  municipio: string;
  uf: string;
  email: string;
  /** owner confirmed it is the business's official contact (only then can a website show it) */
  emailVerified?: boolean;
  telefone: string;
  situacao: string;
  dataSituacao: string;
};

export type PdfFile = {
  id: string;
  name: string;
  sizeKb: number;
  pages: number;
  md5: string;
  status: PdfStatus;
  step: number;
  progress: number;
  docType: DocType;
  detection: Detection | null;
  fields: Fields | null;
  industry: Industry | null;
  br?: BrRaw;
  textLayer: boolean;
  error?: string;
  failedAt?: "process" | "sheet";
  duplicateOf?: { row: number; name: string; reason: string };
  sheetRow?: number;
  driveFileId?: string;
  driveLink?: string;
  confirmMissing?: boolean;
  criticalChecked?: boolean;
  /** Demo only: how the fake pipeline ends. */
  outcome?: "review" | "failed" | "sheetFail";
  blobUrl?: string;
  local?: boolean;
  /** Scanned form waiting for the AI read (backend status needs_ai). */
  needsAi?: boolean;
  aiRunning?: boolean;
  candidates?: AddressCandidate[];
  scan?: ScanInfo;
};

export type Extracted = { fields: Fields; industry: Industry; br?: BrRaw };

const f = (value: string, source: FieldSource = "text", confidence?: number, note?: string): Field =>
  value ? { value, source, confidence, note } : { value: "", source: "missing" };

const blankBox = (v: string) => !v.trim() || /^\*+$/.test(v.trim());

/** F = LOGRADOURO, NÚMERO, COMPLEMENTO - BAIRRO; skips "********" and a number already in the logradouro. */
export function composeBrAddress(r: BrRaw): string {
  const parts = [r.logradouro.trim()];
  const num = r.numero.trim();
  if (!blankBox(num) && !new RegExp(`\\b${num}$`).test(r.logradouro.trim())) parts.push(num);
  if (!blankBox(r.complemento)) parts.push(r.complemento.trim());
  return parts.join(", ") + (blankBox(r.bairro) ? "" : ` - ${r.bairro.trim()}`);
}

/** Builds a CNPJ with valid check digits from its first 12 digits (demo data only). */
function cnpj(base12: string): string {
  const all = base12 + checkDigits(base12.split("").map(Number)).join("");
  return `${all.slice(0, 2)}.${all.slice(2, 5)}.${all.slice(5, 8)}/${all.slice(8, 12)}-${all.slice(12)}`;
}

function brExtract(r: BrRaw, j: string, category: IndustryKey, src: FieldSource = "text"): Extracted {
  const [code, ...rest] = r.cnaePrincipal.split(" - ");
  const tel = blankBox(r.telefone) ? "" : r.telefone;
  return {
    br: r,
    industry: { code, raw: rest.join(" - "), category, source: "doc" },
    fields: {
      A: f(r.nome, src, src === "ai" ? 96 : undefined),
      D: f(tel, src, src === "ai" ? 94 : undefined),
      E: { value: shortName(r.nome), source: "auto" },
      F: f(composeBrAddress(r), src, src === "ai" ? 92 : undefined, "Ghép LOGRADOURO + NÚMERO + COMPLEMENTO - BAIRRO"),
      G: f(r.municipio, src, src === "ai" ? 97 : undefined),
      H: f(r.uf, src, src === "ai" ? 99 : undefined),
      I: f(r.cep, src, src === "ai" ? 95 : undefined),
      J: f(j, src, src === "ai" ? 97 : undefined),
    },
  };
}

const brRaw = (p: Partial<BrRaw> & Pick<BrRaw, "nome" | "cnaePrincipal" | "logradouro" | "numero" | "cep" | "bairro" | "municipio" | "uf">): BrRaw => ({
  fantasia: "********", porte: "ME", abertura: "14/03/2019", cnaeSecundarias: [], natureza: "206-2 - Sociedade Empresária Limitada",
  complemento: "********", email: "", telefone: "", situacao: "ATIVA", dataSituacao: "14/03/2019", ...p,
});

type UsBase = { a: string; d: string; street: string; city: string; st: string; zip: string; j: string };

function us(b: UsBase, src: FieldSource = "text", conf: Partial<Record<FieldKey, number>> = {}, notes: Partial<Record<FieldKey, string>> = {}): Fields {
  const pick = (k: FieldKey, v: string) => f(v, src, src === "ai" ? (conf[k] ?? 97) : undefined, notes[k]);
  return {
    A: pick("A", b.a),
    D: pick("D", b.d),
    E: b.a ? { value: shortName(b.a), source: "auto" } : f(""),
    F: pick("F", b.street),
    G: pick("G", b.city),
    H: pick("H", b.st),
    I: pick("I", b.zip),
    J: pick("J", b.j),
  };
}

const CA_NOTES = { H: "Phôi ghi “California” → chuẩn hoá CA", J: "Khớp số in ở trang 1 và trang Attachment" };
const ca = (b: Omit<UsBase, "st" | "d">, conf: Partial<Record<FieldKey, number>> = {}) =>
  us({ ...b, st: "CA", d: "" }, "ai", conf, CA_NOTES);
const wy = (a: string, d: string, street: string, city: string, zip: string, j: string) => us({ a, d, street, city, st: "WY", zip, j });

const md5 = (seed: number) =>
  Array.from({ length: 32 }, (_, i) => "0123456789abcdef"[(seed * 7 + i * 13 + ((seed * i) % 11)) % 16]).join("");

const DET = {
  wa: { confidence: 97, reason: "“Filed Secretary of State · State of Washington”, có số UBI" },
  wy: { confidence: 99, reason: "Tiêu đề “STATE OF WYOMING · Articles of Organization”, có Original ID" },
  ca: { confidence: 96, reason: "Bản scan mẫu LLC-1 (REV 01/2013): khung “Articles of Organization of a Limited Liability Company”, dấu FILED · State of California" },
  br: { confidence: 99, reason: "“CADASTRO NACIONAL DA PESSOA JURÍDICA · Comprovante de Inscrição” · có lớp chữ, đọc thẳng từng ô" },
};

const BR = {
  horizonte: brExtract(
    brRaw({
      nome: "CONSTRUTORA HORIZONTE AZUL LTDA", cnaePrincipal: "41.20-4-00 - Construção de edifícios",
      logradouro: "AV PAULISTA 1578", numero: "1578", complemento: "CONJ 42", cep: "01.310-200", bairro: "BELA VISTA",
      municipio: "SAO PAULO", uf: "SP", telefone: "(11) 3251-4400", email: "CONTATO@HORIZONTEAZUL.COM.BR",
    }),
    cnpj("006239040001"),
    "construction",
  ),
  alfa: brExtract(
    brRaw({
      nome: "ALFA SISTEMAS DIGITAIS LTDA", fantasia: "ALFA DIGITAL", cnaePrincipal: "62.01-5-01 - Desenvolvimento de programas de computador sob encomenda",
      logradouro: "R XV DE NOVEMBRO", numero: "300", complemento: "SALA 804", cep: "80.020-310", bairro: "CENTRO",
      municipio: "CURITIBA", uf: "PR", telefone: "(41) 3322-5180", abertura: "02/08/2016",
    }),
    cnpj("045210870001"),
    "tech",
  ),
  vale: brExtract(
    brRaw({
      nome: "AGROPECUARIA VALE VERDE LTDA", cnaePrincipal: "01.51-2-01 - Criação de bovinos para corte",
      cnaeSecundarias: ["01.15-6-00 - Cultivo de soja"], logradouro: "ROD GO-060 KM 12", numero: "S/N", cep: "75.380-000",
      bairro: "ZONA RURAL", municipio: "TRINDADE", uf: "GO", telefone: "(62) 3505-1122", porte: "DEMAIS",
    }),
    cnpj("012874550001"),
    "agriculture",
  ),
  sorriso: brExtract(
    brRaw({
      nome: "CLINICA ODONTOLOGICA SORRISO PLENO LTDA", fantasia: "SORRISO PLENO", cnaePrincipal: "86.30-5-04 - Atividade odontológica",
      logradouro: "R DA BAHIA", numero: "1200", complemento: "LOJA 02", cep: "30.160-011", bairro: "CENTRO",
      municipio: "BELO HORIZONTE", uf: "MG", telefone: "(31) 3274-9910",
    }),
    cnpj("087641230001"),
    "dental",
  ),
  // Mirrors the association sample: no phone, no e-mail, no LTDA suffix, house number "02".
  associacao: brExtract(
    brRaw({
      nome: "ASSOCIACAO CULTURAL VILA NOVA ESPERANCA", cnaePrincipal: "94.93-6-00 - Atividades de organizações associativas ligadas à cultura e à arte",
      natureza: "399-9 - Associação Privada", porte: "DEMAIS", logradouro: "R JOAQUIM DIAS", numero: "02", cep: "02.913-040",
      bairro: "VL NOVA CACHOEIRINHA", municipio: "SAO PAULO", uf: "SP", abertura: "21/09/1998",
    }),
    cnpj("001248830001"),
    "media",
  ),
};

const base = (p: Partial<PdfFile> & Pick<PdfFile, "id" | "name" | "docType" | "status">): PdfFile => ({
  sizeKb: 240, pages: 1, md5: md5(p.id.length * 31 + p.name.length), step: 0, progress: 0,
  detection: p.docType === "unknown" ? null : DET[p.docType as "wa" | "wy" | "ca" | "br"], fields: null, industry: null,
  textLayer: p.docType !== "ca",
  ...p,
});

const done = (e: Extracted) => ({ fields: e.fields, industry: e.industry, br: e.br });

export const MOCK_FILES: PdfFile[] = [
  base({
    id: "p1", name: "2024-001312455-articles.pdf", docType: "wy", status: "saved", step: 3, progress: 100, pages: 2, sizeKb: 284,
    fields: wy("Bighorn Basin Roofing LLC", "(307) 555-0412", "418 Grand Ave", "Laramie", "82070", "2024-001312455"),
    industry: industryFromName("Bighorn Basin Roofing LLC"),
    sheetRow: 43, driveFileId: "1AbX7qWyRoof", driveLink: "https://drive.google.com/file/d/demo-p1/view",
  }),
  base({
    id: "p2", name: "ALFA SISTEMAS DIGITAIS LTDA.pdf", docType: "br", status: "saved", step: 3, progress: 100, sizeKb: 118,
    ...done(BR.alfa), sheetRow: 44, driveFileId: "1BrQ9alfaSist", driveLink: "https://drive.google.com/file/d/demo-p2/view",
  }),
  base({
    id: "p3", name: "40211873-1.pdf", docType: "ca", status: "saved", step: 3, progress: 100, pages: 2, sizeKb: 905,
    fields: ca({ a: "Pacific Crest Dental Group, LLC", street: "1450 Fifth Ave. Ste 300", city: "San Diego", zip: "92101", j: "202315814027" }),
    industry: industryFromName("Pacific Crest Dental Group LLC"), confirmMissing: true, criticalChecked: true,
    sheetRow: 45, driveFileId: "1CaZ3pacDent", driveLink: "https://drive.google.com/file/d/demo-p3/view",
  }),
  base({
    id: "p4", name: "Absaroka Software Labs - Articles.pdf", docType: "wy", status: "review", step: 3, progress: 100, pages: 2,
    fields: wy("Absaroka Software Labs LLC", "(307) 555-0623", "1401 Sheridan Ave", "Cody", "82414", "2024-001331087"),
    industry: industryFromName("Absaroka Software Labs LLC"),
  }),
  base({
    id: "p5", name: "38511204-1.pdf", docType: "ca", status: "review", step: 3, progress: 100, pages: 2, sizeKb: 1180,
    fields: ca(
      { a: "Sunset Ridge Builders, LLC", street: "1840 W. Olympic Blvd. Ste 210", city: "Los Angeles", zip: "90015", j: "201431610432" },
      { A: 93, J: 88, F: 90, G: 96, H: 99, I: 91 },
    ),
    industry: industryFromName("Sunset Ridge Builders LLC"),
  }),
  base({ id: "p6", name: "CONSTRUTORA HORIZONTE AZUL LTDA.pdf", docType: "br", status: "review", step: 3, progress: 100, sizeKb: 121, ...done(BR.horizonte) }),
  base({ id: "p7", name: "AGROPECUARIA VALE VERDE LTDA.pdf", docType: "br", status: "processing", step: 2, progress: 50, outcome: "review" }),
  base({ id: "p8", name: "green-river-freight-annual.pdf", docType: "wy", status: "processing", step: 0, progress: 75, pages: 2, outcome: "review" }),
  base({
    id: "p9", name: "laramie-legal-annual-report.pdf", docType: "wy", status: "duplicate", step: 3, progress: 100,
    fields: wy("Laramie Legal Group LLC", "(307) 555-0159", "379 Lincolnway", "Riverton", "82501", "2024-001292774"),
    industry: industryFromName("Laramie Legal Group LLC"),
    duplicateOf: { row: 10, name: "Laramie Legal Group LLC", reason: "Trùng mã đăng ký J + bang WY" },
  }),
  base({
    id: "p10", name: "CLINICA ODONTOLOGICA SORRISO PLENO LTDA.pdf", docType: "br", status: "failed", failedAt: "sheet", step: 3, progress: 100, sizeKb: 116,
    ...done(BR.sorriso), driveFileId: "1SrP4sorrisoPl",
    error: "Google Sheets trả lỗi 429 (vượt giới hạn ghi). PDF đã nằm trên Drive và đã lưu ID — thử lại chỉ ghi Sheet, không upload lại.",
  }),
  base({
    id: "p11", name: "scan_0618.pdf", docType: "unknown", status: "review", step: 3, progress: 100, sizeKb: 1720, textLayer: false,
    detection: { confidence: 41, reason: "Trang 1 bị cắt mất phần tiêu đề — không khớp chắc chắn mẫu nào (gần nhất: California LLC-1, 41%)" },
    fields: us({ a: "", d: "", street: "", city: "", st: "", zip: "", j: "" }),
  }),
  base({
    id: "p12", name: "scan_0021232316.pdf", docType: "ca", status: "failed", failedAt: "process", step: 2, progress: 100, sizeKb: 2240,
    error: "Bản scan quá mờ — AI chỉ đọc được 31% nội dung, không xác định được tên công ty và Entity No. Không tự điền.",
  }),
  base({ id: "p13", name: "vedauwoo-media-group.pdf", docType: "wy", status: "queued", pages: 2, outcome: "review" }),
  base({ id: "p14", name: "ASSOCIACAO CULTURAL VILA NOVA ESPERANCA.pdf", docType: "br", status: "queued", outcome: "review" }),
  base({ id: "p15", name: "39822105-1.pdf", docType: "ca", status: "queued", outcome: "sheetFail", pages: 2, sizeKb: 860 }),
];

/** Demo extraction results for files that are still queued/processing. */
export const MOCK_RESULTS: Record<string, Extracted> = {
  p7: BR.vale,
  p8: {
    fields: wy("Green River Freight LLC", "(307) 555-0718", "1188 Dewar Dr", "Rock Springs", "82901", "2024-001335902"),
    industry: industryFromName("Green River Freight LLC"),
  },
  p13: {
    fields: wy("Vedauwoo Media Group LLC", "(307) 555-0832", "605 S 3rd St", "Laramie", "82070", "2024-001337156"),
    industry: industryFromName("Vedauwoo Media Group LLC"),
  },
  p14: BR.associacao,
  p15: {
    fields: ca({ a: "Redwood Legal Partners, LLC", street: "500 Capitol Mall Ste 1100", city: "Sacramento", zip: "95814", j: "201509710158" }),
    industry: industryFromName("Redwood Legal Partners LLC"),
  },
};

/** Demo result when the user picks a type for an unrecognised file and re-reads it. */
export const RESCAN_SAMPLES: Record<Exclude<DocType, "unknown">, Extracted> = {
  wa: {
    fields: us({ a: "Cascade Ridge Media LLC", d: "(206) 555-0142", street: "1201 3rd Ave Ste 400", city: "Seattle", st: "WA", zip: "98101", j: "604000123" }, "ai"),
    industry: industryFromName("Cascade Ridge Media LLC"),
  },
  ca: {
    fields: ca({ a: "Golden State Media Studio, LLC", street: "6255 Sunset Blvd. Ste 1500", city: "Los Angeles", zip: "90028", j: "201600382150" }, { A: 96, J: 97 }),
    industry: industryFromName("Golden State Media Studio LLC"),
  },
  wy: {
    fields: us({ a: "Teton Basin Media LLC", d: "(307) 555-0610", street: "155 W Pearl Ave", city: "Jackson", st: "WY", zip: "83001", j: "2024-001340221" }, "ai"),
    industry: industryFromName("Teton Basin Media LLC"),
  },
  br: brExtract(
    brRaw({
      nome: "ESTUDIO LUZ NORTE LTDA", cnaePrincipal: "59.11-1-99 - Atividades de produção cinematográfica, de vídeos e de programas de televisão",
      logradouro: "AV EDUARDO RIBEIRO", numero: "520", cep: "69.010-001", bairro: "CENTRO", municipio: "MANAUS", uf: "AM", telefone: "(92) 3234-5566",
    }),
    cnpj("009512330001"),
    "media",
    "ai",
  ),
};

export const SHEET_TABS = ["Phoi US", "Tinh Tool"] as const;
