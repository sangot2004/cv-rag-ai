import { Brand, Loading } from "@/components/ui";

export default function LoadingPage() {
  return <main className="login-page"><section className="login-card system-state" aria-busy="true"><Brand/><Loading text="Đang mở trang…"/></section></main>;
}
