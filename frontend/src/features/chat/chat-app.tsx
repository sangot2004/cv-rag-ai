"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileSearch, Plus, Search, LogOut, Menu, X, Send, ThumbsUp, ThumbsDown, Trash2, RefreshCw, ShieldCheck, MessageSquare } from "lucide-react";
import { SessionGate } from "@/features/auth/session-gate";
import { Brand, ErrorNotice, Loading } from "@/components/ui";
import { api, ApiError, broadcastSession, leaveSession } from "@/lib/api";
import { conversationListSchema, conversationSchema, historySchema, type User, type Criteria } from "@/lib/contracts";
import { CandidateResultCards } from "./candidate-results";
import { AssistantMarkdown } from "./assistant-markdown";
import { CriteriaForm } from "./criteria-form";

export function ChatApp({initialThread}: {initialThread?: string}) {
  return <SessionGate>{user => <Workspace key={user.user_id} user={user} initialThread={initialThread}/>}</SessionGate>;
}

function Workspace({user, initialThread}: {user: User; initialThread?: string}) {
  const client = useQueryClient();
  const [thread, setThread] = useState(initialThread || "");
  const [search, setSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState<unknown>(null);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [cleanupId, setCleanupId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [votes, setVotes] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const drawer = useRef<HTMLDialogElement>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const scrollArea = useRef<HTMLDivElement>(null);
  const listKey = ["conversations", user.user_id];
  const historyKey = ["history", user.user_id, thread];
  const list = useQuery({queryKey: listKey, queryFn: async ({signal}) => conversationListSchema.parse(await api("/api/backend/conversations?limit=50", {signal}))});
  const history = useQuery({queryKey: historyKey, enabled: !!thread, queryFn: async ({signal}) => historySchema.parse(await api(`/api/backend/conversations/${encodeURIComponent(thread)}/messages`, {signal})),
    refetchInterval: query => query.state.data?.execution_status === "running" ? 3000 : false});
  const data = history.data;
  const draft = drafts[thread] || "";
  const pending = data?.pending_confirmations || [];
  const incomplete = data?.execution_status === "failed" || data?.execution_status === "interrupted";
  const running = data?.execution_status === "running";
  const blocked = busy || needsRefresh || !!history.error || (!!thread && !data) || incomplete || running || pending.length > 0;
  const currentTitle = list.data?.items.find(item => item.thread_id === thread)?.title || (thread ? "Hội thoại" : "Cuộc trò chuyện mới");

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 768px)");
    const closeDrawer = () => { if (desktop.matches) drawer.current?.close(); };
    desktop.addEventListener("change", closeDrawer);
    return () => desktop.removeEventListener("change", closeDrawer);
  }, []);

  useEffect(() => {
    const pop = () => {
      if (busyRef.current) return;
      setThread(new URLSearchParams(window.location.search).get("thread") || ""); setError(null); setNeedsRefresh(false);
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  useEffect(() => { scrollArea.current?.scrollTo({top: scrollArea.current.scrollHeight, behavior: "instant"}); }, [thread, data?.messages.length, pending.length]);

  function select(id: string) {
    if (busyRef.current) return;
    setThread(id); setError(null); setNeedsRefresh(false); setNotice("");
    window.history.replaceState(null, "", id ? `/chat?thread=${encodeURIComponent(id)}` : "/chat");
    drawer.current?.close();
  }
  function setDraft(value: string) { setDrafts(old => ({...old, [thread]: value})); }
  async function refresh(id = thread) {
    if (id) {
      const fresh = historySchema.parse(await api(`/api/backend/conversations/${encodeURIComponent(id)}/messages`));
      client.setQueryData(["history", user.user_id, id], fresh);
      const lastQuestion = [...fresh.messages].reverse().find(message => message.role === "user")?.content;
      setDrafts(old => lastQuestion && old[id] === lastQuestion ? {...old, [id]: ""} : old);
    }
    await client.invalidateQueries({queryKey: listKey});
  }
  async function action(work: () => Promise<void>, uncertainOnFailure = true) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null); setNotice("");
    try { await work(); }
    catch (error) {
      setError(error);
      if (uncertainOnFailure && !(error instanceof ApiError && [400, 403, 404, 422].includes(error.status))) setNeedsRefresh(true);
    } finally { busyRef.current = false; setBusy(false); }
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (blocked || !draft.trim()) return;
    const question = draft;
    const draftKey = thread;
    await action(async () => {
      let id = thread;
      if (!id) {
        const created = conversationSchema.parse(await api("/api/backend/conversations", {method: "POST", body: {}}));
        id = created.thread_id; setThread(id);
        setDrafts(old => ({...old, [id]: question}));
        window.history.replaceState(null, "", `/chat?thread=${id}`);
      }
      await api(`/api/backend/conversations/${id}/messages`, {method: "POST", body: {question}});
      setDrafts(old => ({...old, [draftKey]: "", [id]: ""}));
      await refresh(id);
    });
  }
  async function resume(id: string, confirmed: boolean, edited_criteria?: Partial<Criteria>) {
    await action(async () => {
      await api(`/api/backend/conversations/${thread}/resume`, {method: "POST", body: {confirmation_id: id, confirmed, ...(confirmed && edited_criteria ? {edited_criteria} : {})}});
      await refresh();
      if (!confirmed) setNotice("Đã hủy yêu cầu này.");
    });
  }
  async function vote(messageId: string, feedback: "up" | "down") {
    const key = `${thread}:${messageId}`;
    if (votes[key]) return;
    await action(async () => {
      setVotes(old => ({...old, [key]: "pending"}));
      try {
        await api(`/api/backend/conversations/${thread}/feedback`, {method: "POST", body: {message_id: messageId, feedback}});
        setVotes(old => ({...old, [key]: "sent"}));
      } catch (error) {
        setVotes(old => ({...old, [key]: "uncertain"})); throw error;
      }
    }, false);
  }
  async function remove(id: string) {
    deleteDialog.current?.close();
    await action(async () => {
      try {
        await api(`/api/backend/conversations/${id}`, {method: "DELETE"});
        setCleanupId(null);
      } catch (error) {
        if (!(error instanceof ApiError && error.code === "CONVERSATION_CLEANUP_PENDING")) throw error;
        setCleanupId(id); setError(error);
      }
      client.removeQueries({queryKey: ["history", user.user_id, id]});
      setDrafts(old => { const next = {...old}; delete next[id]; return next; });
      if (thread === id) { setThread(""); window.history.replaceState(null, "", "/chat"); }
      await client.invalidateQueries({queryKey: listKey});
    }, false);
  }
  async function logout() {
    await action(async () => {
      await api("/api/session/logout", {method: "POST", body: {}});
      leaveSession("signed-out");
      await client.cancelQueries(); client.clear(); setDrafts({}); broadcastSession();
    }, false);
  }
  const sidebar = <>
    <div className="sidebar-top"><Brand/><button className="icon-button mobile-only" aria-label="Đóng danh sách hội thoại" onClick={() => drawer.current?.close()}><X size={20}/></button></div>
    <div className="sidebar-new"><button className="btn primary full" disabled={busy} onClick={() => select("")}><Plus size={18}/>Cuộc trò chuyện mới</button>{!busy && <Link className="btn full candidate-nav-link" href="/candidates">Ứng viên</Link>}{user.role === "admin" && !busy && <><Link className="btn full candidate-nav-link" href="/interviews">Câu hỏi phỏng vấn</Link><Link className="btn full candidate-nav-link" href="/emails/compose">Thư mời phỏng vấn</Link><Link className="btn full candidate-nav-link" href="/ingestion/upload">Tiếp nhận CV</Link><Link className="btn full candidate-nav-link" href="/ops">System Ops</Link><Link className="btn full candidate-nav-link" href="/admin/departments">Quản trị</Link></>}</div>
    <nav className="sidebar-content" aria-label="Lịch sử hội thoại"><div className="sidebar-label">Hội thoại của bạn</div><div className="history-search"><Search size={15}/><input aria-label="Tìm trong hội thoại đã tải" placeholder="Tìm hội thoại…" value={search} onChange={e => setSearch(e.target.value)}/></div>
      {list.isPending && <Loading/>}{list.error && <><ErrorNotice error={list.error}/><button className="btn compact" onClick={() => list.refetch()}>Tải lại danh sách</button></>}
      {list.data?.items.filter(item => item.title.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(item => <div className={`history-item ${item.thread_id === thread ? "active" : ""}`} key={item.thread_id}>
        <button className="history-open" disabled={busy} onClick={() => select(item.thread_id)} aria-current={item.thread_id === thread ? "page" : undefined}><strong>{item.title || "Cuộc trò chuyện mới"}</strong><small>{new Date(item.updated_at).toLocaleDateString("vi-VN")}</small></button>
        <button className="icon-button destructive" aria-label={`Xóa hội thoại ${item.title}`} disabled={busy || (item.thread_id === thread && !!running)} onClick={() => {setDeleteId(item.thread_id); deleteDialog.current?.showModal();}}><Trash2 size={15}/></button>
      </div>)}
      {list.data && !list.data.items.length && <p className="sidebar-note">Hội thoại mới sẽ xuất hiện ở đây khi bạn gửi câu hỏi.</p>}
      <p className="sidebar-note">Hiển thị tối đa 50 hội thoại gần nhất.</p>
    </nav>
    <div className="sidebar-footer"><div className="user-block"><span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span><div className="user-info"><strong>{user.username}</strong><small>{user.role === "admin" ? "Quản trị viên" : "Tester"}</small></div><button className="icon-button" aria-label="Đăng xuất" disabled={busy} onClick={logout}><LogOut size={18}/></button></div><p className="scope-caption">{user.role === "admin" ? "Tra cứu theo quyền quản trị" : "CV thuộc phòng ban được cấp"}</p></div>
  </>;
  return <div className="workspace"><a className="skip-link" href="#chat-main">Đến nội dung hội thoại</a>
    <aside className="sidebar desktop-sidebar">{sidebar}</aside>
    <dialog className="mobile-drawer" ref={drawer} aria-label="Hội thoại của bạn" onClick={event => {if (event.target === event.currentTarget) drawer.current?.close();}}><div className="drawer-content">{sidebar}</div></dialog>
    <main className="main-panel" id="chat-main"><header className="workspace-header"><button className="icon-button mobile-only" aria-label="Mở danh sách hội thoại" onClick={() => drawer.current?.showModal()}><Menu size={21}/></button><div className="header-title"><p className="eyebrow">Không gian làm việc</p><h1>{currentTitle}</h1><p className="header-subtitle">Tra cứu hồ sơ · Đối chiếu yêu cầu tuyển dụng</p></div><span className="badge">{user.role === "admin" ? "Admin" : "Tester"}</span></header>
    <div className="scroll-region" ref={scrollArea}><div className="chat-content">
      {error != null && <ErrorNotice error={error}/>}
      {cleanupId && <div className="notice warning"><div><strong>Hội thoại đã được ẩn</strong><p>Cần thử lại để hoàn tất dọn dữ liệu.</p><button className="btn compact" disabled={busy} onClick={() => remove(cleanupId)}>Hoàn tất xóa</button></div></div>}
      {notice && <p className="notice success" role="status">{notice}</p>}
      {!!thread && history.isPending && <Loading text="Đang tải hội thoại…"/>}
      {history.error && <><ErrorNotice error={history.error}/><button className="btn" onClick={() => history.refetch()}>Tải lại hội thoại</button></>}
      {!thread && <section className="welcome"><div className="welcome-mark"><FileSearch size={29}/></div><h2>Bắt đầu từ một câu hỏi</h2><p>Tìm ứng viên phù hợp, khám phá kinh nghiệm và đối chiếu hồ sơ với yêu cầu tuyển dụng.</p><div className="suggestions">{["Ứng viên nào biết Python?", "Liệt kê các ứng viên mới nhất.", "Tìm ứng viên Data Engineer có kỹ năng SQL."].map(text => <button className="suggestion" key={text} onClick={() => setDraft(text)} disabled={busy}><MessageSquare size={18}/>{text}</button>)}</div><p className="privacy-note"><ShieldCheck size={16}/>Hội thoại được lưu riêng cho tài khoản của bạn.</p></section>}
      {data?.messages.map(message => <article className={`message ${message.role}`} key={message.id}><span className="avatar"><FileSearch size={17}/></span><div className="message-content"><p className="message-label">{message.role === "user" ? "Bạn" : "Trợ lý CV"}</p>{message.role === "assistant" ? <AssistantMarkdown content={message.content}/> : <div className="message-text">{message.content}</div>}{message.role === "assistant" && !!message.candidate_results?.length && <CandidateResultCards groups={message.candidate_results}/>}{message.role === "assistant" && <div className="message-actions"><button className="icon-button" aria-label="Câu trả lời hữu ích" disabled={busy || !!votes[`${thread}:${message.id}`]} onClick={() => vote(message.id, "up")}><ThumbsUp size={15}/></button><button className="icon-button" aria-label="Câu trả lời chưa hữu ích" disabled={busy || !!votes[`${thread}:${message.id}`]} onClick={() => vote(message.id, "down")}><ThumbsDown size={15}/></button>{votes[`${thread}:${message.id}`] && <span className="vote-status">{votes[`${thread}:${message.id}`] === "sent" ? "Đã gửi đánh giá" : votes[`${thread}:${message.id}`] === "pending" ? "Đang gửi…" : "Chưa xác định được kết quả gửi"}</span>}</div>}</div></article>)}
      {pending.map(item => <CriteriaForm key={`${thread}:${item.confirmation_id}`} pending={item} disabled={busy || needsRefresh || !!history.error || !!running} onResume={resume}/>)}
      {(busy || running) && <Loading text="Đang xử lý yêu cầu…"/>}
      {(needsRefresh || running) && <section className="status-panel warning"><h2>Kiểm tra trạng thái hội thoại</h2><p>Yêu cầu có thể vẫn đang được xử lý. Kiểm tra kết quả trước khi gửi câu hỏi tiếp theo.</p><div className="status-actions"><button className="btn" disabled={busy} onClick={() => action(async () => {await refresh(); setNeedsRefresh(false);})}><RefreshCw size={16}/>Kiểm tra trạng thái</button></div></section>}
      {incomplete && <section className="status-panel warning"><h2>Lượt xử lý chưa hoàn tất</h2><p>Bạn có thể đọc lại lịch sử và mở cuộc trò chuyện mới để tiếp tục.</p><div className="status-actions"><button className="btn primary" onClick={() => select("")}>Mở cuộc trò chuyện mới</button></div></section>}
      {!!thread && data && !data.messages.length && !busy && <p className="notice">Hội thoại chưa có tin nhắn. Hãy nhập câu hỏi bên dưới.</p>}
    </div></div>
    <footer className={`composer-area ${blocked ? "compact" : ""}`}><div className="composer-inner">{blocked ? <p className="composer-guard" role="status">{pending.length ? "Xác nhận hoặc hủy các tiêu chí phía trên để tiếp tục." : incomplete ? "Mở cuộc trò chuyện mới để tiếp tục." : "Chờ xử lý hoặc kiểm tra lại trạng thái hội thoại để tiếp tục."}</p> : <form onSubmit={send}><div className="composer-box"><label className="sr-only" htmlFor="question">Câu hỏi của bạn</label><textarea id="question" value={draft} onChange={e => setDraft(e.target.value)} maxLength={20000} placeholder="Hỏi về ứng viên hoặc dán mô tả công việc…"/><div className="composer-bottom"><span className="char-count">{draft.length.toLocaleString("vi-VN")} / 20.000 ký tự</span><button className="btn primary compact" disabled={!draft.trim()}><Send size={15}/>Gửi câu hỏi</button></div></div><p className="composer-caption">Kiểm tra lại thông tin trong hồ sơ trước khi đưa ra quyết định.</p></form>}</div></footer>
    </main>
    <dialog ref={deleteDialog} aria-labelledby="delete-title"><h2 id="delete-title">Xóa hội thoại?</h2><p>Hội thoại và đánh giá liên quan sẽ được xóa khỏi lịch sử của bạn.</p><div className="dialog-actions"><button className="btn" onClick={() => deleteDialog.current?.close()}>Giữ lại</button><button className="btn danger" onClick={() => deleteId && remove(deleteId)}>Xóa hội thoại</button></div></dialog>
  </div>;
}
