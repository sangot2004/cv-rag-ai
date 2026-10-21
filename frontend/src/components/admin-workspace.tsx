"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Building2, BriefcaseBusiness, FileUp, ListChecks, Mail, Mails, History, LogOut, Menu, MessageSquare, ShieldCheck, Workflow, Users, X } from "lucide-react";
import { Brand, ErrorNotice } from "@/components/ui";
import { api, broadcastSession, leaveSession } from "@/lib/api";
import type { User } from "@/lib/contracts";

export function AdminWorkspace({user, title, active, children, mainId = "candidate-main"}: {user: User; title: string; active: "candidates" | "interviews" | "compose" | "bulk" | "history" | "users" | "departments" | "postings" | "upload" | "jobs"; children: ReactNode; mainId?: string}) {
  const client = useQueryClient();
  const drawer = useRef<HTMLDialogElement>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 768px)");
    const close = () => {if (media.matches) drawer.current?.close();};
    media.addEventListener("change", close);
    return () => media.removeEventListener("change", close);
  }, []);
  async function logout() {
    setLoggingOut(true); setError(null);
    try {
      await api("/api/session/logout", {method: "POST", body: {}});
      leaveSession("signed-out"); await client.cancelQueries(); client.clear(); broadcastSession();
    } catch (error) {setError(error); setLoggingOut(false);}
  }
  const sidebar = <>
    <div className="sidebar-top"><Brand/><button className="icon-button mobile-only" aria-label="Đóng điều hướng" onClick={() => drawer.current?.close()}><X size={20}/></button></div>
    <nav className="sidebar-content candidate-navigation" aria-label="Điều hướng chính">
      <p className="sidebar-label">Không gian làm việc</p>
      <Link href="/chat"><MessageSquare size={18}/>Hỏi đáp AI</Link>
      <Link href="/candidates" aria-current={active === "candidates" ? "page" : undefined} onClick={() => drawer.current?.close()}><Users size={18}/>Ứng viên</Link>
      <Link href="/interviews" aria-current={active === "interviews" ? "page" : undefined} onClick={() => drawer.current?.close()}><ListChecks size={18}/>Câu hỏi phỏng vấn</Link>
      <p className="sidebar-label email-nav-label">Thư mời phỏng vấn</p>
      <Link href="/emails/compose" aria-current={active === "compose" ? "page" : undefined}><Mail size={18}/>Soạn thư mời</Link>
      <Link href="/emails/bulk" aria-current={active === "bulk" ? "page" : undefined}><Mails size={18}/>Gửi hàng loạt</Link>
      <Link href="/emails/history" aria-current={active === "history" ? "page" : undefined}><History size={18}/>Lịch sử gửi thư</Link>
      <p className="sidebar-label email-nav-label">Tiếp nhận CV</p>
      <Link href="/ingestion/upload" aria-current={active === "upload" ? "page" : undefined}><FileUp size={18}/>Upload CV</Link>
      <Link href="/ingestion/jobs" aria-current={active === "jobs" ? "page" : undefined}><Workflow size={18}/>Theo dõi xử lý</Link>
      <p className="sidebar-label email-nav-label">Quản trị</p>
      <Link href="/admin/departments" aria-current={active === "departments" ? "page" : undefined}><Building2 size={18}/>Phòng ban</Link>
      <Link href="/admin/postings" aria-current={active === "postings" ? "page" : undefined}><BriefcaseBusiness size={18}/>Vị trí tuyển dụng</Link>
      <Link href="/admin/users" aria-current={active === "users" ? "page" : undefined}><ShieldCheck size={18}/>Quản lý tài khoản</Link>
    </nav>
    <div className="sidebar-footer"><div className="user-block"><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><div className="user-info"><strong>{user.username}</strong><small>Quản trị viên</small></div><button className="icon-button" aria-label="Đăng xuất" disabled={loggingOut} onClick={logout}><LogOut size={18}/></button></div></div>
  </>;
  return <div className="workspace candidate-workspace">
    <a className="skip-link" href={`#${mainId}`}>Đến nội dung chính</a>
    <aside className="sidebar desktop-sidebar">{sidebar}</aside>
    <dialog ref={drawer} className="mobile-drawer" aria-label="Điều hướng" onClick={e => {if (e.target === e.currentTarget) drawer.current?.close();}}><div className="drawer-content">{sidebar}</div></dialog>
    <main id={mainId} className="candidate-main">
      <header className="workspace-header"><button className="icon-button mobile-only" aria-label="Mở điều hướng" onClick={() => drawer.current?.showModal()}><Menu size={20}/></button><div className="header-title"><p className="eyebrow">Không gian tuyển dụng</p><p>{title}</p></div><span className="badge">Admin</span></header>
      <div className="candidate-scroll"><div className="candidate-content">{error != null && <ErrorNotice error={error}/>}
        {children}
      </div></div>
    </main>
  </div>;
}
