"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Mail, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { ErrorNotice, Loading } from "@/components/ui";
import { candidateSchema, candidateListSchema, type Candidate } from "@/features/candidates/contracts";
import { batchSchema, validEmail } from "./contracts";

export function ComposeEmails({user, kind, candidateId}: {user: User; kind: "single" | "bulk"; candidateId?: string}) {
  const router = useRouter();
  const [selection, setSelection] = useState<Candidate[] | null>(null);
  const [search, setSearch] = useState(""); const [page, setPage] = useState(1);
  const [position, setPosition] = useState<string | null>(null);
  const [format, setFormat] = useState("online");
  const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null);
  const creating = useRef(false); const request = useRef<{body: string; id: string} | null>(null);
  const initial = useQuery({queryKey: ["candidate", user.user_id, "email-initial", candidateId], enabled: !!candidateId, queryFn: async ({signal}) => candidateSchema.parse(await api(`/api/backend/candidates/${candidateId}`, {signal}))});
  const params = new URLSearchParams({page: String(page), page_size: "10"}); if (search) params.set("q", search);
  const list = useQuery({queryKey: ["candidates", user.user_id, "email-picker", search, page], queryFn: async ({signal}) => candidateListSchema.parse(await api(`/api/backend/candidates?${params}`, {signal}))});
  const chosen = selection ?? (initial.data ? [initial.data] : []);
  function toggle(c: Candidate) {
    if (kind === "single") setSelection(chosen.some(item => item.candidate_id === c.candidate_id) ? [] : [c]);
    else setSelection(chosen.some(item => item.candidate_id === c.candidate_id) ? chosen.filter(item => item.candidate_id !== c.candidate_id) : chosen.length < 20 ? [...chosen, c] : chosen);
  }
  function find(event: FormEvent<HTMLFormElement>) {event.preventDefault(); setPage(1); setSearch(String(new FormData(event.currentTarget).get("q") || "").trim());}
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (creating.current || !chosen.length) return;
    const fields = new FormData(event.currentTarget);
    const details = `Vòng phỏng vấn: ${fields.get("round")}\nNgày: ${fields.get("date")}\nGiờ: ${fields.get("time")} (giờ Việt Nam, UTC+7)\nHình thức: ${format === "online" ? "Trực tuyến" : "Tại văn phòng"}\n${format === "online" ? "Link" : "Địa điểm"}: ${fields.get("location")}\nNgười phỏng vấn: ${fields.get("interviewers") || "Chưa cung cấp"}\nGhi chú: ${fields.get("notes") || "Không có"}`;
    const input = {kind, candidate_ids: chosen.map(c => c.candidate_id), position: String(fields.get("position")).trim(), name: String(fields.get("name") || `Thư mời ${chosen[0].full_name}`).trim(), interview_details: details};
    const body = JSON.stringify(input);
    if (!request.current || request.current.body !== body) request.current = {body, id: crypto.randomUUID()};
    creating.current = true; setBusy(true); setError(null);
    try {
      const batch = batchSchema.parse(await api("/api/backend/emails/batches", {method: "POST", body: {...input, request_id: request.current.id}}));
      router.push(`/emails/batches/${batch.batch_id}`);
    } catch (error) {setError(error); setBusy(false); creating.current = false;}
  }
  return <>
    <div className="candidate-page-title"><div><p className="eyebrow">Thư mời phỏng vấn</p><h1>{kind === "bulk" ? "Soạn thư mời hàng loạt" : "Soạn thư mời"}</h1><p className="muted">Chọn người nhận và thông tin phỏng vấn, sau đó soạn và duyệt nội dung.</p></div><Mail className="candidate-title-icon" size={56}/></div>
    <div className="email-tabs"><Link className="btn" href="/emails/batches">Đợt gửi & bản nháp đã lưu</Link><Link className="btn" href="/emails/history">Lịch sử gửi thư</Link></div>
    {error != null && <ErrorNotice error={error}/>}{initial.error && <ErrorNotice error={initial.error}/>}
    <section className="candidate-card email-picker"><div className="interview-row"><h2>{kind === "bulk" ? "Chọn người nhận (tối đa 20)" : "Chọn ứng viên"}</h2><span className="badge">Đã chọn {chosen.length}</span></div>
      <form className="interview-picker-search" onSubmit={find}><label className="field"><span>Tìm tên hoặc email người nhận</span><input name="q" maxLength={200} placeholder="Tên hoặc email…"/></label><button className="btn" type="submit"><Search size={16}/>Tìm</button></form>
      {!!chosen.length && <div className="skill-list">{chosen.map(c => <button className="btn compact" key={c.candidate_id} disabled={busy} onClick={() => toggle(c)}>{c.full_name} ×</button>)}</div>}
      {list.isPending ? <Loading/> : list.error ? <><ErrorNotice error={list.error}/><button className="btn" onClick={() => list.refetch()}>Thử tải lại</button></> : list.data && <>
        <div className="email-candidate-grid">{list.data.items.map(c => <label className="email-candidate-option" key={c.candidate_id}><input type="checkbox" aria-label={`Chọn ${c.full_name}`} checked={chosen.some(item => item.candidate_id === c.candidate_id)} disabled={busy || !validEmail(c.email) || (kind === "bulk" && chosen.length >= 20 && !chosen.some(item => item.candidate_id === c.candidate_id))} onChange={() => toggle(c)}/><span><strong>{c.full_name}</strong><small>{c.email || "Chưa có email"}{c.email && !validEmail(c.email) && " · Email chưa hợp lệ"}</small></span></label>)}</div>
        {!list.data.items.length && <p className="muted">Không tìm thấy ứng viên.</p>}<div className="candidate-pagination"><span className="small">Trang {page}</span><div><button className="btn compact" disabled={page <= 1} onClick={() => setPage(n => n-1)}>Trước</button><button className="btn compact" disabled={!list.data.has_next} onClick={() => setPage(n => n+1)}>Sau</button></div></div>
      </>}
    </section>
    <form className="candidate-card email-setup" onSubmit={create}><h2>Thông tin buổi phỏng vấn</h2><div className="candidate-filter-grid">
      <label className="field"><span>Tên đợt gửi / bản nháp</span><input name="name" maxLength={255} placeholder="Ví dụ: Phỏng vấn Data Engineer"/></label>
      <label className="field"><span>Vị trí tuyển dụng</span><input name="position" required maxLength={255} value={position ?? chosen[0]?.applied_position ?? ""} onChange={e => setPosition(e.target.value)}/></label>
      <label className="field"><span>Vòng phỏng vấn</span><input name="round" required maxLength={100} defaultValue="Phỏng vấn chuyên môn"/></label>
      <label className="field"><span>Hình thức</span><select value={format} onChange={e => setFormat(e.target.value)}><option value="online">Trực tuyến</option><option value="office">Tại văn phòng</option></select></label>
      <label className="field"><span>Ngày phỏng vấn</span><input type="date" name="date" required/></label>
      <label className="field"><span>Giờ phỏng vấn (Việt Nam)</span><input type="time" name="time" required/></label>
      <label className="field"><span>{format === "online" ? "Link phỏng vấn" : "Địa điểm phỏng vấn"}</span><input key={format} name="location" type={format === "online" ? "url" : "text"} pattern={format === "online" ? "https?://.+" : undefined} required maxLength={1000}/></label>
      <label className="field"><span>Người phỏng vấn</span><input name="interviewers" maxLength={500}/></label>
    </div><label className="field"><span>Ghi chú phỏng vấn</span><textarea name="notes" maxLength={4000}/></label>
      <p className="muted small">Tạo bản nháp chưa gửi email. Bạn sẽ được xem, sửa và xác nhận người nhận trước khi gửi.</p>
      <button type="submit" className="btn primary" disabled={busy || !chosen.length || chosen.some(c => !validEmail(c.email))}>{busy ? "Đang tạo…" : "Tạo bản nháp"}</button>
    </form>
  </>;
}
