"use client";
import Link from "next/link";
import { ArrowUpRight, Check, CircleAlert, Mail, Trophy } from "lucide-react";
import type { CandidateResults, User } from "@/lib/contracts";

export function CandidateResultCards({groups, userRole}: {groups: CandidateResults; userRole: User["role"]}) {
  return <div className="chat-results">{groups.map((group,index)=><section key={index} className="chat-result-group" aria-label={group.kind === "candidate_ranking" ? "Kết quả Top-K" : "Đánh giá theo JD"}>
    <header className="chat-results-heading"><Trophy size={18}/><div><h3>{group.title}</h3><p>{group.kind === "candidate_ranking" ? "Xếp hạng theo JD đã xác nhận" : "Đánh giá theo yêu cầu của bạn"} · Thang điểm 1–5</p></div></header>
    {group.unavailable && <p className="notice small">Một số hồ sơ không còn khả dụng trong phạm vi truy cập hiện tại.</p>}
    {!group.items.length && <p className="muted small">{group.unavailable ? "Không có hồ sơ có thể hiển thị." : "Không tìm thấy ứng viên phù hợp với tiêu chí đã chọn."}</p>}
    {group.items.map(item=><article className="chat-candidate-card" key={item.candidate_id}>
      <div className="chat-candidate-heading"><span className="chat-rank" aria-label={`Hạng ${item.rank}`}>{item.rank.toString().padStart(2,"0")}</span><div className="chat-candidate-name"><h4><Link href={`/candidates/${item.candidate_id}`}>{item.full_name}</Link></h4><p>{item.applied_position || "Chưa có vị trí ứng tuyển"}</p></div><div className="chat-score" aria-label={`Điểm phù hợp ${item.overall_score} trên 5`}><strong>{item.overall_score.toLocaleString("vi-VN",{maximumFractionDigits:1})}</strong><span>/ 5</span></div></div>
      <p className="chat-candidate-summary">{item.summary}</p>
      <div className="chat-candidate-notes">{!!item.strengths.length && <div><h5><Check size={15}/>Điểm mạnh</h5><ul>{item.strengths.map((text,i)=><li key={i}>{text}</li>)}</ul></div>}{!!item.concerns.length && <div><h5><CircleAlert size={15}/>Cần làm rõ</h5><ul>{item.concerns.map((text,i)=><li key={i}>{text}</li>)}</ul></div>}</div>
      {!!item.criteria.length && <details className="chat-score-details"><summary>Điểm và lý do theo từng tiêu chí</summary><div>{item.criteria.map((criterion,i)=><div className="chat-criterion" key={i}><div><strong>{criterion.criterion}</strong><span>{criterion.score}/5</span></div><meter min={1} max={5} value={criterion.score} aria-label={criterion.criterion}/><p>{criterion.justification}</p></div>)}</div></details>}
      <footer><span className="muted small">Kết quả tại thời điểm đánh giá</span><div className="chat-candidate-actions"><Link className="btn compact" href={`/candidates/${item.candidate_id}`}>Xem hồ sơ<ArrowUpRight size={15}/></Link>{userRole === "admin" && <Link className="btn primary compact" href={`/emails/compose?candidate=${item.candidate_id}`}><Mail size={15}/>Soạn thư mời</Link>}</div></footer>
    </article>)}
    <p className="muted small">Điểm và lý do do AI đánh giá từ CV; kiểm tra hồ sơ gốc trước khi quyết định.</p>
  </section>)}</div>;
}
