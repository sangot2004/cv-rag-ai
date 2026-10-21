"use client";
import Link from "next/link";
import { AdminWorkspace } from "@/components/admin-workspace";
import { Brand } from "@/components/ui";
import { SessionGate } from "@/features/auth/session-gate";
import { ComposeEmails } from "./compose";
import { EmailBatch } from "./email-batch";
import { EmailHistory, EmailBatches } from "./history";

type Props = {mode: "compose" | "bulk" | "history" | "batches" | "batch"; candidateId?: string; batchId?: string; search?: string};
export function EmailsApp(props: Props) {
  return <SessionGate>{user => user.role !== "admin" ? <main className="login-page"><section className="login-card"><Brand/><h1>Bạn chưa có quyền truy cập</h1><p>Chức năng thư mời dành cho quản trị viên.</p><Link className="btn primary" href="/chat">Trở về hội thoại</Link></section></main> : props.mode === "batch" && props.batchId ? <EmailBatch key={`${user.user_id}:${props.batchId}`} user={user} batchId={props.batchId}/> : <AdminWorkspace key={user.user_id} user={user} mainId="email-main" title="Thư mời phỏng vấn" active={props.mode === "compose" ? "compose" : props.mode === "bulk" ? "bulk" : "history"}>
    {props.mode === "history" ? <EmailHistory key={props.search} search={props.search || ""} user={user}/> : props.mode === "batches" ? <EmailBatches user={user}/> : <ComposeEmails key={props.mode + props.candidateId} user={user} kind={props.mode === "bulk" ? "bulk" : "single"} candidateId={props.candidateId}/>}
  </AdminWorkspace>}</SessionGate>;
}
