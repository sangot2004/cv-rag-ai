"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus, ShieldCheck } from "lucide-react";
import { AdminWorkspace } from "@/components/admin-workspace";
import { Brand, ErrorNotice, Loading } from "@/components/ui";
import { SessionGate } from "@/features/auth/session-gate";
import { api } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { accountsSchema, departmentsSchema, postingsSchema, type Account } from "./contracts";
import { useDepartments } from "./catalog";

type Mode = "departments" | "postings" | "users";
const names = {departments: "Phòng ban", postings: "Vị trí tuyển dụng", users: "Quản lý tài khoản"};
export function ManagementApp({mode, search}: {mode: Mode; search: string}) {
  return <SessionGate>{user => user.role !== "admin" ? <main className="login-page"><section className="login-card"><Brand/><h1>Bạn chưa có quyền truy cập</h1><Link className="btn primary" href="/chat">Trở về hội thoại</Link></section></main> : <AdminWorkspace key={user.user_id} user={user} active={mode} title={names[mode]} mainId="management-main"><Management key={`${mode}:${search}`} user={user} mode={mode} search={search}/></AdminWorkspace>}</SessionGate>;
}
function Management({user, mode, search}: {user: User; mode: Mode; search: string}) {
  const router = useRouter(), client = useQueryClient(), params = new URLSearchParams(search);
  const [error, setError] = useState<unknown>(null), [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const [role, setRole] = useState("tester"), [target, setTarget] = useState<Account | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const departments = useDepartments(user.user_id);
  const query = useQuery({queryKey: ["management", user.user_id, mode, search], queryFn: async ({signal}) => {
    const data = await api(`/api/backend/admin/${mode}?${search}`, {signal});
    return mode === "users" ? accountsSchema.parse(data) : mode === "departments" ? departmentsSchema.parse(data) : postingsSchema.parse(data);
  }});
  const data = query.data;
  async function refresh() {await client.invalidateQueries({queryKey: ["management", user.user_id]});}
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget, fields = new FormData(form);
    let body: unknown;
    if (mode === "departments") body = {department_name: String(fields.get("department_name")).trim()};
    else if (mode === "postings") body = {department_id: fields.get("department_id"), position_title: String(fields.get("position_title")).trim()};
    else {
      body = {username: String(fields.get("username")).trim(), password: fields.get("password"), role, department_id: fields.get("department_id") || null};
      const password = form.elements.namedItem("password") as HTMLInputElement;
      password.value = "";
    }
    setBusy(true); setError(null); setNotice("");
    try {await api(`/api/backend/admin/${mode}`, {method: "POST", body}); form.reset(); setRole("tester"); await refresh(); setNotice("Đã tạo thành công.");}
    catch (error) {setError(error);} finally {setBusy(false);}
  }
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const next = new URLSearchParams();
    new FormData(event.currentTarget).forEach((value, key) => {if (String(value)) next.set(key, String(value));});
    router.push(`/admin/${mode}?${next}`);
  }
  function page(n: number) {const next = new URLSearchParams(search); next.set("page", String(n)); router.push(`/admin/${mode}?${next}`);}
  async function changeStatus() {
    if (!target) return; setBusy(true); setError(null); setNotice(""); dialog.current?.close();
    try {await api(`/api/backend/admin/users/${target.user_id}/active`, {method: "POST", body: {active: !target.is_active}}); await refresh(); setNotice("Đã cập nhật trạng thái tài khoản và thu hồi các phiên cũ.");}
    catch (error) {setError(error);} finally {setBusy(false);}
  }
  return <>
    <div className="candidate-page-title"><div><p className="eyebrow">Quản trị hệ thống</p><h1>{names[mode]}</h1><p className="muted">{mode === "users" ? "Cấp quyền truy cập và quản lý trạng thái tài khoản." : "Tổ chức dữ liệu tuyển dụng theo phòng ban và vị trí."}</p></div>{mode === "users" ? <ShieldCheck size={30}/> : <Building2 size={30}/>}</div>
    <nav className="management-tabs" aria-label="Quản trị"><Link className="btn" href="/admin/departments" aria-current={mode === "departments" ? "page" : undefined}>Phòng ban</Link><Link className="btn" href="/admin/postings" aria-current={mode === "postings" ? "page" : undefined}>Vị trí tuyển dụng</Link><Link className="btn" href="/admin/users" aria-current={mode === "users" ? "page" : undefined}>Tài khoản</Link></nav>
    {error != null && <ErrorNotice error={error}/>} {notice && <p className="notice success" role="status">{notice}</p>}
    <section className="candidate-card"><h2>{mode === "users" ? "Tạo tài khoản" : mode === "departments" ? "Tạo phòng ban" : "Tạo vị trí tuyển dụng"}</h2>
      <form className="management-create" onSubmit={create}>
        {mode === "departments" ? <label className="field"><span>Tên phòng ban</span><input name="department_name" required maxLength={100}/></label> : <>
          {mode === "postings" ? <label className="field"><span>Tên vị trí tuyển dụng</span><input name="position_title" required maxLength={255}/></label> : <>
            <label className="field"><span>Tên tài khoản mới</span><input name="username" required minLength={3} maxLength={100} autoComplete="off"/></label>
            <label className="field"><span>Mật khẩu mới</span><input aria-label="Mật khẩu mới" name="password" type="password" required minLength={12} maxLength={256} autoComplete="new-password"/><small>Từ 12 đến 256 ký tự.</small></label>
            <label className="field"><span>Quyền tài khoản</span><select aria-label="Quyền tài khoản" value={role} onChange={e => setRole(e.target.value)}><option value="tester">Tester</option><option value="admin">Admin</option></select></label>
          </>}
          <label className="field"><span>Phòng ban của {mode === "users" ? "tài khoản" : "vị trí"}</span><select aria-label={`Phòng ban của ${mode === "users" ? "tài khoản" : "vị trí"}`} name="department_id" required={mode === "postings" || role === "tester"} defaultValue={params.get("department_id") || ""} disabled={departments.isPending || !!departments.error}><option value="">Chọn phòng ban</option>{departments.data?.map(d => <option key={d.department_id} value={d.department_id}>{d.department_name}</option>)}</select>{departments.data?.length === 0 && <small>Hãy tạo phòng ban trước.</small>}</label>
        </>}
        <button className="btn primary" disabled={busy || (mode !== "departments" && (departments.isPending || !!departments.error))}><Plus size={16}/>{busy ? "Đang lưu…" : "Tạo mới"}</button>
      </form>
      {departments.error && <><ErrorNotice error={departments.error}/><button className="btn" onClick={() => departments.refetch()}>Tải lại phòng ban</button></>}
    </section>
    <section className="candidate-card candidate-results">
      <form className="management-filter" onSubmit={filter} aria-label="Bộ lọc quản trị"><label className="field"><span>Tìm kiếm</span><input name="q" defaultValue={params.get("q") || ""} maxLength={200} placeholder={mode === "users" ? "Tên tài khoản…" : "Tên…"}/></label>
        {mode !== "departments" && <label className="field"><span>Lọc phòng ban</span><select aria-label="Lọc phòng ban" name="department_id" defaultValue={params.get("department_id") || ""}><option value="">Tất cả phòng ban</option>{departments.data?.map(d => <option key={d.department_id} value={d.department_id}>{d.department_name}</option>)}</select></label>}
        {mode === "users" && <><label className="field"><span>Lọc quyền</span><select aria-label="Lọc quyền" name="role" defaultValue={params.get("role") || ""}><option value="">Tất cả quyền</option><option value="admin">Admin</option><option value="tester">Tester</option></select></label><label className="field"><span>Lọc trạng thái</span><select aria-label="Lọc trạng thái" name="active" defaultValue={params.get("active") || ""}><option value="">Tất cả trạng thái</option><option value="true">Đang hoạt động</option><option value="false">Đã khóa</option></select></label></>}
        <button className="btn">Áp dụng</button><Link className="btn" href={`/admin/${mode}`}>Xóa bộ lọc</Link>
      </form>
      {query.isPending ? <Loading/> : query.error ? <><ErrorNotice error={query.error}/><button className="btn" onClick={() => query.refetch()}>Tải lại danh sách</button></> : data && <>
        <div className="candidate-results-heading"><h2>{data.total} {mode === "users" ? "tài khoản" : mode === "departments" ? "phòng ban" : "vị trí"}</h2></div>
        {!data.items.length ? <p className="candidate-empty">Chưa có dữ liệu phù hợp.</p> : <div className="candidate-table-wrap"><table className="candidate-table management-table"><thead><tr>{(mode === "departments" ? ["Phòng ban", "Vị trí tuyển", "CV", "Thao tác"] : mode === "postings" ? ["Vị trí tuyển dụng", "Phòng ban", "Trạng thái", "CV", "Thao tác"] : ["Tài khoản", "Quyền", "Phòng ban", "Trạng thái", "Thao tác"]).map(s => <th key={s}>{s}</th>)}</tr></thead><tbody>
          {data.items.map(row => "username" in row ? <tr key={row.user_id}><td><strong>{row.username}</strong>{row.user_id === user.user_id && <small className="muted"> · Bạn</small>}</td><td>{row.role === "admin" ? "Admin" : "Tester"}</td><td>{row.department_name || "—"}</td><td><span className={`badge ${row.is_active ? "success" : ""}`}>{row.is_active ? "Đang hoạt động" : "Đã khóa"}</span></td><td><button className="btn compact" disabled={busy || row.user_id === user.user_id} onClick={() => {setTarget(row); dialog.current?.showModal();}}>{row.is_active ? "Khóa tài khoản" : "Mở tài khoản"}</button></td></tr> : "posting_id" in row ? <tr key={row.posting_id}><td><strong>{row.position_title}</strong></td><td>{row.department_name}</td><td><span className="badge">{row.is_active ? "Đang tuyển" : "Đã ngừng tuyển"}</span></td><td>{row.cv_count}</td><td><Link href={`/candidates?posting_id=${row.posting_id}&posting_name=${encodeURIComponent(row.position_title)}`}>Xem ứng viên</Link></td></tr> : <tr key={row.department_id}><td><strong>{row.department_name}</strong></td><td>{row.posting_count}</td><td>{row.cv_count}</td><td><div className="management-links"><Link href={`/admin/postings?department_id=${row.department_id}`}>Xem vị trí</Link><Link href={`/candidates?department_id=${row.department_id}&department_name=${encodeURIComponent(row.department_name)}`}>Xem CV</Link></div></td></tr>)}
        </tbody></table></div>}
        <div className="candidate-pagination"><span>Trang {data.page} / {Math.max(1, Math.ceil(data.total / data.page_size))}</span><div><button className="btn compact" disabled={data.page <= 1} onClick={() => page(data.page-1)}>Trang trước</button><button className="btn compact" disabled={!data.has_next} onClick={() => page(data.page+1)}>Trang sau</button></div></div>
      </>}
    </section>
    <dialog ref={dialog} className="email-confirm" aria-labelledby="account-confirm-title"><h2 id="account-confirm-title">{target?.is_active ? "Khóa tài khoản?" : "Mở lại tài khoản?"}</h2><p>Tài khoản: <strong>{target?.username}</strong>. Các phiên cũ sẽ bị thu hồi; lịch sử hội thoại vẫn được giữ.</p><div className="interview-confirm-actions"><button className="btn" onClick={() => dialog.current?.close()}>Hủy</button><button className="btn primary" onClick={changeStatus}>Xác nhận</button></div></dialog>
  </>;
}
