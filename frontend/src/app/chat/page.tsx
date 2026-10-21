import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "@/lib/server/backend";
import { ChatApp } from "@/features/chat/chat-app";

export default async function Chat({searchParams}: {searchParams: Promise<{thread?: string}>}) {
  if (!(await cookies()).has(SESSION_COOKIE)) redirect("/login");
  return <ChatApp initialThread={(await searchParams).thread}/>;
}
