import { cookies } from "next/headers";
import { redirect, notFound } from "next/navigation";
import { z } from "zod";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { CandidatesApp } from "@/features/candidates/candidates-app";
import { searchString, type SearchParams } from "@/features/candidates/contracts";

export default async function Candidate({params, searchParams}: {params: Promise<{candidateId: string}>; searchParams: Promise<SearchParams>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  const {candidateId} = await params;
  if (!z.uuid().safeParse(candidateId).success) notFound();
  return <CandidatesApp candidateId={candidateId} search={searchString(await searchParams)}/>;
}
