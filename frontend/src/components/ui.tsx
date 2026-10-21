import { FileSearch, LoaderCircle } from "lucide-react";
import { ApiError } from "@/lib/api";
import { ZodError } from "zod";

export function Brand() {
  return <div className="brand"><span className="brand-mark"><FileSearch size={23}/></span><span><strong>CV RAG AI</strong><small>Trợ lý tuyển dụng</small></span></div>;
}
export function Loading({text = "Đang tải…"}: {text?: string}) {
  return <div className="notice" role="status"><LoaderCircle className="loading-icon" size={18}/><span>{text}</span></div>;
}
export function ErrorNotice({error}: {error: unknown}) {
  const message = error instanceof ZodError
    ? "Dữ liệu phản hồi từ máy chủ chưa đúng định dạng. Vui lòng tải lại hoặc liên hệ quản trị viên."
    : error instanceof Error ? error.message : "Đã xảy ra lỗi. Vui lòng thử lại.";
  return <div className="notice error" role="alert"><div><strong>{message}</strong>{error instanceof ApiError && error.requestId && <p className="request-reference">Mã hỗ trợ: <code>{error.requestId}</code></p>}</div></div>;
}
