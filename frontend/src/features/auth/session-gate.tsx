"use client";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, sessionNavigationPending } from "@/lib/api";
import { userSchema, type User } from "@/lib/contracts";
import { Brand, ErrorNotice, Loading } from "@/components/ui";

export function SessionGate({children}: {children: (user: User) => React.ReactNode}) {
  const client = useQueryClient();
  const session = useQuery({queryKey: ["session"], queryFn: async ({signal}) => userSchema.parse(await api("/api/session/me", {signal})), refetchOnWindowFocus: "always", refetchInterval: 60_000});
  useEffect(() => {
    if (session.data) client.removeQueries({predicate: query =>
      ["history", "conversations", "candidates", "candidate", "interviews", "emails", "management", "ingestion", "ops"].includes(String(query.queryKey[0])) && query.queryKey[1] !== session.data.user_id});
  }, [client, session.data]);
  useEffect(() => {
    const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("cv-session") : null;
    if (channel) channel.onmessage = () => { if (!sessionNavigationPending()) window.location.reload(); };
    const restore = (event: PageTransitionEvent) => { if (event.persisted) window.location.reload(); };
    window.addEventListener("pageshow", restore);
    return () => { channel?.close(); window.removeEventListener("pageshow", restore); };
  }, []);
  if (session.error) return <main className="login-page"><div className="login-card"><Brand/><h1>Chưa xác minh được phiên</h1><ErrorNotice error={session.error}/><button className="btn primary" onClick={() => session.refetch()}>Thử lại</button></div></main>;
  if (!session.data) return <main className="login-page"><Loading text="Đang xác minh tài khoản…"/></main>;
  // Preserve forms during validation; keep private content hidden until the
  // backend confirms the current cookie. User-keyed workspace resets on swap.
  return <><div style={session.isFetching ? {visibility: "hidden"} : undefined} inert={session.isFetching}>{children(session.data)}</div>{session.isFetching && <div className="session-check"><Loading text="Đang xác minh phiên…"/></div>}</>;
}
