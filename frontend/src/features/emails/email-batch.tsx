"use client";
import Link from "next/link";
import { useRef, useState, type ReactNode, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, RefreshCw, Save, Send, Sparkles } from "lucide-react";
import { AdminWorkspace } from "@/components/admin-workspace";
import { ErrorNotice, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { batchSchema, errorNames, statusNames, type Batch, type Draft } from "./contracts";

export function EmailBatch({user, batchId}: {user: User; batchId: string}) {
  const client = useQueryClient(); const key = ["emails", user.user_id, "batch", batchId];
  const query = useQuery({queryKey: key, queryFn: async ({signal}) => batchSchema.parse(await api(`/api/backend/emails/batches/${batchId}`, {signal})), refetchOnWindowFocus: "always", refetchInterval: q => q.state.data && (["queued", "sending"].includes(q.state.data.status) || q.state.data.drafts.some(d => d.is_generating)) ? 2000 : false});
  return <AdminWorkspace user={user} mainId="email-main" active={query.data?.kind === "bulk" ? "bulk" : "compose"} title="Soạn, duyệt và theo dõi thư mời">
    {query.data ? <>{query.error && <ErrorNotice error={query.error}/>}<BatchEditor user={user} batch={query.data} refreshing={query.isFetching || !!query.error} refresh={async () => {await query.refetch();}} update={batch => client.setQueryData(key, batch)}/></> : query.isPending ? <Loading/> : <><ErrorNotice error={query.error}/><button className="btn" onClick={() => query.refetch()}>Thử tải lại</button></>}
  </AdminWorkspace>;
}
function BatchEditor({batch, refreshing, refresh, update}: {user: User; batch: Batch; refreshing: boolean; refresh: () => Promise<void>; update: (b: Batch) => void}) {
  const [busy, setBusy] = useState(false); const busyRef = useRef(false);
  const [selected, setSelected] = useState<string[]>([]); const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [allowPrevious, setAllowPrevious] = useState(false);
  const [error, setError] = useState<unknown>(null); const [notice, setNotice] = useState("");
  const [confirmation, setConfirmation] = useState<{title: string; detail: ReactNode; run: () => void} | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const draftMode = batch.status === "draft";
  const generating = batch.drafts.some(d => d.is_generating);
  const locked = busy || refreshing || generating;
  const approved = batch.drafts.filter(d => d.ready && !dirty[d.draft_id] && (batch.kind === "single" || selected.includes(d.draft_id)));
  const prior = approved.some(d => d.previously_sent);
  function ask(title: string, detail: ReactNode, run: () => void) {setConfirmation({title, detail, run}); dialog.current?.showModal();}
  async function action(path: string, body: unknown, message: string, draftId?: string) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null); setNotice("");
    try {
      update(batchSchema.parse(await api(`/api/backend/emails/${path}`, {method: "POST", body})));
      if (draftId) setDirty(old => ({...old, [draftId]: false}));
      setNotice(message);
    } catch (error) {setError(error); await refresh();}
    finally {busyRef.current = false; setBusy(false);}
  }
  async function generateMissing() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null); setNotice("");
    let succeeded = 0, failed = 0;
    try {
      for (const draft of batch.drafts.filter(d => (!d.subject || !d.body) && !dirty[d.draft_id])) {
        try {
          update(batchSchema.parse(await api(`/api/backend/emails/drafts/${draft.draft_id}/generate`, {method: "POST", body: {expected_revision: draft.revision}})));
          succeeded++;
        } catch {failed++;}
      }
      setNotice(`Đã tạo ${succeeded} nháp${failed ? `; ${failed} nháp chưa tạo được, hãy kiểm tra từng người nhận` : ""}. Chưa có email nào được gửi.`);
    } finally {await refresh(); busyRef.current = false; setBusy(false);}
  }
  function dispatch() {
    const payload = {confirmed: true, allow_previous: allowPrevious, drafts: approved.map(d => ({draft_id: d.draft_id, revision: d.revision}))};
    ask(`Xác nhận gửi ${approved.length} thư mời?`, <><p>Gửi đúng nội dung đã lưu đến các địa chỉ sau:</p><ul className="email-approval-list">{approved.map(d => <li key={d.draft_id}><strong>{d.full_name}</strong><span>{d.recipient_email}</span><small>{d.subject}</small></li>)}</ul>{prior && <p className="email-warning">Bạn đã xác nhận gửi thêm cho người từng nhận thư.</p>}</>, () => void action(`batches/${batch.batch_id}/dispatch`, payload, "Đã lưu duyệt gửi. Theo dõi kết quả từng thư bên dưới."));
  }
  return <>
    <div className="candidate-page-title"><div><p className="eyebrow">{draftMode ? "Soạn và duyệt" : "Tiến độ gửi thư"}</p><h1>{batch.name}</h1><p className="muted">{batch.position} · {batch.kind === "single" ? "Một ứng viên" : "Hàng loạt"}</p></div><span className="badge">{statusNames[batch.status] || batch.status}</span></div>
    <div className="email-tabs"><Link className="btn" href="/emails/batches">Đợt gửi & bản nháp</Link><Link className="btn" href="/emails/history">Lịch sử gửi thư</Link><button className="btn" disabled={busy || refreshing} onClick={() => refresh()}><RefreshCw size={16}/>Tải lại trạng thái</button></div>
    <details className="candidate-card"><summary>Thông tin phỏng vấn đã dùng để soạn</summary><p className="profile-text">{batch.interview_details}</p></details>
    {error != null && <ErrorNotice error={error}/>}{notice && <div className="notice" role="status">{notice}</div>}
    {(busy || generating) && <Loading text="Đang xử lý yêu cầu…"/>}
    {draftMode ? <>
      <div className="candidate-card email-review-toolbar"><div><h2>{batch.drafts.length} bản nháp</h2><p className="muted small">Lưu nội dung rồi kiểm tra người nhận trước khi duyệt. Bản nháp không tự gửi.</p></div><button className="btn" disabled={locked || !batch.drafts.some(d => (!d.subject || !d.body) && !dirty[d.draft_id])} onClick={generateMissing}><Sparkles size={16}/>Tạo nháp AI còn thiếu</button>
        {batch.kind === "bulk" && <button className="btn" disabled={locked} onClick={() => setSelected(batch.drafts.filter(d => d.ready && !dirty[d.draft_id]).map(d => d.draft_id))}>Chọn tất cả nháp hợp lệ đã lưu</button>}
      </div>
      <div className="email-draft-list">{batch.drafts.map(draft => <DraftCard key={`${draft.draft_id}:${draft.revision}`} draft={draft} disabled={locked} multi={batch.kind === "bulk"} selected={selected.includes(draft.draft_id)} select={() => setSelected(old => old.includes(draft.draft_id) ? old.filter(id => id !== draft.draft_id) : [...old, draft.draft_id])} markDirty={value => setDirty(old => ({...old, [draft.draft_id]: value}))}
        save={(subject, body) => void action(`drafts/${draft.draft_id}`, {expected_revision: draft.revision, subject, body}, "Đã lưu bản nháp.", draft.draft_id)}
        generate={needsConfirm => {const run = () => void action(`drafts/${draft.draft_id}/generate`, {expected_revision: draft.revision}, "Đã tạo và lưu nháp AI.", draft.draft_id); if (needsConfirm) ask("Tạo lại nội dung nháp?", <p>Nội dung đang sửa sẽ được thay khi AI tạo thành công. Nếu lỗi, bản đã lưu vẫn được giữ.</p>, run); else run();}}/> )}</div>
      {prior && <label className="email-acknowledge"><input type="checkbox" checked={allowPrevious} onChange={e => setAllowPrevious(e.target.checked)}/>Tôi xác nhận gửi thêm cho những người đã từng nhận thư mời.</label>}
      <div className="candidate-card email-send-bar"><span>Đã duyệt chọn: <strong>{approved.length}</strong> / {batch.drafts.length}</span><button className="btn primary" disabled={locked || !approved.length || (prior && !allowPrevious) || approved.some(d => dirty[d.draft_id])} onClick={dispatch}><Send size={17}/>{batch.kind === "single" ? "Xem lại & xác nhận gửi" : `Duyệt & gửi ${approved.length} thư`}</button></div>
    </> : <>
      {batch.dispatch_error && <div className="notice">{errorNames[batch.dispatch_error] || "Hàng đợi cần kiểm tra."}</div>}
      {batch.counts.queued > 0 && <div className="notice email-queue-note"><p>Thư đã được duyệt và đang chờ worker xử lý. Nếu chưa chạy, hãy kiểm tra Celery worker và Redis.</p><button className="btn compact" disabled={locked} onClick={() => action(`batches/${batch.batch_id}/requeue`, {confirmed: true}, "Đã yêu cầu đưa lại các thư chưa xử lý vào hàng đợi.")}>Đưa lại vào hàng đợi</button></div>}
      <div className="email-metrics">{["queued", "sending", "success", "failed", "unknown"].map(s => <div className="candidate-card" key={s}><span className="muted small">{statusNames[s]}</span><strong>{batch.counts[s] || 0}</strong></div>)}</div>
      <section className="candidate-card email-deliveries"><h2>Kết quả từng người nhận · {batch.total} thư đã duyệt</h2>{batch.deliveries.map(d => <article key={d.delivery_id} className="email-delivery"><div><Link href={`/candidates/${d.candidate_id}`}>{d.full_name}</Link><p className="small">{d.recipient_email}</p><p className="small muted">{d.subject}</p>{d.error_code && <p className="email-warning small">{errorNames[d.error_code] || "Cần kiểm tra dịch vụ gửi thư."}</p>}</div><span className={`badge ${d.status === "success" ? "success" : d.status === "failed" ? "error" : ""}`}>{statusNames[d.status]}</span>
        {d.status === "failed" && <button className="btn compact" disabled={locked} onClick={() => ask("Xác nhận thử gửi lại?", <p>Gửi lại thư đã bị từ chối trước đó tới {d.recipient_email}. Nội dung giữ nguyên như lần duyệt.</p>, () => void action(`deliveries/${d.delivery_id}/retry`, {confirmed: true, allow_previous: allowPrevious}, "Đã đưa thư thất bại vào hàng đợi."))}>Thử gửi lại</button>}
        {d.status === "unknown" && <button className="btn compact" disabled={locked} onClick={() => action(`deliveries/${d.delivery_id}/reconcile`, {confirmed: true}, "Đã kiểm tra Gmail. Xem trạng thái cập nhật; thư chưa rõ kết quả không được tự gửi lại.")}>Kiểm tra Gmail</button>}
      </article>)}</section>
      {batch.drafts.some(d => d.previously_sent) && batch.counts.failed > 0 && <label className="email-acknowledge"><input type="checkbox" checked={allowPrevious} onChange={e => setAllowPrevious(e.target.checked)}/>Tôi xác nhận gửi thêm nếu người nhận đã từng có thư thành công.</label>}
    </>}
    <dialog className="email-confirm" ref={dialog} aria-labelledby="email-confirm-title"><h2 id="email-confirm-title">{confirmation?.title}</h2><div>{confirmation?.detail}</div><div className="interview-confirm-actions"><button className="btn" onClick={() => dialog.current?.close()}>Hủy</button><button className="btn primary" onClick={() => {dialog.current?.close(); confirmation?.run();}}>Xác nhận</button></div></dialog>
  </>;
}
function DraftCard({draft, disabled, multi, selected, select, markDirty, save, generate}: {draft: Draft; disabled: boolean; multi: boolean; selected: boolean; select: () => void; markDirty: (dirty: boolean) => void; save: (subject: string, body: string) => void; generate: (confirm: boolean) => void}) {
  const [subject, setSubject] = useState(draft.subject), [body, setBody] = useState(draft.body), [preview, setPreview] = useState(false);
  const dirty = subject !== draft.subject || body !== draft.body;
  function change(nextSubject: string, nextBody: string) {setSubject(nextSubject); setBody(nextBody); markDirty(nextSubject !== draft.subject || nextBody !== draft.body);}
  function submit(event: FormEvent<HTMLFormElement>) {event.preventDefault(); save(subject, body);}
  return <article className="candidate-card email-draft" aria-label={`Nháp ${draft.full_name}`}><header className="interview-row"><div><h2>{draft.full_name}</h2><p className="muted small">Người nhận: {draft.recipient_email || "Chưa có email"}</p></div>{multi && <label className="email-check"><input type="checkbox" aria-label={`Duyệt ${draft.full_name}`} disabled={disabled || !draft.ready || dirty} checked={selected} onChange={select}/>Duyệt gửi</label>}</header>
    {draft.previously_sent && <p className="email-warning small">Địa chỉ/ứng viên này đã từng được gửi thư mời.</p>}
    {draft.error_code && <p className="email-warning small">{errorNames[draft.error_code] || "Nháp cần kiểm tra."}</p>}
    {dirty && <span className="badge pending">Chưa lưu thay đổi</span>}
    <div className="email-tabs"><button className={`btn compact ${!preview ? "primary" : ""}`} onClick={() => setPreview(false)}>Chỉnh sửa</button><button className={`btn compact ${preview ? "primary" : ""}`} onClick={() => setPreview(true)}><Eye size={15}/>Xem trước</button><button className="btn compact" disabled={disabled} onClick={() => generate(dirty || !!draft.body || !!draft.subject)}><Sparkles size={15}/>Tạo nháp AI</button></div>
    {preview ? <div className="email-preview"><p className="small muted">Đến: {draft.recipient_email || "Chưa có email"}{dirty && " · Nội dung chưa lưu"}</p><h3>{subject || "Chưa có tiêu đề"}</h3><p className="profile-text">{body || "Chưa có nội dung"}</p></div> : <form onSubmit={submit} className="email-draft-form"><label className="field"><span>Tiêu đề thư</span><input required maxLength={500} value={subject} disabled={disabled} onChange={e => change(e.target.value, body)}/></label><label className="field"><span>Nội dung thư</span><textarea aria-label="Nội dung thư" required maxLength={15000} value={body} disabled={disabled} onChange={e => change(subject, e.target.value)}/></label><button className="btn" type="submit" disabled={disabled || !dirty || !subject.trim() || !body.trim()}><Save size={16}/>Lưu bản nháp</button></form>}
  </article>;
}
