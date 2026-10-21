"use client";
import Link from "next/link";
import { AdminWorkspace } from "@/components/admin-workspace";
import { Brand } from "@/components/ui";
import { SessionGate } from "@/features/auth/session-gate";
import { UploadCVs } from "./upload";
import { Jobs, JobDetail } from "./jobs";
export function IngestionApp({mode, search = "", jobId}: {mode: "upload" | "jobs" | "job"; search?: string; jobId?: string}) {
  return <SessionGate>{user => user.role !== "admin" ? <main className="login-page"><section className="login-card"><Brand/><h1>Bạn chưa có quyền truy cập</h1><Link className="btn primary" href="/chat">Trở về hội thoại</Link></section></main> : <AdminWorkspace key={user.user_id} user={user} active={mode === "upload" ? "upload" : "jobs"} title="Tiếp nhận hồ sơ CV" mainId="ingestion-main">
    <nav className="management-tabs" aria-label="Tiếp nhận CV"><Link className="btn" href="/ingestion/upload" aria-current={mode === "upload" ? "page" : undefined}>Upload CV</Link><Link className="btn" href="/ingestion/jobs" aria-current={mode !== "upload" ? "page" : undefined}>Theo dõi xử lý</Link></nav>
    {mode === "upload" ? <UploadCVs user={user}/> : jobId ? <JobDetail key={jobId} user={user} jobId={jobId}/> : <Jobs key={search} user={user} search={search}/>}
  </AdminWorkspace>}</SessionGate>;
}
