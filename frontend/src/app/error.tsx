"use client";
import Link from "next/link";
import { CircleAlert } from "lucide-react";
import { Brand } from "@/components/ui";

export default function ErrorPage({error, reset}: {error: Error & {digest?: string}; reset: () => void}) {
  return <main className="login-page"><section className="login-card system-state"><Brand/>
    <div className="welcome-mark"><CircleAlert size={28}/></div><h1>Chưa mở được trang</h1>
    <p>Hãy thử tải lại. Nếu thao tác vừa thực hiện bị gián đoạn, kiểm tra trạng thái trước khi gửi lại yêu cầu.</p>
    {error.digest && <p className="small muted">Mã hỗ trợ: <code>{error.digest}</code></p>}
    <div className="status-actions"><button className="btn primary" onClick={reset}>Thử tải lại</button><Link className="btn" href="/chat">Trở về hội thoại</Link></div>
  </section></main>;
}
