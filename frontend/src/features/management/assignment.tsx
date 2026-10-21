"use client";
import { useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ErrorNotice } from "@/components/ui";
import { usePostings } from "./catalog";
export function CandidateAssignment({userId, candidateId, postingId}: {userId: string; candidateId: string; postingId: string | null}) {
  const postings = usePostings(userId), client = useQueryClient(), dialog = useRef<HTMLDialogElement>(null);
  const [value, setValue] = useState(postingId || ""), [error, setError] = useState<unknown>(null), [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  function confirm(event: FormEvent) {event.preventDefault(); dialog.current?.showModal();}
  async function assign() {
    dialog.current?.close(); setBusy(true); setError(null); setNotice("");
    try {
      await api(`/api/backend/candidates/${candidateId}/posting`, {method: "POST", body: {posting_id: value || null, expected_posting_id: postingId}});
      await Promise.all([client.invalidateQueries({queryKey: ["candidate", userId, candidateId]}), client.invalidateQueries({queryKey: ["candidates", userId]}), client.invalidateQueries({queryKey: ["management", userId]})]);
      setNotice("Đã cập nhật vị trí tuyển dụng.");
    } catch (error) {setError(error); await client.invalidateQueries({queryKey: ["candidate", userId, candidateId]});} finally {setBusy(false);}
  }
  return <div className="candidate-assignment"><form onSubmit={confirm}><label className="field"><span>Gán vị trí tuyển dụng</span><select aria-label="Gán vị trí tuyển dụng" value={value} disabled={busy || postings.isPending || !!postings.error} onChange={e => setValue(e.target.value)}><option value="">Chưa gắn vị trí</option>{postings.data?.map(p => <option key={p.posting_id} value={p.posting_id}>{p.department_name} · {p.position_title}</option>)}</select></label><button className="btn compact" disabled={busy || postings.isPending || !!postings.error || value === (postingId || "")}>Lưu vị trí</button></form>
    {error != null && <ErrorNotice error={error}/>} {postings.error && <><ErrorNotice error={postings.error}/><button className="btn compact" onClick={() => postings.refetch()}>Tải lại vị trí</button></>}{notice && <p className="small" role="status">{notice}</p>}
    <dialog ref={dialog} className="email-confirm" aria-labelledby="assignment-title"><h2 id="assignment-title">Thay đổi vị trí tuyển dụng?</h2><p>{value ? `Vị trí mới: ${postings.data?.find(p => p.posting_id === value)?.department_name} · ${postings.data?.find(p => p.posting_id === value)?.position_title}.` : "Ứng viên sẽ chưa được gắn vị trí tuyển dụng."} Phạm vi CV mà tester tra cứu được sẽ thay đổi theo phòng ban mới.</p><div className="interview-confirm-actions"><button type="button" className="btn" onClick={() => dialog.current?.close()}>Hủy</button><button type="button" className="btn primary" onClick={assign}>Xác nhận</button></div></dialog>
  </div>;
}
