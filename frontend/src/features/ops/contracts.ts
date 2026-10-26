import { z } from "zod";
const metrics = z.object({calls: z.number(), input_tokens: z.number(), output_tokens: z.number(), estimated_cost_usd: z.number().nullable(), priced_calls: z.number(), missing_usage_calls: z.number(), error_calls: z.number(), failover_calls: z.number()});
export const usageSchema = z.object({id: z.number(), operation_id: z.string(), module_name: z.string(), model_name: z.string(), status: z.string(), input_tokens: z.number().nullable(), output_tokens: z.number().nullable(), cached_tokens: z.number().nullable(), reasoning_tokens: z.number().nullable(), latency_ms: z.number(), estimated_cost_usd: z.number().nullable(), pricing_version: z.string(), attempt: z.number(), created_at: z.string()});
export const dashboardSchema = z.object({
  start: z.string(), end: z.string(), summary: metrics.extend({median_ms: z.number().nullable(), p95_ms: z.number().nullable()}),
  daily: z.array(metrics.extend({day: z.string()})), breakdown: z.array(metrics.extend({module_name: z.string(), model_name: z.string()})),
  options: z.object({modules: z.array(z.string()), models: z.array(z.string()), statuses: z.array(z.string())}),
  dlq_count: z.number(), alerts: z.object({count: z.number(), latency_ms: z.number(), tokens: z.number()}),
  logs: z.object({items: z.array(usageSchema), total: z.number(), page: z.number(), page_size: z.number(), has_next: z.boolean()}),
});
export type Dashboard = z.infer<typeof dashboardSchema>;
export type Usage = z.infer<typeof usageSchema>;
export function number(value: number | null) {return value === null ? "Chưa có dữ liệu" : value.toLocaleString("vi-VN", {maximumFractionDigits: 1});}
export function money(value: number | null) {return value === null ? "Chưa xác định" : `$${value.toLocaleString("en-US", {minimumFractionDigits: 6, maximumFractionDigits: 6})}`;}
export function time(value: string) {return new Date(value).toLocaleString("vi-VN", {timeZone: "UTC"}) + " UTC";}
