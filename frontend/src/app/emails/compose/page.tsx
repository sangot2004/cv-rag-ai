import { cookies } from "next/headers";
import { redirect, notFound } from "next/navigation";
import { z } from "zod";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { EmailsApp } from "@/features/emails/emails-app";
export default async function Compose({searchParams}: {searchParams: Promise<{candidate?: string}>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  const {candidate} = await searchParams;
  if (candidate && !z.uuid().safeParse(candidate).success) notFound();
  return <EmailsApp mode="compose" candidateId={candidate}/>;
}
