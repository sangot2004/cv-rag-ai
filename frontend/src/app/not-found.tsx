import Link from "next/link";
import { FileSearch } from "lucide-react";
import { Brand } from "@/components/ui";

export default function NotFound() {
  return <main className="login-page"><section className="login-card system-state"><Brand/>
    <div className="welcome-mark"><FileSearch size={28}/></div><p className="eyebrow">404</p>
    <h1>Không tìm thấy trang</h1><p>Đường dẫn không còn tồn tại hoặc chưa đúng. Bạn có thể trở về hội thoại để tiếp tục.</p>
    <Link className="btn primary" href="/chat">Trở về hội thoại</Link>
  </section></main>;
}
