"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({children}: {children: React.ReactNode}) {
  const [client] = useState(() => new QueryClient({defaultOptions: {
    queries: {retry: false, staleTime: 0, refetchOnWindowFocus: false},
    mutations: {retry: false},
  }}));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
