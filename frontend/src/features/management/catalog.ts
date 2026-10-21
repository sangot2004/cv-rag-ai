"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { departmentsSchema, postingsSchema, type Department, type Posting } from "./contracts";

export function useDepartments(userId: string) {
  return useQuery({queryKey: ["management", userId, "department-options"], queryFn: async ({signal}) => {
    const rows: Department[] = [];
    for (let page = 1; ; page++) {
      const data = departmentsSchema.parse(await api(`/api/backend/admin/departments?page_size=100&page=${page}`, {signal}));
      rows.push(...data.items); if (!data.has_next) return rows;
    }
  }});
}
export function usePostings(userId: string) {
  return useQuery({queryKey: ["management", userId, "posting-options"], queryFn: async ({signal}) => {
    const rows: Posting[] = [];
    for (let page = 1; ; page++) {
      const data = postingsSchema.parse(await api(`/api/backend/admin/postings?page_size=100&page=${page}`, {signal}));
      rows.push(...data.items); if (!data.has_next) return rows.filter(p => p.is_active);
    }
  }});
}
