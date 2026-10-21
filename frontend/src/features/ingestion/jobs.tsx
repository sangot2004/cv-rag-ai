"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { ErrorNotice, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { dateTime, jobError, jobLabels, jobSchema, jobsSchema } from "./contracts";
export function Jobs({user, search}: {user: User; search: string}) {
  const params = new URLSearchParams(search), router = useRouter();
  const query = useQuery({queryKey: ["ingestion", user.user_id, "jobs", search], queryFn: async ({signal}) => jobsSchema.parse(await api(`/api/backend/ingestion/jobs?${search}`, {signal})), refetchInterval: 5000});
  function filter(event: FormEvent<HTMLFormElement>) {event.preventDefault(); const p = new URLSearchParams(); new FormData(event.currentTarget).forEach((v,k) => {if (String(v)) p.set(k,String(v));}); router.push(`/ingestion/jobs?${p}`);}
  function page(n: number) {const p = new URLSearchParams(search); p.set("page",String(n)); router.push(`/ingestion/jobs?${p}`);}
  const data = query.data;
  return <><div className="candidate-page-title"><div><p className="eyebrow">Tiếp nhận hồ sơ</p><h1>Theo dõi xử lý CV</h1><p className="muted">Tác vụ từ upload và email; cập nhật định kỳ khi bạn mở trang.</p></div><Link className="btn primary" href="/ingestion/upload">Upload CV</Link></div>
    <section className="candidate-card candidate-results"><form className="management-filter" aria-label="Bộ lọc tác vụ" onSubmit={filter}><label className="field"><span>Tìm tên file</span><input name="q" maxLength={200} defaultValue={params.get("q") || ""}/></label><label className="field"><span>Trạng thái xử lý</span><select aria-label="Trạng thái xử lý" name="status" defaultValue={params.get("status") || ""}><option value="">Tất cả trạng thái</option>{Object.entries(jobLabels).map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label><label className="field"><span>Nguồn tiếp nhận</span><select aria-label="Nguồn tiếp nhận" name="source_type" defaultValue={params.get("source_type") || ""}><option value="">Tất cả nguồn</option><option value="web_upload">Upload</option><option value="email">Email</option></select></label><button className="btn">Áp dụng</button><Link className="btn" href="/ingestion/jobs">Xóa bộ lọc</Link></form>
    {query.error && <><ErrorNotice error={query.error}/><button className="btn" onClick={() => query.refetch()}>Tải lại tác vụ</button></>}{query.isPending ? <Loading/> : data && <><div className="candidate-results-heading"><h2>{data.total} tác vụ</h2><button className="btn compact" onClick={() => query.refetch()}>Làm mới</button></div>{!data.items.length ? <p className="candidate-empty">Chưa có tác vụ phù hợp.</p> : <div className="candidate-table-wrap"><table className="candidate-table management-table"><thead><tr><th>Hồ sơ</th><th>Nguồn</th><th>Vị trí / Phòng ban</th><th>Trạng thái</th><th>Lần xử lý</th><th>Cập nhật</th></tr></thead><tbody>{data.items.map(job => <tr key={job.job_id}><td><Link href={`/ingestion/jobs/${job.job_id}`}><strong>{job.original_filename}</strong></Link>{job.candidate_name && <p className="small muted">{job.candidate_name}</p>}</td><td>{job.source_type === "email" ? "Email" : "Upload"}</td><td>{job.position_title || "Tự xác định từ CV"}<p className="muted small">{job.department_name}</p></td><td><span className={`badge ${job.status === "indexed" ? "success" : ""}`}>{jobLabels[job.status] || job.status}</span>{job.dispatch_error && <p className="field-error small">Chưa vào hàng đợi</p>}</td><td>{job.attempts}/{job.max_attempts}</td><td>{dateTime(job.updated_at)}</td></tr>)}</tbody></table></div>}<div className="candidate-pagination"><span>Trang {data.page} / {Math.max(1,Math.ceil(data.total/data.page_size))}</span><div><button className="btn compact" disabled={data.page <= 1} onClick={() => page(data.page-1)}>Trang trước</button><button className="btn compact" disabled={!data.has_next} onClick={() => page(data.page+1)}>Trang sau</button></div></div></>}
    </section></>;
}
export function JobDetail({user, jobId}: {user: User; jobId: string}) {
  const [error, setError] = useState<unknown>(null), [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const query = useQuery({queryKey: ["ingestion", user.user_id, "job", jobId], queryFn: async ({signal}) => jobSchema.parse(await api(`/api/backend/ingestion/jobs/${jobId}`, {signal})), refetchInterval: q => ["pending", "processing", "failed"].includes(q.state.data?.status || "") ? 2000 : false});
  const job = query.data;
  async function retry() {
    dialog.current?.close(); setBusy(true); setError(null); setNotice("");
    try {await api(`/api/backend/ingestion/jobs/${jobId}/retry`, {method: "POST", body: {confirmed: true}}); setNotice("Đã lưu yêu cầu xử lý lại. Theo dõi trạng thái hàng đợi bên dưới.");}
    catch (error) {setError(error);} finally {await query.refetch(); setBusy(false);}
  }
  return <><Link className="candidate-back" href="/ingestion/jobs">← Danh sách tác vụ</Link>{query.isPending ? <Loading/> : query.error && !job ? <><ErrorNotice error={query.error}/><button className="btn" onClick={() => query.refetch()}>Tải lại tác vụ</button></> : job && <>
    <div className="candidate-page-title"><div><p className="eyebrow">Chi tiết tiếp nhận</p><h1>{job.original_filename}</h1><p className="muted small">Mã tác vụ: {job.job_id}</p></div><span className={`badge ${job.status === "indexed" ? "success" : ""}`}>{jobLabels[job.status] || job.status}</span></div>
    {query.error && <ErrorNotice error={query.error}/>} {error != null && <ErrorNotice error={error}/>} {notice && <p className="notice" role="status">{notice}</p>}
    {job.dispatch_error && <p className="notice error" role="alert">{jobError(job.dispatch_error)}</p>}{job.error_code && <p className="notice" role="status">{jobError(job.error_code)}</p>}
    <section className="candidate-card"><h2>Thông tin xử lý</h2><dl className="job-facts"><dt>Nguồn</dt><dd>{job.source_type === "email" ? "Email" : "Upload"}</dd><dt>Vị trí tiếp nhận</dt><dd>{job.position_title || "Tự xác định từ nội dung CV"}</dd><dt>Phòng ban</dt><dd>{job.department_name || "Chưa xác định"}</dd><dt>Số lần xử lý trong lượt</dt><dd>{job.attempts} / {job.max_attempts}</dd><dt>Tiếp nhận lúc</dt><dd>{dateTime(job.created_at)}</dd><dt>Bắt đầu lần gần nhất</dt><dd>{dateTime(job.started_at)}</dd><dt>Cập nhật gần nhất</dt><dd>{dateTime(job.updated_at)}</dd></dl>
      <div className="management-actions"><button className="btn" onClick={() => query.refetch()}>Làm mới trạng thái</button>{job.can_retry && <button className="btn primary" disabled={busy || !!query.error} onClick={() => dialog.current?.showModal()}>{job.status === "processing" ? "Kiểm tra và khôi phục" : job.status === "pending" ? "Đưa lại vào hàng đợi" : "Thử xử lý lại"}</button>}{job.candidate_id && <Link className="btn primary" href={`/candidates/${job.candidate_id}`}>Mở hồ sơ ứng viên</Link>}</div>
      {job.status === "processing" && <p className="muted small">Hệ thống chỉ cho khôi phục khi không còn worker giữ tác vụ. Tác vụ đang chạy sẽ bị chặn thử lại.</p>}{job.status === "failed" && <p className="muted small">Worker sẽ tự thử lại theo thời gian chờ. Bạn có thể yêu cầu xử lý lại ngay nếu đã khắc phục dịch vụ phụ thuộc.</p>}{job.status === "rejected" && <p className="muted small">Không thử lại file đã bị từ chối. Kiểm tra và chỉnh nội dung CV trước khi upload bản khác.</p>}
    </section>
    <dialog ref={dialog} className="email-confirm" aria-labelledby="job-confirm-title"><h2 id="job-confirm-title">Xác nhận xử lý lại CV?</h2><p>File: <strong>{job.original_filename}</strong>. Hệ thống dùng lại tác vụ này; quá trình xử lý có thể gọi AI và tiêu thụ token.</p><div className="interview-confirm-actions"><button className="btn" onClick={() => dialog.current?.close()}>Hủy</button><button className="btn primary" onClick={retry}>Xác nhận</button></div></dialog>
  </>}</>;
}
