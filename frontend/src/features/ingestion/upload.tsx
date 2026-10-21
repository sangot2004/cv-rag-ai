"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileUp, UploadCloud, X } from "lucide-react";
import { api, ApiError, leaveSession } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { ErrorNotice, Loading } from "@/components/ui";
import { useDepartments, usePostings } from "@/features/management/catalog";
import { capabilitiesSchema, jobSchema, type Job } from "./contracts";

type FileRow = {id: string; file: File; state: "ready" | "uploading" | "accepted" | "error"; progress: number; job?: Job; error?: string};
function mb(bytes: number) {return `${(bytes / 1024 / 1024).toLocaleString("vi-VN", {maximumFractionDigits: 2})} MB`;}
export function UploadCVs({user}: {user: User}) {
  const [rows, setRows] = useState<FileRow[]>([]), [department, setDepartment] = useState(""), [posting, setPosting] = useState("");
  const [error, setError] = useState<unknown>(null), [busy, setBusy] = useState(false), [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null), active = useRef<XMLHttpRequest | null>(null), cancelled = useRef(false);
  useEffect(() => {cancelled.current = false; return () => {cancelled.current = true; active.current?.abort();};}, []);
  const departments = useDepartments(user.user_id), postings = usePostings(user.user_id);
  const capabilities = useQuery({queryKey: ["ingestion", user.user_id, "capabilities"], queryFn: async ({signal}) => capabilitiesSchema.parse(await api("/api/backend/ingestion/capabilities", {signal}))});
  const config = capabilities.data;
  function add(files: FileList | File[]) {
    if (!config || busy) return;
    if (rows.length + files.length > 10) {setError(new Error("Chọn tối đa 10 file trong một lượt.")); return;}
    const next: FileRow[] = Array.from(files).map(file => {
      const reason = !file.name.toLowerCase().endsWith(".pdf") ? "Chỉ tiếp nhận file PDF." : file.size < config.min_bytes ? "File nhỏ hơn dung lượng tối thiểu." : file.size > config.max_bytes ? "File vượt quá dung lượng cho phép." : undefined;
      return {id: crypto.randomUUID(), file, state: reason ? "error" : "ready", progress: 0, error: reason};
    });
    setError(null); setRows(previous => [...previous, ...next]);
    if (input.current) input.current.value = "";
  }
  function patch(id: string, update: Partial<FileRow>) {setRows(previous => previous.map(row => row.id === id ? {...row, ...update} : row));}
  function send(row: FileRow): Promise<Job> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); active.current = xhr;
      xhr.open("POST", "/api/backend/ingestion/uploads"); xhr.timeout = 150000;
      xhr.upload.onprogress = event => {if (event.lengthComputable) patch(row.id, {progress: Math.round(event.loaded / event.total * 100)});};
      xhr.onload = () => {
        let result; try {result = JSON.parse(xhr.responseText);} catch {reject(new Error("Phản hồi chưa hợp lệ. Kiểm tra danh sách tác vụ trước khi upload lại.")); return;}
        if (xhr.status === 401) leaveSession("expired");
        if (xhr.status < 200 || xhr.status >= 300) {reject(new ApiError(xhr.status, result?.error?.code || "UPLOAD_FAILED", result?.error?.message || "Upload chưa thành công.", result?.error?.request_id)); return;}
        const parsed = jobSchema.safeParse(result); if (parsed.success) resolve(parsed.data); else reject(new Error("Chưa đọc được kết quả. Hãy kiểm tra danh sách tác vụ."));
      };
      xhr.onerror = xhr.ontimeout = () => reject(new Error("Mất kết nối hoặc quá thời gian chờ. File có thể đã được nhận; hãy kiểm tra danh sách tác vụ trước khi gửi lại."));
      xhr.onabort = () => reject(new Error("Đã dừng chờ upload. Hãy kiểm tra danh sách tác vụ."));
      const form = new FormData(); form.append("file", row.file); form.append("posting_id", posting); xhr.send(form);
    });
  }
  async function upload() {
    if (busy || !posting) return;
    setBusy(true); setError(null);
    for (const row of rows.filter(row => row.state === "ready")) {
      if (cancelled.current) break;
      patch(row.id, {state: "uploading", progress: 0});
      try {const job = await send(row); if (!cancelled.current) patch(row.id, {state: "accepted", job, progress: 100});}
      catch (error) {if (!cancelled.current) patch(row.id, {state: "error", error: error instanceof Error ? error.message : "Upload chưa thành công."});}
    }
    active.current = null; if (!cancelled.current) setBusy(false);
  }
  const dependencyError = capabilities.error || departments.error || postings.error;
  return <>
    <div className="candidate-page-title"><div><p className="eyebrow">Tiếp nhận hồ sơ</p><h1>Upload CV</h1><p className="muted">Chọn vị trí tuyển dụng và gửi hồ sơ vào hệ thống.</p></div><FileUp size={30}/></div>
    {dependencyError ? <><ErrorNotice error={dependencyError}/><button className="btn" onClick={() => {void capabilities.refetch(); void departments.refetch(); void postings.refetch();}}>Tải lại cấu hình</button></> : !config || departments.isPending || postings.isPending ? <Loading/> : <>
      <section className="candidate-card"><h2>Vị trí tiếp nhận</h2><div className="management-create"><label className="field"><span>Phòng ban tiếp nhận</span><select aria-label="Phòng ban tiếp nhận" value={department} disabled={busy} onChange={e => {setDepartment(e.target.value); setPosting("");}}><option value="">Chọn phòng ban</option>{departments.data?.map(d => <option key={d.department_id} value={d.department_id}>{d.department_name}</option>)}</select></label><label className="field"><span>Vị trí tiếp nhận</span><select aria-label="Vị trí tiếp nhận" value={posting} disabled={busy || !department} onChange={e => setPosting(e.target.value)}><option value="">Chọn vị trí tuyển dụng</option>{postings.data?.filter(p => p.department_id === department).map(p => <option value={p.posting_id} key={p.posting_id}>{p.position_title}</option>)}</select></label></div><p className="muted small">CV sẽ thuộc phòng ban của vị trí đã chọn. Tester chỉ tra cứu được CV thuộc phòng ban được cấp.</p>{!postings.data?.length && <p className="notice">Chưa có vị trí đang tuyển. <Link href="/admin/postings">Tạo vị trí tuyển dụng</Link></p>}</section>
      <section className="candidate-card"><h2>Chọn hồ sơ PDF</h2><div className={`upload-drop ${dragging ? "dragging" : ""}`} onDragOver={e => {e.preventDefault(); if (!busy) setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={e => {e.preventDefault(); setDragging(false); add(e.dataTransfer.files);}}><UploadCloud size={40}/><p>Kéo thả CV vào đây</p><button className="btn" disabled={busy} onClick={() => input.current?.click()}>Chọn file PDF</button><input ref={input} className="sr-only" type="file" accept="application/pdf,.pdf" multiple aria-label="File CV" disabled={busy} onChange={e => {if (e.target.files) add(e.target.files);}}/><p className="muted small">PDF · {Math.ceil(config.min_bytes/1024)} KB–{mb(config.max_bytes)} · tối đa {config.max_pages} trang/file · 10 file/lượt.</p><p className="muted small">Tên file mẫu: <code>{config.filename_example}</code></p></div>
        {error != null && <ErrorNotice error={error}/>}
        {!!rows.length && <div className="upload-files">{rows.map(row => <article className="upload-file" key={row.id} aria-label={`File ${row.file.name}`}><div><strong>{row.file.name}</strong><p className="muted small">{mb(row.file.size)}</p>{row.state === "uploading" && <><progress max="100" value={row.progress} aria-label={`Tiến độ upload ${row.file.name}`}/><p className="small" role="status">{row.progress === 100 ? "Đang kiểm tra và lưu file…" : `Đang tải lên: ${row.progress}%`}</p></>}{row.state === "accepted" && <p className="small success-text">{row.job?.status === "indexed" ? "CV đã được xử lý trước đó." : "Đã tiếp nhận file. Xem tác vụ để biết kết quả xử lý."} <Link href={`/ingestion/jobs/${row.job?.job_id}`}>Xem tác vụ</Link></p>}{row.error && <p role="alert" className="field-error">{row.error}</p>}</div>{row.state !== "uploading" && <button className="icon-button" disabled={busy} aria-label={`Bỏ file ${row.file.name}`} onClick={() => setRows(previous => previous.filter(x => x.id !== row.id))}><X size={18}/></button>}</article>)}</div>}
        <div className="management-actions"><button className="btn primary" disabled={busy || !posting || !rows.some(row => row.state === "ready")} onClick={upload}>{busy ? "Đang tiếp nhận…" : `Upload ${rows.filter(row => row.state === "ready").length} CV`}</button><Link className="btn" href="/ingestion/jobs">Theo dõi xử lý</Link></div><p className="muted small">Sau khi nhận file, worker sẽ trích xuất và lập chỉ mục. Tải lại trang không làm mất tác vụ đã lưu.</p>
      </section>
    </>}
  </>;
}
