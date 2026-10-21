"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, ListChecks, RefreshCw, Search, Sparkles, Trash2, X } from "lucide-react";
import { AdminWorkspace } from "@/components/admin-workspace";
import { Brand, ErrorNotice, Loading } from "@/components/ui";
import { SessionGate } from "@/features/auth/session-gate";
import { CandidatePortrait } from "@/features/candidates/candidate-portrait";
import { candidateDetailSchema, candidateListSchema } from "@/features/candidates/contracts";
import { api } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { categoryLabels, interviewSetSchema } from "./contracts";

type Props = {candidateId?: string; listSearch: string};
export function InterviewsApp(props: Props) {
  return <SessionGate>{user => user.role === "admin" ? <AdminWorkspace key={user.user_id} user={user} active="interviews" mainId="interview-main" title="Chuẩn bị phỏng vấn"><InterviewPage key={props.candidateId || "picker"} user={user} {...props}/></AdminWorkspace>
    : <main className="login-page"><section className="login-card"><Brand/><h1>Bạn chưa có quyền truy cập</h1><p>Chức năng câu hỏi phỏng vấn dành cho quản trị viên.</p><Link className="btn primary" href="/chat">Trở về hội thoại</Link></section></main>}</SessionGate>;
}
function CandidatePicker({user, close}: {user: User; close?: () => void}) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({page: String(page), page_size: "10"});
  if (search) params.set("q", search);
  const query = useQuery({queryKey: ["candidates", user.user_id, "interview-picker", search, page], queryFn: async ({signal}) => candidateListSchema.parse(await api(`/api/backend/candidates?${params}`, {signal}))});
  function submit(event: FormEvent<HTMLFormElement>) {event.preventDefault(); setPage(1); setSearch(String(new FormData(event.currentTarget).get("q") || "").trim());}
  return <section className="candidate-card interview-picker" aria-label="Chọn ứng viên"><div className="interview-row"><h2>Chọn ứng viên</h2>{close && <button className="icon-button" aria-label="Đóng chọn ứng viên" onClick={close}><X size={18}/></button>}</div>
    <form onSubmit={submit} className="interview-picker-search"><label className="field"><span>Tên hoặc email ứng viên</span><input name="q" maxLength={200} placeholder="Tìm ứng viên…"/></label><button className="btn" type="submit"><Search size={17}/>Tìm</button></form>
    {query.isPending ? <Loading/> : query.error ? <><ErrorNotice error={query.error}/><button className="btn" onClick={() => query.refetch()}>Thử tải lại</button></> : query.data && <>
      <div className="interview-picker-list">{query.data.items.map(c => <button className="interview-picker-item" key={c.candidate_id} onClick={() => {router.push(`/interviews?candidate=${c.candidate_id}`); close?.();}}><strong>{c.full_name}</strong><span className="muted small">{c.applied_position || "Chưa có vị trí"} · {c.email || "Chưa có email"}</span></button>)}{!query.data.items.length && <p className="muted">Không tìm thấy ứng viên.</p>}</div>
      <div className="candidate-pagination"><span className="small">Trang {query.data.page} / {Math.max(query.data.total_pages, 1)}</span><div><button className="btn compact" disabled={page <= 1} onClick={() => setPage(n => n - 1)}>Trước</button><button className="btn compact" disabled={!query.data.has_next} onClick={() => setPage(n => n + 1)}>Sau</button></div></div>
    </>}
  </section>;
}
function InterviewPage({user, candidateId, listSearch}: Props & {user: User}) {
  const client = useQueryClient();
  const [selecting, setSelecting] = useState(false);
  const [count, setCount] = useState("8");
  const [category, setCategory] = useState("all");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const [confirmation, setConfirmation] = useState<{kind: "generate" | "delete"; revision: string; count: number} | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const profile = useQuery({queryKey: ["candidate", user.user_id, candidateId], enabled: !!candidateId, queryFn: async ({signal}) => candidateDetailSchema.parse(await api(`/api/backend/candidates/${candidateId}`, {signal}))});
  const setKey = ["interviews", user.user_id, candidateId];
  const query = useQuery({queryKey: setKey, enabled: !!candidateId && !!profile.data && !profile.error, queryFn: async ({signal}) => interviewSetSchema.parse(await api(`/api/backend/candidates/${candidateId}/interview-questions`, {signal})), refetchOnWindowFocus: "always", refetchInterval: q => q.state.data?.is_generating ? 2000 : false});
  const state = query.data, candidate = profile.data;
  const locked = busy || !!state?.is_generating || query.isFetching || !!query.error;
  const number = Number(count), validCount = Number.isInteger(number) && number >= 3 && number <= 15;
  async function mutate(kind: "generate" | "delete", revision: string, maxQuestions: number, replaceExisting: boolean) {
    if (busyRef.current || !candidateId) return;
    busyRef.current = true; setBusy(true); setError(null); setNotice("");
    try {
      const path = `/api/backend/candidates/${candidateId}/interview-questions`;
      const result = interviewSetSchema.parse(await api(kind === "generate" ? `${path}/generate` : `${path}?expected_revision=${revision}`, kind === "generate"
        ? {method: "POST", body: {max_questions: maxQuestions, expected_revision: revision, replace_existing: replaceExisting}}
        : {method: "DELETE"}));
      client.setQueryData(setKey, result); setCategory("all");
      setNotice(kind === "delete" ? "Đã xóa bộ câu hỏi." : `Đã lưu ${result.items.length} câu hỏi có trích dẫn từ CV.`);
    } catch (error) {
      setError(error);
      await query.refetch(); // Read saved state after uncertain responses; never auto-submit again.
    } finally {setBusy(false); busyRef.current = false;}
  }
  function requestMutation(kind: "generate" | "delete") {
    if (!state || locked || (kind === "generate" && !validCount)) return;
    if (kind === "delete" || state.items.length) {
      setConfirmation({kind, revision: state.revision, count: number}); dialog.current?.showModal();
    } else void mutate(kind, state.revision, number, false);
  }
  async function copy(text: string) {
    try {await navigator.clipboard.writeText(text); setNotice("Đã sao chép câu hỏi.");}
    catch {setNotice("Chưa sao chép được. Bạn có thể chọn và sao chép nội dung câu hỏi.");}
  }
  return <>
    <div className="candidate-page-title"><div><p className="eyebrow">Chuẩn bị phỏng vấn</p><h1>Câu hỏi phỏng vấn</h1><p className="muted">Sinh câu hỏi từ nội dung CV, kèm trích dẫn để kiểm tra.</p></div><span className="candidate-title-icon"><ListChecks size={26}/></span></div>
    {!candidateId ? <CandidatePicker user={user}/> : profile.isPending ? <Loading text="Đang tải ứng viên…"/> : profile.error ? <><ErrorNotice error={profile.error}/><Link href="/interviews" className="btn">Chọn ứng viên khác</Link></> : candidate && <>
      <div className="interview-page-actions"><Link className="btn" href={`/candidates/${candidateId}${listSearch ? `?${listSearch}` : ""}`}>Xem hồ sơ ứng viên</Link><Link className="btn" href={`/emails/compose?candidate=${candidateId}`}>Soạn thư mời</Link><button className="btn" disabled={locked} onClick={() => query.refetch()}><RefreshCw size={16}/>Tải lại bộ đã lưu</button><button className="btn" disabled={locked || !state?.items.length} onClick={() => requestMutation("delete")}><Trash2 size={16}/>Xóa toàn bộ</button></div>
      {selecting && <CandidatePicker user={user} close={() => setSelecting(false)}/>}
      <div className="interview-grid"><aside className="interview-settings">
        <section className="candidate-card"><div className="interview-row"><h2>Ứng viên đã chọn</h2><button className="btn compact" disabled={busy || state?.is_generating} onClick={() => setSelecting(true)}>Đổi ứng viên</button></div>
          {candidate.has_photo && <CandidatePortrait candidateId={candidate.candidate_id} name={candidate.full_name}/>}
          <h3 className="interview-candidate-name">{candidate.full_name}</h3><p className="muted">{candidate.applied_position || "Chưa có vị trí ứng tuyển"}</p><p className="muted small">{candidate.email || "Chưa có email"}</p>
        </section>
        <section className="candidate-card interview-settings-form"><h2>Cấu hình bộ câu hỏi</h2><label className="field"><span>Số câu hỏi</span><input aria-label="Số câu hỏi" type="number" min={3} max={15} step={1} value={count} disabled={busy || state?.is_generating} onChange={e => setCount(e.target.value)}/><small>Yêu cầu từ 3 đến 15 câu.</small></label>
          {!validCount && <p className="field-error" role="alert">Nhập số nguyên từ 3 đến 15.</p>}
          <p className="muted small">Chỉ lưu câu hỏi có trích dẫn khớp CV. Số câu thực tế có thể ít hơn yêu cầu.</p>
          {state && !state.has_cv && <div className="notice">Ứng viên chưa có nội dung CV để sinh câu hỏi.</div>}
          <button className="btn primary full" disabled={locked || !state?.has_cv || !validCount} onClick={() => requestMutation("generate")}><Sparkles size={17}/>{busy || state?.is_generating ? "Đang xử lý…" : state?.items.length ? "Sinh lại bộ câu hỏi" : "Sinh bộ câu hỏi"}</button>
          {!!state?.items.length && <p className="muted small">Sinh lại sẽ thay bộ đang lưu sau khi có kết quả hợp lệ.</p>}
        </section>
      </aside><div className="interview-results">
        {error != null && <ErrorNotice error={error}/>}{notice && <div className="notice success" role="status">{notice}</div>}
        {(busy || state?.is_generating) && <Loading text="Đang xử lý bộ câu hỏi. Có thể mất một lúc…"/>}
        {query.isPending ? <Loading text="Đang tải bộ câu hỏi đã lưu…"/> : query.error ? <><ErrorNotice error={query.error}/><button className="btn" onClick={() => query.refetch()}>Thử tải lại</button></> : state && <>
          <div className="interview-tabs" role="group" aria-label="Lọc nhóm câu hỏi">{["all", ...Object.keys(categoryLabels)].map(value => <button key={value} className={`btn compact ${category === value ? "primary" : ""}`} aria-pressed={category === value} onClick={() => setCategory(value)}>{value === "all" ? "Tất cả" : categoryLabels[value as keyof typeof categoryLabels]} ({value === "all" ? state.items.length : state.items.filter(q => q.category === value).length})</button>)}</div>
          {!state.items.length ? <section className="candidate-card candidate-empty"><ListChecks size={30}/><h2>Chưa có bộ câu hỏi</h2><p className="muted">Chọn số câu và bấm Sinh bộ câu hỏi để bắt đầu.</p></section> : <>
            {!state.items.some(q => category === "all" || category === q.category) && <div className="notice">Chưa có câu hỏi trong nhóm này.</div>}
            {state.items.map((q, index) => (category === "all" || category === q.category) && <article className="candidate-card interview-question" key={q.id}>
              <div className="interview-row"><span className="badge">Câu {index + 1}</span><span className="badge">{categoryLabels[q.category]}</span></div><h2>{q.question}</h2>
              <div className="interview-evidence"><p className="small"><strong>Căn cứ từ CV · {q.cv_section}</strong></p><blockquote>{q.evidence_quote}</blockquote></div>
              <button className="btn compact" onClick={() => copy(`${q.question}\n\nCăn cứ CV (${q.cv_section}): ${q.evidence_quote}`)}><Copy size={15}/>Sao chép câu {index + 1}</button>
            </article>)}
          </>}
        </>}
      </div></div>
      <dialog className="interview-confirm" ref={dialog} aria-labelledby="interview-confirm-title"><h2 id="interview-confirm-title">{confirmation?.kind === "delete" ? "Xóa toàn bộ câu hỏi?" : "Thay bộ câu hỏi đã lưu?"}</h2><p>{confirmation?.kind === "delete" ? "Bộ câu hỏi của ứng viên này sẽ bị xóa khỏi database." : "Bộ hiện tại được giữ cho đến khi sinh và lưu thành công bộ mới."}</p><div className="interview-confirm-actions"><button className="btn" onClick={() => dialog.current?.close()}>Hủy</button><button className={`btn ${confirmation?.kind === "delete" ? "danger" : "primary"}`} onClick={() => {dialog.current?.close(); if (confirmation) void mutate(confirmation.kind, confirmation.revision, confirmation.count, true);}}>{confirmation?.kind === "delete" ? "Xác nhận xóa" : "Xác nhận sinh lại"}</button></div></dialog>
    </>}
  </>;
}
