"use client";
import { useId, useState, type FormEvent } from "react";
import { Check, X, ClipboardCheck } from "lucide-react";
import { criteriaSchema, type Criteria, type History } from "@/lib/contracts";

export function CriteriaForm({pending, disabled, onResume}: {
  pending: History["pending_confirmations"][number]; disabled: boolean;
  onResume: (id: string, confirmed: boolean, edits?: Partial<Criteria>) => void;
}) {
  const prefix = useId();
  const original = pending.criteria;
  const [title, setTitle] = useState(original.position_title);
  const [skills, setSkills] = useState(original.required_skills.join("\n"));
  const [years, setYears] = useState(original.min_years_experience?.toString() ?? "");
  const [education, setEducation] = useState(original.preferred_education ?? "");
  const [topK, setTopK] = useState(original.top_k.toString());
  const [error, setError] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    const result = criteriaSchema.safeParse({position_title: title, required_skills: skills.split("\n").map(s => s.trim()).filter(Boolean), min_years_experience: years === "" ? null : Number(years), preferred_education: education.trim() || null, top_k: Number(topK)});
    if (!result.success) { setError("Kiểm tra tiêu chí: tên vị trí không để trống; tối đa 100 kỹ năng, mỗi kỹ năng 200 ký tự; kinh nghiệm từ 0 và Top-K từ 1 đến 10."); return; }
    const edits: Record<string, unknown> = {};
    for (const key of Object.keys(result.data) as (keyof Criteria)[]) {
      if (JSON.stringify(result.data[key]) !== JSON.stringify(original[key])) edits[key] = result.data[key];
    }
    setError(""); onResume(pending.confirmation_id, true, edits as Partial<Criteria>);
  }
  return <section className="criteria-card"><header><ClipboardCheck size={22}/><div><h2>Xác nhận tiêu chí tuyển dụng</h2><p>Kiểm tra và điều chỉnh trước khi tìm ứng viên.</p></div></header>
    <form className="criteria-form" onSubmit={submit}><fieldset disabled={disabled}><legend className="sr-only">Tiêu chí tuyển dụng</legend>
      <div className="field"><label htmlFor={`${prefix}-title`}>Vị trí tuyển dụng</label><input id={`${prefix}-title`} value={title} onChange={e => setTitle(e.target.value)} required maxLength={500}/></div>
      <div className="field"><label htmlFor={`${prefix}-skills`}>Kỹ năng yêu cầu</label><textarea id={`${prefix}-skills`} value={skills} onChange={e => setSkills(e.target.value)} aria-describedby={`${prefix}-help`}/><small id={`${prefix}-help`}>Mỗi dòng một kỹ năng. Để trống nếu không yêu cầu.</small></div>
      <div className="field-row"><div className="field"><label htmlFor={`${prefix}-years`}>Số năm kinh nghiệm tối thiểu</label><input id={`${prefix}-years`} type="number" min="0" step="any" value={years} onChange={e => setYears(e.target.value)} placeholder="Không yêu cầu"/></div><div className="field"><label htmlFor={`${prefix}-top`}>Số ứng viên (Top-K)</label><input id={`${prefix}-top`} type="number" min="1" max="10" step="1" required value={topK} onChange={e => setTopK(e.target.value)}/></div></div>
      <div className="field"><label htmlFor={`${prefix}-education`}>Học vấn ưu tiên</label><input id={`${prefix}-education`} value={education} onChange={e => setEducation(e.target.value)} maxLength={1000} placeholder="Không yêu cầu"/></div>
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="criteria-actions"><button type="button" className="btn" onClick={() => onResume(pending.confirmation_id, false)}><X size={16}/>Hủy yêu cầu</button><button className="btn primary"><Check size={16}/>Xác nhận và tìm ứng viên</button></div>
    </fieldset></form></section>;
}
