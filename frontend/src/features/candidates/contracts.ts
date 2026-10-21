import { z } from "zod";

export const candidateSchema = z.object({
  candidate_id: z.uuid(), full_name: z.string(), email: z.string().nullable(), has_photo: z.boolean(),
  applied_position: z.string().nullable(), total_years_experience: z.number().nullable(),
  skills: z.array(z.string()), created_at: z.string(), updated_at: z.string(),
  posting: z.object({posting_id: z.uuid(), position_title: z.string(), is_active: z.boolean(),
    department: z.object({department_id: z.uuid(), department_name: z.string()})}).nullable(),
});
export const candidateListSchema = z.object({items: z.array(candidateSchema), total: z.number().int().nonnegative(),
  page: z.number().int().positive(), page_size: z.number().int().positive(), total_pages: z.number().int().nonnegative(), has_next: z.boolean()});
const optionalText = z.string().nullable();
export const candidateDetailSchema = candidateSchema.extend({
  phone: optionalText, raw_text: optionalText,
  experience: z.array(z.object({company: optionalText, title: optionalText, start_date: optionalText, end_date: optionalText, description: optionalText})),
  education: z.array(z.object({school: optionalText, degree: optionalText, field: optionalText, graduation_year: z.number().int().nullable()})),
  certificates: z.array(z.object({name: z.string(), issuer: optionalText, issue_date: optionalText, credential_id: optionalText})),
  projects: z.array(z.object({name: z.string(), role: optionalText, tech_stack: z.array(z.string()), description: optionalText, start_date: optionalText, end_date: optionalText})),
});
export type Candidate = z.infer<typeof candidateSchema>;
export type SearchParams = Record<string, string | string[] | undefined>;
export function searchString(params: SearchParams) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) for (const item of Array.isArray(value) ? value : [value]) query.append(key, item);
  }
  return query.toString();
}
export function apiSearch(search: string) {
  const query = new URLSearchParams(search);
  query.delete("department_name"); query.delete("posting_name");
  return query.toString();
}
