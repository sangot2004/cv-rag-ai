import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { searchString, type SearchParams } from "@/features/candidates/contracts";
import { EmailsApp } from "@/features/emails/emails-app";
export default async function History({searchParams}: {searchParams: Promise<SearchParams>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  return <EmailsApp mode="history" search={searchString(await searchParams)}/>;
}
