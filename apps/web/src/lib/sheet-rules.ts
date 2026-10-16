/**
 * Business rules shared by the three independent modules.
 * Column letters follow the existing Google Sheet (A..L). Each module may
 * only write its own column, and only when that cell is still empty.
 */

export type SheetRow = {
  row: number; // 1-based sheet row (data starts at row 3: row 1 = title, row 2 = header)
  A: string; // business name
  B: string; // domain            — written by Domain Manager only
  C: string; // https website url — written by SSL + Website Builder only
  D: string; // phone
  E: string; // short name / slug
  F: string; // street address
  G: string; // city
  H: string; // state
  I: string; // zip
  J: string; // registration / control id
  K: string; // "Xem phôi" Google Drive link
  L: string; // legacy label (role still to be confirmed)
};

export type ModuleKey = "pdf" | "domain" | "web";

export const MODULE_COLUMN: Record<ModuleKey, keyof SheetRow> = {
  pdf: "K",
  domain: "B",
  web: "C",
};

const filled = (v: string) => v.trim().length > 0;

/** Domain Manager picks rows whose column B is empty. */
export const isEligibleForDomain = (r: SheetRow) => !filled(r.B);

/** SSL + Website Builder picks rows with a domain in B and an empty C. */
export const isEligibleForWebsite = (r: SheetRow) => filled(r.B) && !filled(r.C);

/**
 * Guard used right before any write: re-read the live cell and only write
 * when it is still empty. A non-empty cell means someone else (a person or
 * another run) already filled it — that is a conflict, never an overwrite.
 */
export function canWriteCell(liveValue: string): "write" | "conflict" {
  return filled(liveValue) ? "conflict" : "write";
}

/** Idempotency keys so a re-run never creates a duplicate PDF, domain or site. */
export const idempotencyKey = {
  pdf: (md5: string, controlId: string, state: string) => `pdf:${md5}:${state}:${controlId}`,
  domain: (domain: string) => `domain:${domain.toLowerCase()}`,
  web: (domain: string) => `web:${domain.toLowerCase()}`,
};
