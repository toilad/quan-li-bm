import { Topbar } from "@/components/shell/topbar";
import { PdfManager } from "@/components/pdf/pdf-manager";

export default function PdfPage() {
  return (
    <>
      <Topbar
        title="PDF Manager"
        subtitle="Tải PDF gốc → kiểm tra dữ liệu trích xuất → ghi Google Sheet (A, D–J) + lưu bản gốc lên Drive (K). B, C luôn để trống."
      />
      <PdfManager />
    </>
  );
}
