"use client";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { SessionGate } from "@/features/auth/session-gate";
import { Brand } from "@/components/ui";

export default function Forbidden() {
  return <SessionGate>{user => <main className="login-page"><section className="login-card forbidden-content"><Brand/><div className="welcome-mark"><ShieldAlert size={28}/></div><h1>Bạn chưa có quyền truy cập</h1><p>Tài khoản {user.username} không được cấp quyền sử dụng chức năng này. Hãy liên hệ quản trị viên nếu cần hỗ trợ.</p><div className="status-actions"><Link className="btn primary" href="/chat">Trở về hội thoại</Link></div></section></main>}</SessionGate>;
}
