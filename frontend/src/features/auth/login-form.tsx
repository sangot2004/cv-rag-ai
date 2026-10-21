"use client";
import { useRef, useState, type FormEvent } from "react";
import { Eye, EyeOff, ArrowRight } from "lucide-react";
import { api, broadcastSession } from "@/lib/api";
import { Brand, ErrorNotice } from "@/components/ui";

export function LoginForm({reason}: {reason?: string}) {
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const submitting = useRef(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    submitting.current = true; setBusy(true); setError(null);
    try {
      await api("/api/session/login", {method: "POST", body: {username: data.get("username"), password: data.get("password")}, redirect401: false});
      form.reset(); broadcastSession(); window.location.replace("/chat");
    } catch (error) { setError(error); submitting.current = false; setBusy(false); }
  }
  return <main className="login-page"><div className="login-wrap"><section className="login-card" aria-labelledby="login-title">
    <Brand/><h1 id="login-title">Chào mừng trở lại</h1><p className="login-description">Đăng nhập để tra cứu hồ sơ và tiếp tục công việc tuyển dụng của bạn.</p>
    {reason === "expired" && <div className="notice warning" role="status">Phiên đăng nhập đã hết hạn hoặc không còn hợp lệ. Vui lòng đăng nhập lại.</div>}
    {reason === "signed-out" && <div className="notice success" role="status">Bạn đã đăng xuất.</div>}
    {error != null && <ErrorNotice error={error}/>}
    <form className="login-form" onSubmit={submit} aria-busy={busy}>
      <div className="field"><label htmlFor="username">Tên đăng nhập</label><input id="username" name="username" autoComplete="username" placeholder="Nhập tên đăng nhập" maxLength={100} required disabled={busy}/></div>
      <div className="field"><label htmlFor="password">Mật khẩu</label><div className="password-wrap"><input id="password" name="password" type={visible ? "text" : "password"} autoComplete="current-password" placeholder="Nhập mật khẩu" maxLength={256} required disabled={busy}/><button type="button" className="icon-button" onClick={() => setVisible(!visible)} aria-label={visible ? "Ẩn mật khẩu" : "Hiện mật khẩu"} aria-pressed={visible}>{visible ? <EyeOff size={18}/> : <Eye size={18}/>}</button></div></div>
      <button className="btn primary full" disabled={busy}>{busy ? "Đang đăng nhập…" : <>Đăng nhập <ArrowRight size={17}/></>}</button>
    </form>
    <p className="login-support small muted">Cần cấp tài khoản hoặc đặt lại mật khẩu? Hãy liên hệ quản trị viên của bạn.</p>
  </section><p className="login-caption">Không gian làm việc dành cho đội ngũ tuyển dụng</p></div></main>;
}
