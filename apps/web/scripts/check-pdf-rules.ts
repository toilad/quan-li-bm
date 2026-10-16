/**
 * Checks the PDF field rules with FAKE values that follow the formats seen on
 * the owner's sample filings (real values stay out of git — see test-fixtures/).
 * Run: npm run check:pdf-rules
 */
import { composeBrAddress, isValidCnpj, validate, type BrRaw, type DocType, type Fields } from "../src/lib/pdf-mock";

let failed = 0;
const check = (name: string, ok: boolean) => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}`);
  if (!ok) failed++;
};

const fields = (v: Partial<Record<keyof Fields, string>>): Fields =>
  Object.fromEntries(
    (["A", "D", "E", "F", "G", "H", "I", "J"] as const).map((k) => [k, { value: v[k] ?? "", source: v[k] ? "text" : "missing" }]),
  ) as Fields;
const issuesOf = (v: Partial<Record<keyof Fields, string>>, t: DocType) => validate(fields(v), t);

// CNPJ check digits (fake numbers, valid digits generated independently), leading zeros kept as text.
for (const c of ["00.123.456/0001-49", "00.098.765/0001-06", "07.112.233/0001-25"]) check(`CNPJ hợp lệ ${c}`, isValidCnpj(c));
check("CNPJ sai số kiểm tra bị bắt", !isValidCnpj("07.112.233/0001-26"));
check("CNPJ mất số 0 đầu (13 số) bị báo", issuesOf({ J: "0.123.456/0001-49" }, "br").J?.msg.includes("số 0") ?? false);

// CEP printed as "00.000-000" on the comprovante.
for (const cep of ["01.234-567", "09.876-000", "70.040-010"]) check(`CEP hợp lệ ${cep}`, !issuesOf({ I: cep }, "br").I);
check("CEP mất số 0 đầu bị báo", issuesOf({ I: "1234567" }, "br").I?.msg.includes("số 0") ?? false);

// Names without LTDA (funds, associations) must not be flagged.
check("Tên hiệp hội không có LTDA không bị cảnh báo", !issuesOf({ A: "ASSOCIACAO DE MORADORES DO BAIRRO EXEMPLO" }, "br").A);

// Empty phone → confirmable "missing", never invented. Empty name → critical.
check("SĐT trống = thiếu, cần xác nhận", issuesOf({ D: "" }, "br").D?.kind === "missing");
check("Tên trống = trường quan trọng", issuesOf({ A: "" }, "br").A?.kind === "critical");

// Address assembly.
const raw = (p: Partial<BrRaw>) => ({ logradouro: "", numero: "", complemento: "********", bairro: "", ...p }) as BrRaw;
check(
  "Địa chỉ không lặp số nhà đã có trong logradouro",
  composeBrAddress(raw({ logradouro: "AV EXEMPLO 1500", numero: "1500", complemento: "SALA 12", bairro: "CENTRO" })) ===
    "AV EXEMPLO 1500, SALA 12 - CENTRO",
);
check(
  "Địa chỉ giữ số nhà '02', bỏ complemento '********'",
  composeBrAddress(raw({ logradouro: "R TESTE", numero: "02", bairro: "VILA MODELO" })) === "R TESTE, 02 - VILA MODELO",
);
check(
  "Địa chỉ có complemento",
  composeBrAddress(raw({ logradouro: "R DAS FLORES", numero: "321", complemento: "LOJA 4", bairro: "JARDIM" })) ===
    "R DAS FLORES, 321, LOJA 4 - JARDIM",
);

// California LLC-1: only a basic format check — warn, never block (rule not confirmed).
check("Entity No. CA 12 số không bị cảnh báo", !issuesOf({ J: "209900012345" }, "ca").J);
check("Entity No. CA 11 số chỉ cảnh báo, không chặn", issuesOf({ J: "20990001234" }, "ca").J?.level === "warn");
check("Entity No. CA có chữ chỉ cảnh báo, không chặn", issuesOf({ J: "B2099000123" }, "ca").J?.level === "warn");
check("Bang 'California' chưa chuẩn hoá bị báo", !!issuesOf({ H: "California" }, "ca").H);
check("ZIP CA 90000 hợp lệ", !issuesOf({ I: "90000" }, "ca").I);
check("ZIP 01234 giữ số 0 hợp lệ", !issuesOf({ I: "01234" }, "wy").I);
check("Tên 'Example Supply Co., LLC' không bị cảnh báo hậu tố", !issuesOf({ A: "Example Supply Co., LLC" }, "ca").A);

console.log(failed ? `\n${failed} kiểm tra thất bại` : "\nTất cả kiểm tra đạt");
process.exit(failed ? 1 : 0);
