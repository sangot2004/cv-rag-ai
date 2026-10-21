import { z } from "zod";
export const categoryLabels = {Technical: "Kỹ thuật", "System Design": "Thiết kế hệ thống", "Soft Skill": "Kỹ năng mềm"};
export const interviewSetSchema = z.object({
  candidate_id: z.uuid(), revision: z.string().regex(/^[a-f0-9]{64}$/), has_cv: z.boolean(), is_generating: z.boolean(),
  items: z.array(z.object({id: z.number().int(), question: z.string(), category: z.enum(["Technical", "System Design", "Soft Skill"]), cv_section: z.string(), evidence_quote: z.string()})),
});
export type InterviewSet = z.infer<typeof interviewSetSchema>;
