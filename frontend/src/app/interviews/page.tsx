import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { z } from "zod";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { InterviewsApp } from "@/features/interviews/interviews-app";

export default async function Interviews({searchParams}: {searchParams: Promise<{candidate?: string; list?: string}>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  const {candidate, list} = await searchParams;
  if (candidate && !z.uuid().safeParse(candidate).success) notFound();
  return <InterviewsApp candidateId={candidate} listSearch={list || ""}/>;
}
