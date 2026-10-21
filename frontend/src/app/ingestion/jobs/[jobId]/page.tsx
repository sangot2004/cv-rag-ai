import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { z } from "zod";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { IngestionApp } from "@/features/ingestion/ingestion-app";
export default async function Job({params}: {params: Promise<{jobId: string}>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  const {jobId} = await params;
  if (!z.uuid().safeParse(jobId).success) notFound();
  return <IngestionApp mode="job" jobId={jobId}/>;
}
