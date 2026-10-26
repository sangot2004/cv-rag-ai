import { z } from "zod";

export const userSchema = z.object({
  user_id: z.string(), username: z.string(), role: z.enum(["admin", "tester"]),
  department_id: z.string().nullable(),
});
export type User = z.infer<typeof userSchema>;
export const loginSchema = z.object({
  username: z.string().trim().min(1).max(100), password: z.string().min(1).max(256),
}).strict();
export const tokenSchema = z.object({
  access_token: z.string().min(1).max(3000), token_type: z.literal("bearer"),
  expires_at: z.string().datetime({ offset: true }), expires_in: z.number().int().positive(),
  user: userSchema,
});
export const criteriaSchema = z.object({
  position_title: z.string().trim().min(1).max(500),
  required_skills: z.array(z.string().trim().min(1).max(200)).max(100),
  min_years_experience: z.number().nonnegative().nullable(),
  preferred_education: z.string().max(1000).nullable(),
  top_k: z.number().int().min(1).max(10),
});
export type Criteria = z.infer<typeof criteriaSchema>;
// New IDs are UUIDs; older saved conversations may use names such as test-cart.
// Validate an opaque, URL-safe database key rather than enforcing UUID version.
export const threadIdSchema = z.string().min(1).max(36).refine(
  value => /^[A-Za-z0-9]/.test(value) && !/[^A-Za-z0-9_-]/.test(value),
  {message: "Mã hội thoại không hợp lệ."},
);
export const conversationSchema = z.object({
  thread_id: threadIdSchema, title: z.string(), created_at: z.string(), updated_at: z.string(),
});
export const conversationListSchema = z.object({items: z.array(conversationSchema), limit: z.number()});
export const candidateResultsSchema = z.array(z.object({
  kind: z.enum(["candidate_ranking", "candidate_evaluation"]), title: z.string(), unavailable: z.boolean(),
  items: z.array(z.object({candidate_id: z.string().uuid(), full_name: z.string(), applied_position: z.string().nullable(), rank: z.number().int().positive(),
    overall_score: z.number().min(1).max(5), summary: z.string(), strengths: z.array(z.string()), concerns: z.array(z.string()),
    criteria: z.array(z.object({criterion:z.string(),score:z.number().min(1).max(5),justification:z.string()})),
  })),
}));
export type CandidateResults = z.infer<typeof candidateResultsSchema>;
export const historySchema = z.object({
  thread_id: threadIdSchema,
  messages: z.array(z.object({id: z.string(), role: z.enum(["user", "assistant"]), content: z.string(), candidate_results: candidateResultsSchema.optional()})),
  pending_confirmations: z.array(z.object({confirmation_id: z.string(), type: z.literal("confirm_jd_criteria"), criteria: criteriaSchema.extend({
    // Read the backend's Criteria contract; tighter edit validation is applied
    // only when the user submits the form (CriteriaEdits).
    position_title: z.string().min(1).max(500),
    required_skills: z.array(z.string()).max(100),
    preferred_education: z.string().nullable(),
  })})),
  execution_status: z.enum(["idle", "running", "awaiting_confirmation", "failed", "interrupted"]),
});
export type History = z.infer<typeof historySchema>;
