import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { ManagementApp } from "@/features/management/management-app";
import { searchString, type SearchParams } from "@/features/candidates/contracts";
export default async function Administration({params, searchParams}: {params: Promise<{section: string}>; searchParams: Promise<SearchParams>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  const {section} = await params;
  if (section !== "users" && section !== "departments" && section !== "postings") notFound();
  return <ManagementApp mode={section} search={searchString(await searchParams)}/>;
}
