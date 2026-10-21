import { z } from "zod";
export const departmentSchema = z.object({department_id: z.string(), department_name: z.string(), posting_count: z.number(), cv_count: z.number()});
export const postingSchema = z.object({posting_id: z.uuid(), department_id: z.string(), department_name: z.string(), position_title: z.string(), is_active: z.boolean(), cv_count: z.number(), created_at: z.string()});
export const accountSchema = z.object({user_id: z.string(), username: z.string(), role: z.enum(["admin", "tester"]), department_id: z.string().nullable(), department_name: z.string().nullable(), is_active: z.boolean(), created_at: z.string()});
export function pageSchema<T extends z.ZodType>(item: T) {return z.object({items: z.array(item), total: z.number(), page: z.number(), page_size: z.number(), has_next: z.boolean()});}
export const departmentsSchema = pageSchema(departmentSchema), postingsSchema = pageSchema(postingSchema), accountsSchema = pageSchema(accountSchema);
export type Posting = z.infer<typeof postingSchema>;
export type Department = z.infer<typeof departmentSchema>;
export type Account = z.infer<typeof accountSchema>;
