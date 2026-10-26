import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { searchString, type SearchParams } from "@/features/candidates/contracts";
import { OpsApp } from "@/features/ops/ops-app";
export default async function Ops({searchParams}: {searchParams: Promise<SearchParams>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  return <OpsApp search={searchString(await searchParams)}/>;
}
