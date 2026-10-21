import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { EmailsApp } from "@/features/emails/emails-app";
export default async function Batches() {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  return <EmailsApp mode="batches"/>;
}
