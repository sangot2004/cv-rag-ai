import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { CandidatesApp } from "@/features/candidates/candidates-app";
import { searchString, type SearchParams } from "@/features/candidates/contracts";

export default async function Candidates({searchParams}: {searchParams: Promise<SearchParams>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  return <CandidatesApp search={searchString(await searchParams)}/>;
}
