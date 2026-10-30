"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { PanelLeftClose, PanelLeftOpen, Activity, Building2, BriefcaseBusiness, FileUp, ListChecks, Mail, Mails, History, LogOut, Menu, MessageSquare, ShieldCheck, Workflow, Users, X } from "lucide-react";
import { Brand, ErrorNotice } from "@/components/ui";
import { api, broadcastSession, leaveSession } from "@/lib/api";
import type { User } from "@/lib/contracts";

export function AdminWorkspace({user, title, active, children, mainId = "candidate-main"}: {user: User; title: string; active: "candidates" | "interviews" | "compose" | "bulk" | "history" | "users" | "departments" | "postings" | "upload" | "jobs" | "ops"; children: ReactNode; mainId?: string}) {
  const client = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
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
    <nav className="sidebar-content candidate-navigation" aria-label="Điều hướng chính" onClick={event => {if (event.target instanceof Element && event.target.closest("a")) drawer.current?.close();}}>
      <p className="sidebar-label">Không gian làm việc</p>
      <Link href="/chat" title="Hỏi đáp AI" aria-label="Hỏi đáp AI"><MessageSquare size={18}/><span className="nav-label">Hỏi đáp AI</span></Link>
      <Link href="/candidates" aria-current={active === "candidates" ? "page" : undefined} onClick={() => drawer.current?.close()} title="Ứng viên" aria-label="Ứng viên"><Users size={18}/><span className="nav-label">Ứng viên</span></Link>
      {user.role === "admin" && <>
      <Link href="/interviews" aria-current={active === "interviews" ? "page" : undefined} onClick={() => drawer.current?.close()} title="Câu hỏi phỏng vấn" aria-label="Câu hỏi phỏng vấn"><ListChecks size={18}/><span className="nav-label">Câu hỏi phỏng vấn</span></Link>
      <p className="sidebar-label email-nav-label">Thư mời phỏng vấn</p>
      <Link href="/emails/compose" aria-current={active === "compose" ? "page" : undefined} title="Soạn thư mời" aria-label="Soạn thư mời"><Mail size={18}/><span className="nav-label">Soạn thư mời</span></Link>
      <Link href="/emails/bulk" aria-current={active === "bulk" ? "page" : undefined} title="Gửi hàng loạt" aria-label="Gửi hàng loạt"><Mails size={18}/><span className="nav-label">Gửi hàng loạt</span></Link>
      <Link href="/emails/history" aria-current={active === "history" ? "page" : undefined} title="Lịch sử gửi thư" aria-label="Lịch sử gửi thư"><History size={18}/><span className="nav-label">Lịch sử gửi thư</span></Link>
      <p className="sidebar-label email-nav-label">Tiếp nhận CV</p>
      <Link href="/ingestion/upload" aria-current={active === "upload" ? "page" : undefined} title="Upload CV" aria-label="Upload CV"><FileUp size={18}/><span className="nav-label">Upload CV</span></Link>
      <Link href="/ingestion/jobs" aria-current={active === "jobs" ? "page" : undefined} title="Theo dõi xử lý" aria-label="Theo dõi xử lý"><Workflow size={18}/><span className="nav-label">Theo dõi xử lý</span></Link>
      <Link href="/ops" aria-current={active === "ops" ? "page" : undefined} title="System Ops" aria-label="System Ops"><Activity size={18}/><span className="nav-label">System Ops</span></Link>
      <p className="sidebar-label email-nav-label">Quản trị</p>
      <Link href="/admin/departments" aria-current={active === "departments" ? "page" : undefined} title="Phòng ban" aria-label="Phòng ban"><Building2 size={18}/><span className="nav-label">Phòng ban</span></Link>
      <Link href="/admin/postings" aria-current={active === "postings" ? "page" : undefined} title="Vị trí tuyển dụng" aria-label="Vị trí tuyển dụng"><BriefcaseBusiness size={18}/><span className="nav-label">Vị trí tuyển dụng</span></Link>
      <Link href="/admin/users" aria-current={active === "users" ? "page" : undefined} title="Quản lý tài khoản" aria-label="Quản lý tài khoản"><ShieldCheck size={18}/><span className="nav-label">Quản lý tài khoản</span></Link>
      </>}
    </nav>
    <div className="sidebar-footer"><div className="user-block"><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><div className="user-info"><strong>{user.username}</strong><small>{user.role === "admin" ? "Quản trị viên" : "Ứng viên thuộc phòng ban của bạn"}</small></div><button className="icon-button" aria-label="Đăng xuất" disabled={loggingOut} onClick={logout}><LogOut size={18}/></button></div></div>
  </>;
  return <div className={`workspace candidate-workspace${collapsed ? " navigation-collapsed" : ""}`}>
    <a className="skip-link" href={`#${mainId}`}>Đến nội dung chính</a>
    <aside className="sidebar desktop-sidebar">{sidebar}</aside>
    <dialog ref={drawer} className="mobile-drawer" aria-label="Điều hướng" onClick={e => {if (e.target === e.currentTarget) drawer.current?.close();}}><div className="drawer-content">{sidebar}</div></dialog>
    <main id={mainId} className="candidate-main">
      <header className="workspace-header"><button className="icon-button desktop-nav-toggle" aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}>{collapsed ? <PanelLeftOpen size={20}/> : <PanelLeftClose size={20}/>}</button><button className="icon-button mobile-only" aria-label="Mở điều hướng" onClick={() => drawer.current?.showModal()}><Menu size={20}/></button><div className="header-title"><p className="eyebrow">Không gian tuyển dụng</p><p>{title}</p></div><span className="badge">{user.role === "admin" ? "Admin" : "Tester"}</span></header>
      <div className="candidate-scroll"><div className="candidate-content">{error != null && <ErrorNotice error={error}/>}
        {children}
      </div></div>
    </main>
  </div>;
}
