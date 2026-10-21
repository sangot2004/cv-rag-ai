import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { searchString, type SearchParams } from "@/features/candidates/contracts";
import { IngestionApp } from "@/features/ingestion/ingestion-app";
export default async function Jobs({searchParams}: {searchParams: Promise<SearchParams>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  return <IngestionApp mode="jobs" search={searchString(await searchParams)}/>;
}
