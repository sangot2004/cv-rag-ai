import { cookies } from "next/headers";
import { redirect, notFound } from "next/navigation";
import { z } from "zod";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { EmailsApp } from "@/features/emails/emails-app";
export default async function Batch({params}: {params: Promise<{batchId: string}>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  const {batchId} = await params;
  if (!z.uuid().safeParse(batchId).success) notFound();
  return <EmailsApp mode="batch" batchId={batchId}/>;
}
