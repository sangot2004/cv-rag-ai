// Deterministic HTTP fixtures for BFF/browser tests. No database or model calls.
import http from "node:http";
import { createHash, randomUUID } from "node:crypto";
let sessions = new Map(), conversations = new Map(), questionSets = new Map(), versions = new Map(), emailBatches = new Map(), emailHistory = [], calls = [], mode = "normal";
let adminDepartments, adminPostings, adminAccounts, ingestionJobs, uploadHashes, assignments;
function resetAdmin() {
  adminDepartments = [{department_id: "11111111-1111-4111-8111-111111111111", department_name: "Engineering", posting_count: 1, cv_count: 22}, {department_id: "11111111-1111-4111-8111-222222222222", department_name: "Sales", posting_count: 0, cv_count: 0}];
  adminPostings = [{posting_id: "22222222-2222-4222-8222-222222222222", department_id: adminDepartments[0].department_id, department_name: "Engineering", position_title: "Data Engineer", is_active: true, cv_count: 22, created_at: new Date().toISOString()}];
  adminAccounts = [{user_id: "sang", username: "sang", role: "admin", department_id: null, department_name: null, is_active: true, created_at: new Date().toISOString()}];
  ingestionJobs = new Map(); uploadHashes = new Map(); assignments = new Map();
}
resetAdmin();
const criteria = {position_title: "Data Engineer", required_skills: ["Python", "SQL"], min_years_experience: 2, preferred_education: null, top_k: 3};
const server = http.createServer(async (req, res) => {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = Buffer.concat(chunks);
  let input;
  let uploaded;
  try {
    if (req.headers["content-type"]?.startsWith("multipart/form-data")) {
      const form = await new Response(body, {headers: {"Content-Type": req.headers["content-type"]}}).formData();
      uploaded = form.get("file"); input = {posting_id: form.get("posting_id"), filename: uploaded?.name};
    } else input = body.length ? JSON.parse(body.toString()) : {};
  } catch {res.writeHead(400).end(); return;}
  const url = new URL(req.url, "http://127.0.0.1:28101");
  const json = (status, data) => {res.writeHead(status, {"Content-Type": "application/json", "X-Request-ID": "test-request-id"}); res.end(data === undefined ? undefined : JSON.stringify(data));};
  const error = (status, code) => json(status, {error: {code, message: code, request_id: "test-request-id"}});
  if (url.pathname === "/health") return json(200, {ok: true});
  if (url.pathname === "/control/reset") {sessions = new Map(); conversations = new Map(); questionSets = new Map(); versions = new Map(); emailBatches = new Map(); emailHistory = []; calls = []; mode = "normal"; resetAdmin(); return json(200, {});}
  if (url.pathname === "/control/job-complete") {for (const job of ingestionJobs.values()) Object.assign(job, {status: input.status || "indexed", candidate_id: input.status === "dlq" ? null : "33333333-3333-4333-8333-000000000001", candidate_name: "Ada Nguyen", attempts: 1, can_retry: input.status === "dlq", error_code: input.status === "dlq" ? "INGESTION_FAILED" : null, dispatch_error: null}); return json(200, {});}
  if (url.pathname === "/control/mode") {mode = input.mode; return json(200, {});}
  if (url.pathname === "/control/revoke") {sessions.clear(); return json(200, {});}
  if (url.pathname === "/control/seed-legacy") {
    const item = {thread_id: "test-cart", title: "Hội thoại cũ của admin", created_at: new Date().toISOString(), updated_at: new Date().toISOString()};
    conversations.set(item.thread_id, {item, owner: "sang", messages: [], pending_confirmations: [], execution_status: "idle", deleted: false});
    return json(200, {});
  }
  if (url.pathname === "/control/email-complete") {
    for (const batch of emailBatches.values()) {
      for (const delivery of batch.deliveries) {
        delivery.status = input.status || "success";
        delivery.gmail_message_id = delivery.status === "success" ? "gmail-fixture" : null;
        delivery.error_code = delivery.status === "unknown" ? "DELIVERY_UNCONFIRMED" : delivery.status === "failed" ? "GMAIL_SETUP_FAILED" : null;
        delivery.finished_at = new Date().toISOString();
        const row = emailHistory.find(row => row.delivery_id === delivery.delivery_id);
        if (row) Object.assign(row, {status: delivery.status, gmail_message_id: delivery.gmail_message_id, error_code: delivery.error_code});
      }
      if (batch.deliveries.length) {
        batch.counts = Object.fromEntries(["queued", "sending", "success", "failed", "unknown"].map(key => [key, batch.deliveries.filter(d => d.status === key).length]));
        batch.status = batch.counts.failed || batch.counts.unknown ? "needs_attention" : "completed";
      }
    }
    return json(200, {});
  }
  if (url.pathname === "/control/calls") return json(200, calls);
  calls.push({method: req.method, path: url.pathname, query: url.search, body: url.pathname.includes("login") || (url.pathname === "/api/admin/users" && req.method === "POST") ? {} : input});
  if (url.pathname === "/api/auth/login") {
    if (input.password !== "test-password-123") return error(401, "AUTHENTICATION_REQUIRED");
    const account = adminAccounts.find(a => a.username === input.username);
    if (account && !account.is_active) return error(401, "AUTHENTICATION_REQUIRED");
    const user = {user_id: account?.user_id || input.username, username: input.username, role: account?.role || (input.username === "sang" ? "admin" : "tester"), department_id: account?.department_id || (input.username === "sang" ? null : "engineering")};
    const token = `test-only-${randomUUID()}`;
    sessions.set(token, user);
    return json(200, {access_token: token, token_type: "bearer", expires_in: 3600, expires_at: new Date(Date.now() + 3600000).toISOString(), user});
  }
  const token = req.headers.authorization?.replace(/^Bearer /, "");
  const user = sessions.get(token);
  if (!user) return error(401, "AUTHENTICATION_REQUIRED");
  if (url.pathname === "/api/auth/me") return json(200, user);
  if (url.pathname === "/api/auth/logout") {
    if (mode === "logout-down") return error(503, "DEPENDENCY_UNAVAILABLE");
    sessions.delete(token); return json(204);
  }
  const paginate = rows => {const page = Number(url.searchParams.get("page") || 1), page_size = Number(url.searchParams.get("page_size") || 20); return {items: rows.slice((page-1)*page_size,page*page_size), total: rows.length, page, page_size, has_next: page*page_size < rows.length};};
  if (url.pathname.startsWith("/api/admin/")) {
    if (user.role !== "admin") return error(403, "FORBIDDEN");
    if (mode === "admin-down") return error(503, "DEPENDENCY_UNAVAILABLE");
    const section = url.pathname.split("/")[3], rows = section === "departments" ? adminDepartments : section === "postings" ? adminPostings : adminAccounts;
    if (req.method === "GET") {
      let filtered = rows.filter(r => JSON.stringify(r).toLowerCase().includes((url.searchParams.get("q") || "").toLowerCase()));
      for (const key of ["department_id", "role"]) if (url.searchParams.has(key)) filtered = filtered.filter(r => r[key] === url.searchParams.get(key));
      if (url.searchParams.has("active")) filtered = filtered.filter(r => r.is_active === (url.searchParams.get("active") === "true"));
      return json(200, paginate(filtered));
    }
    if (url.pathname.endsWith("/active")) {
      const account = adminAccounts.find(a => a.user_id === url.pathname.split("/")[4]);
      if (!account) return error(404, "USER_NOT_FOUND");
      if (account.user_id === user.user_id) return error(409, "USER_STATE_CONFLICT");
      account.is_active = input.active;
      for (const [token, session] of sessions) if (session.user_id === account.user_id) sessions.delete(token);
      return json(200, {user_id: account.user_id, is_active: account.is_active});
    }
    if (section === "departments") {
      if (rows.some(r => r.department_name.toLowerCase() === input.department_name.toLowerCase())) return error(409, "DEPARTMENT_EXISTS");
      const row = {department_id: randomUUID(), department_name: input.department_name, posting_count: 0, cv_count: 0}; rows.push(row); return json(201,row);
    }
    const dept = adminDepartments.find(d => d.department_id === input.department_id);
    if (section === "postings") {
      if (!dept) return error(422, "DEPARTMENT_NOT_FOUND");
      const row = {posting_id: randomUUID(), ...input, department_name: dept.department_name, is_active: true, cv_count: 0, created_at: new Date().toISOString()}; rows.push(row); dept.posting_count++; return json(201,row);
    }
    if (rows.some(a => a.username === input.username)) return error(409, "USERNAME_EXISTS");
    const row = {user_id: randomUUID(), username: input.username, role: input.role, department_id: input.department_id, department_name: dept?.department_name || null, is_active: true, created_at: new Date().toISOString()}; rows.push(row); return json(201,row);
  }
  if (url.pathname.startsWith("/api/ingestion/")) {
    if (user.role !== "admin") return error(403, "FORBIDDEN");
    if (url.pathname.endsWith("/capabilities")) return json(200, {extensions: ["pdf"], min_bytes: 20480, max_bytes: 52428800, max_pages: 10, filename_pattern: "mock", filename_example: "NguyenVanA_DataEngineer_CV.pdf"});
    if (url.pathname.endsWith("/uploads")) {
      if (input.filename.includes("Invalid")) return error(422, "INVALID_FILENAME_FORMAT");
      const hash = createHash("sha256").update(Buffer.from(await uploaded.arrayBuffer())).digest("hex");
      if (uploadHashes.has(hash)) return json(202, ingestionJobs.get(uploadHashes.get(hash)));
      const posting = adminPostings.find(p => p.posting_id === input.posting_id);
      const row = {job_id: randomUUID(), original_filename: input.filename, source_type: "web_upload", status: "pending", attempts: 0, max_attempts: 3, error_code: null, dispatch_error: mode === "queue-down" ? "QUEUE_UNAVAILABLE" : null,
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(), started_at: null, candidate_id: null, candidate_name: null, posting_id: posting?.posting_id || null, position_title: posting?.position_title || null, department_name: posting?.department_name || null, can_retry: true};
      ingestionJobs.set(row.job_id,row); uploadHashes.set(hash,row.job_id); return json(202,row);
    }
    if (url.pathname === "/api/ingestion/jobs") {
      let rows = [...ingestionJobs.values()].reverse();
      for (const key of ["status", "source_type"]) if (url.searchParams.has(key)) rows = rows.filter(r => r[key] === url.searchParams.get(key));
      rows = rows.filter(r => r.original_filename.includes(url.searchParams.get("q") || ""));
      return json(200,paginate(rows));
    }
    const row = ingestionJobs.get(url.pathname.split("/")[4]);
    if (!row) return error(404,"JOB_NOT_FOUND");
    if (req.method === "POST") {
      if (mode === "job-busy") return error(409,"JOB_RUNNING");
      if (!row.can_retry) return error(409,"JOB_NOT_RETRYABLE");
      Object.assign(row,{status: "pending", attempts: 0, error_code: null, dispatch_error: null});
    }
    return json(200,row);
  }
  if (url.pathname.startsWith("/api/emails")) {
    if (user.role !== "admin") return error(403, "FORBIDDEN");
    const candidateInfo = id => {const n = Number(id.slice(-12)); return {candidate_id: id, full_name: n === 1 ? "Ada Nguyen" : `Ứng viên ${String(n).padStart(2, "0")}`, recipient_email: n === 1 ? "ada@example.test" : n === 2 ? "binh@example.test" : null};};
    const refreshPrior = batch => {batch.drafts.forEach(d => {d.previously_sent = emailHistory.some(e => e.recipient_email === d.recipient_email && e.status === "success");}); return batch;};
    if (url.pathname === "/api/emails/batches") {
      if (req.method === "GET") {
        const page = Number(url.searchParams.get("page") || 1), rows = [...emailBatches.values()].reverse();
        return json(200, {items: rows.slice((page-1)*20, page*20), total: rows.length, page, page_size: 20, has_next: page*20 < rows.length});
      }
      const existing = [...emailBatches.values()].find(b => b.request_id === input.request_id);
      if (existing) return json(200, refreshPrior(existing));
      const batch = {batch_id: randomUUID(), request_id: input.request_id, kind: input.kind, name: input.name, position: input.position, interview_details: input.interview_details, status: "draft", total: 0,
        counts: {queued: 0, sending: 0, success: 0, failed: 0, unknown: 0}, dispatch_error: null, created_at: new Date().toISOString(), deliveries: [],
        drafts: input.candidate_ids.map(id => ({...candidateInfo(id), draft_id: randomUUID(), subject: "", body: "", revision: 1, error_code: null, is_generating: false, ready: false, previously_sent: false}))};
      emailBatches.set(batch.batch_id, batch); return json(200, refreshPrior(batch));
    }
    const batchMatch = url.pathname.match(/^\/api\/emails\/batches\/([^/]+)(?:\/(dispatch|requeue))?$/);
    if (batchMatch) {
      const batch = emailBatches.get(batchMatch[1]); if (!batch) return error(404, "INVITATION_NOT_FOUND");
      if (req.method === "GET" || batchMatch[2] === "requeue") return json(200, refreshPrior(batch));
      if (batch.status !== "draft") return json(202, refreshPrior(batch));
      const selected = input.drafts.map(approval => batch.drafts.find(d => d.draft_id === approval.draft_id && d.revision === approval.revision));
      if (selected.some(d => !d)) return error(409, "STALE_EMAIL_DRAFT");
      if (selected.some(d => d.previously_sent) && !input.allow_previous) return error(409, "PREVIOUS_INVITATION");
      batch.deliveries = selected.map(d => ({delivery_id: randomUUID(), draft_id: d.draft_id, candidate_id: d.candidate_id, full_name: d.full_name, recipient_email: d.recipient_email, subject: d.subject, status: "queued", attempts: 0, error_code: null, gmail_message_id: null, started_at: null, finished_at: null}));
      batch.total = selected.length; batch.counts.queued = selected.length; batch.status = "queued";
      batch.deliveries.forEach(d => emailHistory.push({...d, id: emailHistory.length + 1, batch_id: batch.batch_id, body: batch.drafts.find(draft => draft.draft_id === d.draft_id).body, sent_at: new Date().toISOString()}));
      if (mode === "email-dispatch-timeout") return error(504, "DEPENDENCY_TIMEOUT");
      return json(202, batch);
    }
    const draftMatch = url.pathname.match(/^\/api\/emails\/drafts\/([^/]+)(?:\/(generate))?$/);
    if (draftMatch) {
      const batch = [...emailBatches.values()].find(b => b.drafts.some(d => d.draft_id === draftMatch[1]));
      if (!batch) return error(404, "INVITATION_NOT_FOUND");
      const draft = batch.drafts.find(d => d.draft_id === draftMatch[1]);
      if (batch.status !== "draft") return error(409, "BATCH_ALREADY_APPROVED");
      if (mode === "email-ai-fail" && draftMatch[2]) {draft.error_code = "AI_DRAFT_FAILED"; return error(503, "DEPENDENCY_UNAVAILABLE");}
      if (mode === "email-stale") {draft.revision++; mode = "normal"; return error(409, "STALE_EMAIL_DRAFT");}
      if (draft.revision !== input.expected_revision) return error(409, "STALE_EMAIL_DRAFT");
      Object.assign(draft, draftMatch[2] ? {subject: `Thư mời ${draft.full_name}`, body: `Xin chào ${draft.full_name},\nMời bạn phỏng vấn. <script>unsafe()</script>`} : {subject: input.subject, body: input.body});
      draft.revision++; draft.error_code = null; draft.ready = !!draft.recipient_email && !!draft.subject && !!draft.body;
      return json(200, refreshPrior(batch));
    }
    const deliveryMatch = url.pathname.match(/^\/api\/emails\/deliveries\/([^/]+)\/(retry|reconcile)$/);
    if (deliveryMatch) {
      const batch = [...emailBatches.values()].find(b => b.deliveries.some(d => d.delivery_id === deliveryMatch[1]));
      if (!batch) return error(404, "INVITATION_NOT_FOUND");
      const d = batch.deliveries.find(d => d.delivery_id === deliveryMatch[1]);
      if (deliveryMatch[2] === "retry" && d.status === "failed") {d.status = "queued"; batch.counts.failed--; batch.counts.queued++; batch.status = "queued";}
      if (deliveryMatch[2] === "reconcile" && d.status === "unknown") {d.status = "success"; batch.counts.unknown--; batch.counts.success++; batch.status = "completed";}
      return json(200, batch);
    }
    if (url.pathname === "/api/emails/history") {
      let rows = [...emailHistory].reverse().filter(row => (!url.searchParams.get("q") || `${row.full_name} ${row.subject} ${row.recipient_email}`.toLowerCase().includes(url.searchParams.get("q").toLowerCase())) && (!url.searchParams.get("status") || row.status === url.searchParams.get("status")));
      const page = Number(url.searchParams.get("page") || 1);
      return json(200, {items: rows.slice((page-1)*20, page*20), total: rows.length, page, page_size: 20, has_next: page*20 < rows.length});
    }
    const row = emailHistory.find(row => String(row.id) === url.pathname.split("/").at(-1));
    return row ? json(200, row) : error(404, "INVITATION_NOT_FOUND");
  }
  if (url.pathname.startsWith("/api/candidates")) {
    if (user.role !== "admin") return error(403, "FORBIDDEN");
    if (mode === "candidate-down") return error(503, "DEPENDENCY_UNAVAILABLE");
    if (mode === "candidate-bad") return json(200, {items: [{candidate_id: "bad"}]});
    const department = {department_id: "11111111-1111-4111-8111-111111111111", department_name: "Engineering"};
    const posting = {posting_id: "22222222-2222-4222-8222-222222222222", position_title: "Data Engineer", is_active: true, department};
    const rows = Array.from({length: 23}, (_, i) => ({candidate_id: `33333333-3333-4333-8333-${String(i + 1).padStart(12, "0")}`, full_name: i === 0 ? "Ada Nguyen" : `Ứng viên ${String(i + 1).padStart(2, "0")}`, email: i === 0 ? "ada@example.test" : i === 1 ? "binh@example.test" : null,
      has_photo: i < 2, applied_position: "Data Engineer", total_years_experience: i === 0 ? 0 : null, skills: ["Python", "SQL"], posting: i === 22 ? null : posting, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-02T00:00:00Z"}));
    for (const row of rows) if (assignments.has(row.candidate_id)) {const id = assignments.get(row.candidate_id), p = adminPostings.find(p => p.posting_id === id); row.posting = p ? {...p, department: {department_id: p.department_id, department_name: p.department_name}} : null;}
    if (url.pathname.endsWith("/posting")) {
      const id = url.pathname.split("/")[3], row = rows.find(r => r.candidate_id === id);
      if (!row) return error(404,"CANDIDATE_NOT_FOUND");
      if ((row.posting?.posting_id || null) !== input.expected_posting_id) return error(409,"CANDIDATE_ASSIGNMENT_CHANGED");
      assignments.set(id,input.posting_id); return json(200,{candidate_id:id, posting_id:input.posting_id});
    }
    const interviewMatch = url.pathname.match(/^\/api\/candidates\/([^/]+)\/interview-questions(?:\/(generate))?$/);
    if (interviewMatch) {
      const id = interviewMatch[1], c = rows.find(row => row.candidate_id === id);
      if (!c) return error(404, "CANDIDATE_NOT_FOUND");
      const has_cv = !id.endsWith("000000000023");
      const state = () => ({candidate_id: id, items: questionSets.get(id) || [], revision: (versions.get(id) || 0).toString(16).padStart(64, "0"), has_cv, is_generating: mode === "interview-busy"});
      if (req.method === "GET") return json(200, state());
      if (mode === "interview-busy") return error(409, "INTERVIEW_BUSY");
      if (mode === "interview-stale") {versions.set(id, (versions.get(id) || 0) + 1); mode = "normal"; return error(409, "STALE_INTERVIEW_SET");}
      const expected = req.method === "DELETE" ? url.searchParams.get("expected_revision") : input.expected_revision;
      if (expected !== state().revision) return error(409, "STALE_INTERVIEW_SET");
      if (req.method === "DELETE") {questionSets.set(id, []); versions.set(id, (versions.get(id) || 0) + 1); return json(200, state());}
      if (!has_cv) return error(422, "CANDIDATE_HAS_NO_CV");
      if (state().items.length && !input.replace_existing) return error(409, "INTERVIEW_REPLACE_REQUIRED");
      if (mode === "interview-fail") return error(503, "DEPENDENCY_UNAVAILABLE");
      if (mode === "interview-invalid") return error(422, "NO_VALID_INTERVIEW_QUESTIONS");
      const questions = ["Bạn đã sử dụng Python trong dự án như thế nào?", "Bạn thiết kế pipeline dữ liệu ra sao?", "Bạn trao đổi yêu cầu với đồng nghiệp như thế nào?"];
      questionSets.set(id, ["Technical", "System Design", "Soft Skill"].map((category, index) => ({id: index + 1, question: questions[index], category, cv_section: "Dự án", evidence_quote: "CV mẫu"})));
      versions.set(id, (versions.get(id) || 0) + 1);
      if (mode === "interview-uncertain") return error(504, "DEPENDENCY_TIMEOUT");
      return json(200, state());
    }
    if (url.pathname.endsWith("/photo")) {
      const candidateId = url.pathname.split("/").at(-2);
      const c = rows.find(row => row.candidate_id === candidateId);
      if (!c) return error(404, "CANDIDATE_NOT_FOUND");
      if (!c.has_photo || c !== rows[0] || mode === "photo-missing") return error(404, "CANDIDATE_PHOTO_NOT_FOUND");
      if (mode === "photo-down") return error(503, "DEPENDENCY_UNAVAILABLE");
      if (mode === "photo-bad") {res.writeHead(200, {"Content-Type": "text/html"}); return res.end("<h1>Invalid portrait</h1>");}
      res.writeHead(200, {"Content-Type": "image/png", "X-Request-ID": "portrait-request-id", "Cache-Control": "private, no-store"});
      return res.end(Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=", "base64"));
    }
    if (url.pathname !== "/api/candidates") {
      const c = rows.find(row => row.candidate_id === url.pathname.split("/").at(-1));
      if (!c) return error(404, "CANDIDATE_NOT_FOUND");
      return json(200, {...c, phone: null, raw_text: "CV mẫu <script>alert('unsafe')</script>", experience: [{company: "Example", title: "Data Intern", start_date: "2025-01-01", end_date: null, description: "Xây dựng pipeline dữ liệu."}], education: [], certificates: [{name: "Data Fundamentals", issuer: null, issue_date: null, credential_id: "ABC"}], projects: [{name: "CV Search", role: null, tech_stack: ["Python"], description: null, start_date: null, end_date: null}]});
    }
    let items = rows.filter(row => `${row.full_name} ${row.email || ""}`.toLowerCase().includes((url.searchParams.get("q") || "").toLowerCase()));
    if (url.searchParams.has("department_id")) items = items.filter(row => row.posting?.department.department_id === url.searchParams.get("department_id"));
    const page = Number(url.searchParams.get("page") || 1), page_size = Number(url.searchParams.get("page_size") || 20), total = items.length;
    return json(200, {items: items.slice((page-1)*page_size, page*page_size), total, page, page_size, total_pages: Math.ceil(total/page_size), has_next: page*page_size < total});
  }
  if (url.pathname === "/api/conversations") {
    if (req.method === "POST") {
      const item = {thread_id: randomUUID(), title: "Cuộc trò chuyện mới", created_at: new Date().toISOString(), updated_at: new Date().toISOString()};
      conversations.set(item.thread_id, {item, owner: user.user_id, messages: [], pending_confirmations: [], execution_status: "idle", deleted: false});
      return json(201, item);
    }
    const items = [...conversations.values()].filter(c => c.owner === user.user_id && !c.deleted).map(c => c.item);
    if (mode === "bad-list") items.push({thread_id: "bad/id", title: "Invalid row", created_at: new Date().toISOString(), updated_at: new Date().toISOString()});
    return json(200, {items, limit: 50});
  }
  const match = url.pathname.match(/^\/api\/conversations\/([^/]+)(?:\/(messages|resume|feedback))?$/);
  const c = conversations.get(match?.[1]);
  if (!c || c.owner !== user.user_id || (c.deleted && req.method !== "DELETE")) return error(404, "CONVERSATION_NOT_FOUND");
  if (req.method === "DELETE") {
    c.deleted = true;
    if (mode === "cleanup") {mode = "normal"; return error(503, "CONVERSATION_CLEANUP_PENDING");}
    conversations.delete(c.item.thread_id); return json(204);
  }
  if (req.method === "GET") return json(200, {thread_id: c.item.thread_id, messages: c.messages, pending_confirmations: c.pending_confirmations, execution_status: c.execution_status});
  if (match[2] === "messages") {
    if (c.execution_status === "failed") return error(409, "EXECUTION_INCOMPLETE");
    c.messages.push({id: randomUUID(), role: "user", content: input.question}); c.item.title = input.question.slice(0, 50);
    if (mode === "jd" || mode === "multiple") {
      c.pending_confirmations = [{confirmation_id: "confirm-1", type: "confirm_jd_criteria", criteria}, ...(mode === "multiple" ? [{confirmation_id: "confirm-2", type: "confirm_jd_criteria", criteria: {...criteria, position_title: "Backend Engineer"}}] : [])];
      c.execution_status = "awaiting_confirmation";
      return json(200, {type: "confirmation_required", thread_id: c.item.thread_id, pending_confirmations: c.pending_confirmations});
    }
    if (mode === "incomplete") {c.execution_status = "failed"; return error(503, "DEPENDENCY_UNAVAILABLE");}
    const message = {id: randomUUID(), role: "assistant", content: "Tìm thấy ứng viên có kỹ năng Python và SQL."};
    c.messages.push(message);
    if (mode === "uncertain") return error(504, "DEPENDENCY_TIMEOUT");
    return json(200, {type: "answer", thread_id: c.item.thread_id, message});
  }
  if (match[2] === "resume") {
    if (mode === "stale") {
      c.pending_confirmations[0].confirmation_id = "confirm-fresh"; mode = "jd";
      return error(409, "STALE_CONFIRMATION");
    }
    if (!c.pending_confirmations.some(p => p.confirmation_id === input.confirmation_id)) return error(409, "STALE_CONFIRMATION");
    c.pending_confirmations = c.pending_confirmations.filter(p => p.confirmation_id !== input.confirmation_id);
    c.execution_status = c.pending_confirmations.length ? "awaiting_confirmation" : "idle";
    if (!input.confirmed) return json(200, {type: "cancelled", thread_id: c.item.thread_id, message: null});
    const message = {id: randomUUID(), role: "assistant", content: "Đã tìm ứng viên theo tiêu chí được xác nhận."}; c.messages.push(message);
    return json(200, {type: "answer", thread_id: c.item.thread_id, message});
  }
  if (match[2] === "feedback") return json(201, input);
  return error(404, "NOT_FOUND");
});
server.listen(28101, "127.0.0.1");
