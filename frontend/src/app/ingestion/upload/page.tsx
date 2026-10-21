import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { IngestionApp } from "@/features/ingestion/ingestion-app";
export default async function Upload() {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  return <IngestionApp mode="upload"/>;
}
