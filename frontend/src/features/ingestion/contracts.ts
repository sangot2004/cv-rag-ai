import { z } from "zod";
import { pageSchema } from "@/features/management/contracts";
export const jobSchema = z.object({job_id: z.uuid(), original_filename: z.string(), source_type: z.string(), status: z.string(), attempts: z.number(), max_attempts: z.number(), error_code: z.string().nullable(), dispatch_error: z.string().nullable(), created_at: z.string(), updated_at: z.string(), started_at: z.string().nullable(), candidate_id: z.string().nullable(), candidate_name: z.string().nullable(), posting_id: z.string().nullable(), position_title: z.string().nullable(), department_name: z.string().nullable(), can_retry: z.boolean()});
export const jobsSchema = pageSchema(jobSchema);
export const capabilitiesSchema = z.object({extensions: z.array(z.string()), min_bytes: z.number(), max_bytes: z.number(), max_pages: z.number(), filename_pattern: z.string(), filename_example: z.string()});
export type Job = z.infer<typeof jobSchema>;
export const jobLabels: Record<string, string> = {pending: "Chờ xử lý", processing: "Đang xử lý", failed: "Chờ thử lại", dlq: "Cần kiểm tra", rejected: "Bị từ chối", indexed: "Đã xử lý"};
export const jobErrors: Record<string, string> = {QUEUE_UNAVAILABLE: "Chưa đưa được vào hàng đợi. Kiểm tra Redis rồi đưa lại vào hàng đợi.", DUPLICATE_CV: "Nội dung CV đã có trong hệ thống.", CV_REJECTED: "File không đáp ứng điều kiện xử lý CV. Kiểm tra nội dung trước khi nộp file khác.", INGESTION_FAILED: "Xử lý chưa thành công. Kiểm tra worker và các dịch vụ phụ thuộc trước khi thử lại."};
export function jobError(code: string | null) {return code ? jobErrors[code] || "Tác vụ cần được quản trị viên kiểm tra." : "";}
export function dateTime(value: string | null) {return value ? new Date(value).toLocaleString("vi-VN", {timeZone: "Asia/Ho_Chi_Minh"}) : "—";}
