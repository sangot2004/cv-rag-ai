"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Coins, RefreshCw, Timer, X, Zap } from "lucide-react";
import { AdminWorkspace } from "@/components/admin-workspace";
import { Brand, ContentSkeleton, ErrorNotice } from "@/components/ui";
import { SessionGate } from "@/features/auth/session-gate";
import { api } from "@/lib/api";
import type { User } from "@/lib/contracts";
import { dashboardSchema, money, number, time, type Dashboard, type Usage } from "./contracts";

export function OpsApp({search}: {search: string}) {
  return <SessionGate>{user => user.role !== "admin" ? <main className="login-page"><section className="login-card"><Brand/><h1>Bạn chưa có quyền truy cập</h1><Link className="btn primary" href="/chat">Trở về hội thoại</Link></section></main> : <AdminWorkspace key={user.user_id} user={user} active="ops" title="Giám sát vận hành AI" mainId="ops-main"><DashboardView key={search} user={user} search={search}/></AdminWorkspace>}</SessionGate>;
}

function DashboardView({user, search}: {user: User; search: string}) {
  const router = useRouter(), params = new URLSearchParams(search);
  const [selected, setSelected] = useState<Usage | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const query = useQuery({queryKey: ["ops", user.user_id, search], queryFn: async ({signal}) => dashboardSchema.parse(await api(`/api/backend/ops/dashboard?${search}`, {signal}))});
  const data = query.data;
  function filter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const next = new URLSearchParams();
    new FormData(event.currentTarget).forEach((value, key) => {if (String(value)) next.set(key, String(value));});
    router.push(`/ops?${next}`);
  }
  function update(key: string, value: string) {const next = new URLSearchParams(search); next.set(key, value); if (key !== "page") next.delete("page"); router.push(`/ops?${next}`);}
  function inspect(row: Usage) {setSelected(row); dialog.current?.showModal();}
  return <>
    <Link className="btn" href="/ops/optimization">Đề xuất tối ưu và experiment</Link>
    <div className="candidate-page-title"><div><p className="eyebrow">System Ops</p><h1>Giám sát vận hành AI</h1><p className="muted">Theo dõi lượng sử dụng, chi phí và những lần gọi cần kiểm tra.</p></div><button className="btn" disabled={query.isFetching} onClick={() => query.refetch()}><RefreshCw size={16} className={query.isFetching ? "loading-icon" : undefined}/> {query.isFetching ? "Đang cập nhật…" : "Làm mới"}</button></div>
    <section className="candidate-card"><form className="management-filter ops-filter" aria-label="Bộ lọc Ops" onSubmit={filter}>
      <label className="field"><span>Khoảng thời gian</span><select aria-label="Khoảng thời gian" name="days" defaultValue={params.get("days") || "7"}>{[1,7,30].map(d => <option key={d} value={d}>{d} ngày gần nhất</option>)}</select></label>
      {([['module', 'Module', data?.options.modules], ['model', 'Model', data?.options.models], ['status', 'Trạng thái', data?.options.statuses]] as const).map(([key,label,values]) => <label key={key} className="field"><span>{label}</span><select aria-label={label} name={key} defaultValue={params.get(key) || ""}><option value="">Tất cả</option>{Array.from(new Set([...(values || []), ...(params.get(key) ? [params.get(key)!] : [])])).map(v => <option key={v} value={v}>{v}</option>)}</select></label>)}
      <button className="btn primary">Áp dụng</button><Link className="btn" href="/ops">Xóa bộ lọc</Link>
    </form>{data && <p className="muted small">{time(data.start)} — {time(data.end)} · Cập nhật gần nhất: {time(data.end)}</p>}</section>
    {query.error && <><ErrorNotice error={query.error}/>{data && <p className="muted small">Đang hiển thị dữ liệu của lần tải thành công trước. Bấm Làm mới để thử lại.</p>}</>}{query.isPending ? <ContentSkeleton cards/> : data && <>
      <div className="ops-kpis">
        <Metric icon={<Activity size={20}/>} label="Lần gọi AI" value={number(data.summary.calls)} note={`${number(data.summary.failover_calls)} calls ở lần failover tiếp theo`}/>
        <Metric icon={<Zap size={20}/>} label="Token đã ghi nhận" value={number(data.summary.input_tokens + data.summary.output_tokens)} note={`Input ${number(data.summary.input_tokens)} · Output ${number(data.summary.output_tokens)}`}/>
        <Metric icon={<Coins size={20}/>} label="Chi phí đã định giá (USD)" value={money(data.summary.estimated_cost_usd)} note={`${number(data.summary.calls - data.summary.priced_calls)} lần gọi chưa xác định chi phí`}/>
        <Metric icon={<Timer size={20}/>} label="Độ trễ p95 / lần gọi" value={data.summary.p95_ms === null ? "Chưa có dữ liệu" : `${number(data.summary.p95_ms)} ms`} note={`Median: ${number(data.summary.median_ms)}${data.summary.median_ms === null ? "" : " ms"}`}/>
      </div>
      <p className="muted small">Chi phí là ước tính theo giá lưu lúc gọi AI, không phải hóa đơn. Giá free tier bằng 0 được hiển thị $0.000000. Có {number(data.summary.missing_usage_calls)} lần gọi thiếu usage; tổng token chỉ gồm dữ liệu đã ghi nhận.</p>
      {!data.summary.calls && <p className="notice" role="status">Chưa có usage khớp bộ lọc. Thực hiện hỏi đáp hoặc xử lý CV, sau đó làm mới.</p>}
      <Trend data={data}/>
      <div className="ops-health">
        <section className="candidate-card"><h2>Cảnh báo theo quy tắc</h2><p className="ops-large">{number(data.alerts.count)} <span>lần gọi cần kiểm tra</span></p><p>Tỷ lệ lỗi: <strong>{data.summary.calls ? `${number(data.summary.error_calls / data.summary.calls * 100)}%` : "Chưa có dữ liệu"}</strong></p><p className="muted small">Call lỗi, độ trễ trên {number(data.alerts.latency_ms)} ms hoặc tổng input + output trên {number(data.alerts.tokens)} token.</p><button className="btn" onClick={() => update("alerts_only", "true")}>Xem các call cảnh báo</button></section>
        <section className="candidate-card"><h2>CV cần xử lý lại</h2><p className="ops-large">{number(data.dlq_count)} <span>tác vụ DLQ toàn hệ thống</span></p><p className="muted">Tác vụ đã hết số lần thử tự động. Chỉ số này không phụ thuộc bộ lọc usage.</p><Link className="btn" href="/ingestion/jobs?status=dlq">Kiểm tra tác vụ lỗi</Link></section>
      </div>
      <section className="candidate-card candidate-results"><div className="candidate-results-heading"><h2>Thống kê theo module và model</h2></div><div className="candidate-table-wrap"><table className="candidate-table management-table"><thead><tr><th>Module / Model</th><th>Lần gọi</th><th>Input / Output</th><th>Lỗi</th><th>Chi phí đã định giá</th></tr></thead><tbody>{data.breakdown.map(row => <tr key={`${row.module_name}:${row.model_name}`}><td><strong>{row.module_name}</strong><p className="muted small">{row.model_name}</p></td><td>{number(row.calls)}</td><td>{number(row.input_tokens)} / {number(row.output_tokens)}</td><td>{number(row.error_calls)}</td><td>{money(row.estimated_cost_usd)}<p className="muted small">{row.calls - row.priced_calls} call thiếu giá · {row.missing_usage_calls} thiếu usage</p></td></tr>)}</tbody></table></div>{!data.breakdown.length && <p className="candidate-empty">Chưa có dữ liệu thống kê.</p>}</section>
      <section className="candidate-card candidate-results"><div className="candidate-results-heading"><h2>Lịch sử gọi AI ({number(data.logs.total)})</h2><label><input type="checkbox" checked={params.get("alerts_only") === "true"} onChange={e => update("alerts_only", String(e.target.checked))}/> Chỉ xem cảnh báo</label></div><div className="candidate-table-wrap"><table className="candidate-table management-table"><thead><tr><th>Thời gian (UTC)</th><th>Module / Model</th><th>Trạng thái</th><th>Token input / output</th><th>Độ trễ</th><th>Chi phí</th><th>Chi tiết</th></tr></thead><tbody>{data.logs.items.map(row => <tr key={row.id}><td>{time(row.created_at)}</td><td>{row.module_name}<p className="muted small">{row.model_name}</p></td><td><span className={`badge ${row.status === "success" ? "success" : ""}`}>{row.status}</span></td><td>{number(row.input_tokens)} / {number(row.output_tokens)}</td><td>{number(row.latency_ms)} ms</td><td>{money(row.estimated_cost_usd)}</td><td><button className="btn compact" aria-label={`Chi tiết call ${row.id}`} onClick={() => inspect(row)}>Chi tiết</button></td></tr>)}</tbody></table></div>{!data.logs.items.length && <p className="candidate-empty">Không có call trong trang này.</p>}<div className="candidate-pagination"><span>Trang {data.logs.page} / {Math.max(1, Math.ceil(data.logs.total / data.logs.page_size))}</span><div><button className="btn compact" disabled={data.logs.page <= 1} onClick={() => update("page", String(data.logs.page - 1))}>Trang trước</button><button className="btn compact" disabled={!data.logs.has_next} onClick={() => update("page", String(data.logs.page + 1))}>Trang sau</button></div></div></section>
      <p className="muted small">Chưa có dữ liệu tỷ lệ cache Redis hoặc hạn ngạch RPM/TPM. Các số liệu trên phản ánh từng lần gọi AI, không phải thời gian hoàn tất toàn bộ yêu cầu.</p>
    </>}
    <dialog ref={dialog} className="email-confirm ops-dialog" aria-labelledby="ops-detail-title"><div className="candidate-results-heading"><h2 id="ops-detail-title">Chi tiết lần gọi AI</h2><button className="icon-button" aria-label="Đóng chi tiết" onClick={() => dialog.current?.close()}><X/></button></div>{selected && <><dl className="job-facts">{Object.entries({"Mã call": selected.id, "Operation ID": selected.operation_id, "Thời gian": time(selected.created_at), "Module": selected.module_name, "Model": selected.model_name, "Trạng thái": selected.status, "Lần thử": selected.attempt, "Input tokens": number(selected.input_tokens), "Output tokens": number(selected.output_tokens), "Cached tokens (provider)": number(selected.cached_tokens), "Reasoning tokens": number(selected.reasoning_tokens), "Độ trễ": `${number(selected.latency_ms)} ms`, "Chi phí ước tính": money(selected.estimated_cost_usd), "Phiên bản giá": selected.pricing_version}).map(([label,value]) => <div key={label} className="ops-fact"><dt>{label}</dt><dd>{value}</dd></div>)}</dl><p className="muted small">Cached tokens do nhà cung cấp báo cáo; không phải số lượt trúng cache Redis. Reasoning/cached tokens là dữ liệu bổ sung, không cộng thêm vào tổng input + output.</p></>}</dialog>
  </>;
}
function Metric({icon, label, value, note}: {icon: React.ReactNode; label: string; value: string; note: string}) {
  return <section className="candidate-card ops-metric"><div className="ops-metric-label">{icon}<h2>{label}</h2></div><p className="ops-large">{value}</p><p className="muted small">{note}</p></section>;
}
function Trend({data}: {data: Dashboard}) {
  const [metric, setMetric] = useState<"calls" | "tokens" | "cost">("calls");
  const [pointLabel, setPointLabel] = useState("");
  const daily = new Map(data.daily.map(row => [row.day, row]));
  const points: {day: string; value: number | null; missing: number}[] = [];
  const cursor = new Date(data.start.slice(0,10) + "T00:00:00Z"), last = data.end.slice(0,10);
  while (cursor.toISOString().slice(0,10) <= last) {
    const day = cursor.toISOString().slice(0,10), row = daily.get(day);
    points.push({day, value: !row ? 0 : metric === "calls" ? row.calls : metric === "tokens" ? row.input_tokens + row.output_tokens : row.estimated_cost_usd, missing: row ? metric === "cost" ? row.calls - row.priced_calls : metric === "tokens" ? row.missing_usage_calls : 0 : 0});
    cursor.setUTCDate(cursor.getUTCDate()+1);
  }
  const max = Math.max(1, ...points.map(p => p.value || 0));
  return <section className="candidate-card"><div className="candidate-results-heading"><h2>Xu hướng sử dụng theo ngày UTC</h2><select className="ops-chart-select" aria-label="Chỉ số biểu đồ" value={metric} onChange={e => {setMetric(e.target.value as typeof metric); setPointLabel("");}}><option value="calls">Lần gọi</option><option value="tokens">Token</option><option value="cost">Chi phí đã định giá</option></select></div><p className="muted small">Ngày đầu và cuối chỉ tính phần nằm trong khoảng đã chọn. Bấm cột để xem số liệu; ngày thiếu giá không được coi là $0.</p><div className="ops-chart" aria-label="Biểu đồ usage theo ngày">{points.map(p => <button key={p.day} className="ops-chart-column" title={`${p.day}: ${metric === "cost" ? money(p.value) : number(p.value)}${p.missing ? ` · ${p.missing} call thiếu dữ liệu` : ""}`} aria-label={`${p.day}: ${metric === "cost" ? money(p.value) : number(p.value)}${p.missing ? `; ${p.missing} call thiếu dữ liệu` : ""}`} onClick={e => setPointLabel(e.currentTarget.title)}><span className="ops-chart-tooltip">{p.day}: {metric === "cost" ? money(p.value) : number(p.value)}{p.missing > 0 && ` · ${p.missing} call thiếu dữ liệu`}</span><span className="ops-bar-space"><span className={`ops-bar ${p.missing ? "partial" : ""}`} style={{height: `${p.value === null ? 0 : Math.max(p.value > 0 ? 2 : 0, p.value / max * 100)}%`}}/>{p.value === null && <span className="ops-unknown">?</span>}</span><span className="ops-chart-date">{p.day.slice(5)}</span></button>)}</div><output className="muted small ops-chart-output" aria-live="polite">{pointLabel || (metric === "cost" ? "Chi phí chỉ gồm các call đã có giá." : "Dữ liệu trong khoảng thời gian đã chọn.")}</output></section>;
}
