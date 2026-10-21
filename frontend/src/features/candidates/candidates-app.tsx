"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, FileSearch, Search, Users, X } from "lucide-react";
import { SessionGate } from "@/features/auth/session-gate";
import { Brand, ErrorNotice, Loading } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { apiSearch, candidateDetailSchema, candidateListSchema, type Candidate } from "./contracts";
import { AdminWorkspace } from "@/components/admin-workspace";
import { CandidatePortrait } from "./candidate-portrait";
import { CandidateAssignment } from "@/features/management/assignment";

type Props = {search: string; candidateId?: string};
export function CandidatesApp(props: Props) {
  return <SessionGate>{user => user.role === "admin"
    ? <AdminWorkspace key={user.user_id} user={user} active="candidates" title={props.candidateId ? "Ứng viên / Chi tiết hồ sơ" : "Quản lý hồ sơ ứng viên"}>{props.candidateId ? <CandidateProfile key={props.candidateId} candidateId={props.candidateId} search={props.search} user={user}/> : <CandidateList key={props.search} search={props.search} user={user}/>}</AdminWorkspace>
    : <main className="login-page"><section className="login-card"><Brand/><h1>Bạn chưa có quyền truy cập</h1><p>Chức năng ứng viên dành cho quản trị viên.</p><Link className="btn primary" href="/chat">Trở về hội thoại</Link></section></main>}</SessionGate>;
}
function QueryError({error, retry}: {error: unknown; retry: () => void}) {
  if (error instanceof ApiError && error.status === 403) return <section className="candidate-card"><h2>Bạn chưa có quyền truy cập</h2><Link href="/chat">Trở về hội thoại</Link></section>;
  if (error instanceof ApiError && error.status === 404) return <section className="candidate-card"><h2>Không tìm thấy ứng viên</h2><p>Hồ sơ này không còn tồn tại hoặc không thể truy cập.</p></section>;
  return <div className="candidate-error"><ErrorNotice error={error}/><button className="btn" onClick={retry}>Thử lại</button></div>;
}
function Skills({items}: {items: string[]}) {
  return items.length ? <div className="skill-list">{items.map((skill, i) => <span className="badge" key={`${skill}-${i}`}>{skill}</span>)}</div> : <span className="muted">Chưa có dữ liệu kỹ năng</span>;
}
function years(value: number | null) {return value === null ? "Chưa có dữ liệu" : `${value.toLocaleString("vi-VN")} năm`;}
function date(value: string | null) {return value ? new Date(value).toLocaleDateString("vi-VN", {timeZone: "UTC"}) : "Chưa có dữ liệu";}
function groupLink(candidate: Candidate, type: "department" | "posting", search: string) {
  const q = new URLSearchParams(search); q.delete("page");
  if (candidate.posting) {
    q.set(`${type}_id`, type === "department" ? candidate.posting.department.department_id : candidate.posting.posting_id);
    q.set(`${type}_name`, type === "department" ? candidate.posting.department.department_name : candidate.posting.position_title);
  }
  return `/candidates?${q}`;
}
function CandidateList({search, user}: {search: string; user: User}) {
  const router = useRouter();
  const params = new URLSearchParams(search);
  const [validation, setValidation] = useState("");
  const query = useQuery({queryKey: ["candidates", user.user_id, apiSearch(search)], queryFn: async ({signal}) => candidateListSchema.parse(await api(`/api/backend/candidates?${apiSearch(search)}`, {signal}))});
  const data = query.data;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setValidation("");
    const fields = new FormData(event.currentTarget);
    const next = new URLSearchParams();
    for (const key of ["q", "position", "min_years_experience", "max_years_experience", "sort", "page_size"]) {
      const value = String(fields.get(key) || "").trim(); if (value) next.set(key, value);
    }
    for (const key of ["department_id", "department_name", "posting_id", "posting_name"]) {const value = params.get(key); if (value) next.set(key, value);}
    const skills = String(fields.get("skills") || "").split(",").map(s => s.trim()).filter(Boolean);
    if (skills.length > 20 || skills.some(s => s.length > 100)) {setValidation("Nhập tối đa 20 kỹ năng, mỗi kỹ năng không quá 100 ký tự."); return;}
    skills.forEach(skill => next.append("skills", skill));
    if (next.has("min_years_experience") && next.has("max_years_experience") && Number(next.get("min_years_experience")) > Number(next.get("max_years_experience"))) {setValidation("Kinh nghiệm tối thiểu phải nhỏ hơn hoặc bằng tối đa."); return;}
    router.push(`/candidates?${next}`);
  }
  function page(number: number) {const next = new URLSearchParams(search); next.set("page", String(number)); router.push(`/candidates?${next}`);}
  function removeGroup(type: string) {const next = new URLSearchParams(search); next.delete(`${type}_id`); next.delete(`${type}_name`); next.delete("page"); router.push(`/candidates?${next}`);}
  return <>
    <div className="candidate-page-title"><div><p className="eyebrow">Hồ sơ tuyển dụng</p><h1>Ứng viên</h1><p className="muted">Tìm kiếm kỹ năng, khám phá kinh nghiệm và xem hồ sơ chi tiết.</p></div><span className="candidate-title-icon"><Users size={26}/></span></div>
    <form className="candidate-card candidate-filters" onSubmit={submit} aria-label="Bộ lọc ứng viên">
      <div className="candidate-filter-grid">
        <label className="field candidate-search"><span>Tìm tên hoặc email</span><input name="q" maxLength={200} defaultValue={params.get("q") || ""} placeholder="Tên ứng viên hoặc email…"/></label>
        <label className="field"><span>Vị trí ứng tuyển</span><input name="position" maxLength={255} defaultValue={params.get("position") || ""} placeholder="Ví dụ: Data Engineer"/></label>
        <label className="field"><span>Kỹ năng</span><input aria-label="Kỹ năng" name="skills" defaultValue={params.getAll("skills").join(", ")} placeholder="Python, SQL"/><small>Phân cách bằng dấu phẩy; cần đủ các kỹ năng.</small></label>
        <label className="field"><span>Kinh nghiệm tối thiểu (năm)</span><input type="number" name="min_years_experience" min="0" step="any" defaultValue={params.get("min_years_experience") || ""}/></label>
        <label className="field"><span>Kinh nghiệm tối đa (năm)</span><input type="number" name="max_years_experience" min="0" step="any" defaultValue={params.get("max_years_experience") || ""}/></label>
        <label className="field"><span>Sắp xếp</span><select name="sort" defaultValue={params.get("sort") || "newest"}><option value="newest">Mới nhất</option><option value="oldest">Cũ nhất</option><option value="name_asc">Tên A–Z</option><option value="experience_desc">Kinh nghiệm giảm dần</option></select></label>
        <label className="field"><span>Số hồ sơ mỗi trang</span><select name="page_size" defaultValue={params.get("page_size") || "20"}>{[10,20,50,100].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
      </div>
      {validation && <p role="alert" className="field-error">{validation}</p>}
      <div className="candidate-filter-actions"><button className="btn primary" type="submit"><Search size={17}/>Áp dụng bộ lọc</button><Link className="btn" href="/candidates">Xóa bộ lọc</Link></div>
      {(params.has("department_id") || params.has("posting_id")) && <div className="skill-list">{["department", "posting"].filter(type => params.has(`${type}_id`)).map(type => <button type="button" key={type} className="btn compact" onClick={() => removeGroup(type)}>{type === "department" ? "Phòng ban" : "Vị trí tuyển dụng"}: {params.get(`${type}_name`) || "Đã chọn"}<X size={14}/><span className="sr-only">Bỏ lọc</span></button>)}</div>}
    </form>
    {query.isPending ? <Loading text="Đang tải danh sách ứng viên…"/> : query.error ? <QueryError error={query.error} retry={() => query.refetch()}/> : data && <section className="candidate-card candidate-results" aria-label="Kết quả tìm kiếm">
      <div className="candidate-results-heading"><h2>{data.total.toLocaleString("vi-VN")} ứng viên</h2><span className="muted small">Bấm tên để mở hồ sơ</span></div>
      {!data.items.length ? <div className="candidate-empty"><FileSearch size={36}/><h2>{data.total ? "Trang này không có hồ sơ" : "Không tìm thấy ứng viên"}</h2><p className="muted">Thử thay đổi hoặc xóa bộ lọc để xem thêm hồ sơ.</p>{data.page > 1 && <button className="btn" onClick={() => page(1)}>Về trang đầu</button>}</div> : <div className="candidate-table-wrap"><table className="candidate-table"><thead><tr><th>Ứng viên</th><th>Vị trí ứng tuyển</th><th>Kinh nghiệm</th><th>Kỹ năng</th><th>Phòng ban / Vị trí tuyển dụng</th></tr></thead><tbody>{data.items.map(item => <tr key={item.candidate_id}>
        <td><Link className="candidate-person" href={`/candidates/${item.candidate_id}${search ? `?${search}` : ""}`}><span className="avatar">{item.full_name.slice(0, 2).toUpperCase()}</span><strong>{item.full_name}</strong></Link><p className="muted small">{item.email || "Chưa có email"}</p>{item.has_photo && <CandidatePortrait candidateId={item.candidate_id} name={item.full_name}/>}</td>
        <td>{item.applied_position || "Chưa có dữ liệu"}</td><td>{years(item.total_years_experience)}</td><td><Skills items={item.skills}/></td>
        <td>{item.posting ? <div className="candidate-group"><Link href={groupLink(item, "department", search)} title="Lọc theo phòng ban">{item.posting.department.department_name}</Link><Link href={groupLink(item, "posting", search)} title="Lọc theo vị trí tuyển dụng">{item.posting.position_title}</Link>{!item.posting.is_active && <span className="badge">Đã ngừng tuyển</span>}</div> : <span className="muted">Chưa gắn vị trí tuyển dụng</span>}</td>
      </tr>)}</tbody></table></div>}
      <div className="candidate-pagination"><span className="muted small">Trang {data.page} / {Math.max(data.total_pages, 1)}</span><div><button className="btn compact" disabled={data.page <= 1} onClick={() => page(data.page - 1)}><ChevronLeft size={16}/>Trang trước</button><button className="btn compact" disabled={!data.has_next} onClick={() => page(data.page + 1)}>Trang sau<ChevronRight size={16}/></button></div></div>
    </section>}
  </>;
}
function Section({title, children, empty}: {title: string; children: ReactNode; empty?: boolean}) {
  return <section className="candidate-card profile-section"><h2>{title}</h2>{empty ? <p className="muted">Chưa có dữ liệu.</p> : children}</section>;
}
function CandidateProfile({candidateId, search, user}: {candidateId: string; search: string; user: User}) {
  const query = useQuery({queryKey: ["candidate", user.user_id, candidateId], queryFn: async ({signal}) => candidateDetailSchema.parse(await api(`/api/backend/candidates/${candidateId}`, {signal}))});
  const c = query.data;
  return <>
    <Link className="candidate-back" href={`/candidates${search ? `?${search}` : ""}`}><ArrowLeft size={17}/>Quay lại danh sách</Link>
    {query.isPending ? <Loading text="Đang tải hồ sơ ứng viên…"/> : query.error ? <QueryError error={query.error} retry={() => query.refetch()}/> : c && <>
      <section className="candidate-card profile-heading">{c.has_photo ? <CandidatePortrait candidateId={c.candidate_id} name={c.full_name} variant="profile" fallback={<span className="avatar profile-avatar">{c.full_name.slice(0, 2).toUpperCase()}</span>}/> : <span className="avatar profile-avatar">{c.full_name.slice(0, 2).toUpperCase()}</span>}<div><p className="eyebrow">Hồ sơ ứng viên</p><h1>{c.full_name}</h1><p className="muted">{c.applied_position || "Chưa có vị trí ứng tuyển"}</p></div><div className="profile-heading-actions"><span className="badge">Kinh nghiệm: {years(c.total_years_experience)}</span><Link className="btn primary" href={`/interviews?candidate=${c.candidate_id}&list=${encodeURIComponent(search)}`}>Tạo câu hỏi phỏng vấn</Link><Link className="btn" href={`/emails/compose?candidate=${c.candidate_id}`}>Soạn thư mời</Link></div></section>
      <div className="profile-grid"><aside className="profile-sidebar">
        <Section title="Thông tin liên hệ"><dl className="profile-facts"><dt>Email</dt><dd>{c.email || "Chưa có dữ liệu"}</dd><dt>Điện thoại</dt><dd>{c.phone || "Chưa có dữ liệu"}</dd><dt>Ngày tạo hồ sơ</dt><dd>{date(c.created_at)}</dd><dt>Cập nhật gần nhất</dt><dd>{date(c.updated_at)}</dd></dl></Section>
        <Section title="Kỹ năng"><Skills items={c.skills}/></Section>
        <Section title="Vị trí tuyển dụng">{c.posting ? <div className="candidate-group"><Link href={groupLink(c, "posting", "")}>{c.posting.position_title}</Link><Link href={groupLink(c, "department", "")}>{c.posting.department.department_name}</Link><span className="badge">{c.posting.is_active ? "Đang tuyển" : "Đã ngừng tuyển"}</span></div> : <p className="muted">Chưa gắn vị trí tuyển dụng.</p>}<CandidateAssignment key={`${c.candidate_id}:${c.posting?.posting_id || ""}`} userId={user.user_id} candidateId={c.candidate_id} postingId={c.posting?.posting_id || null}/></Section>
      </aside><div className="profile-sections">
        <Section title="Kinh nghiệm làm việc" empty={!c.experience.length}>{c.experience.map((x, i) => <article className="profile-entry" key={i}><h3>{x.title || "Chưa có chức danh"}</h3><p>{x.company || "Chưa có tên công ty"}</p><p className="muted small">{date(x.start_date)} – {date(x.end_date)}</p>{x.description && <p className="profile-text">{x.description}</p>}</article>)}</Section>
        <Section title="Học vấn" empty={!c.education.length}>{c.education.map((x, i) => <article className="profile-entry" key={i}><h3>{x.school || "Chưa có tên trường"}</h3><p>{[x.degree, x.field].filter(Boolean).join(" · ") || "Chưa có thông tin ngành học"}</p><p className="muted small">Năm tốt nghiệp: {x.graduation_year ?? "Chưa có dữ liệu"}</p></article>)}</Section>
        <Section title="Chứng chỉ" empty={!c.certificates.length}>{c.certificates.map((x, i) => <article className="profile-entry" key={i}><h3>{x.name}</h3><p>{x.issuer || "Chưa có đơn vị cấp"}</p><p className="muted small">Ngày cấp: {date(x.issue_date)}</p>{x.credential_id && <p className="small">Mã chứng chỉ: {x.credential_id}</p>}</article>)}</Section>
        <Section title="Dự án" empty={!c.projects.length}>{c.projects.map((x, i) => <article className="profile-entry" key={i}><h3>{x.name}</h3>{x.role && <p>{x.role}</p>}<p className="muted small">{date(x.start_date)} – {date(x.end_date)}</p>{x.description && <p className="profile-text">{x.description}</p>}<Skills items={x.tech_stack}/></article>)}</Section>
        <section className="candidate-card"><details><summary>Nội dung CV đã trích xuất</summary><p className="profile-text raw-cv">{c.raw_text || "Chưa có nội dung CV."}</p></details></section>
        <p className="muted small">Thông tin được trích xuất từ CV. Kiểm tra hồ sơ trước khi đưa ra quyết định tuyển dụng.</p>
      </div></div>
    </>}
  </>;
}
