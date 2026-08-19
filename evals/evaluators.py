"""
Evaluator functions theo đúng interface LangSmith yêu cầu:
    def evaluator(run, example) -> dict  (hoặc EvaluationResult)
run.outputs  = kết quả thật do target function trả về
example.outputs = đáp án đúng đã lưu trong Dataset
"""


def full_name_match(run, example) -> dict:
    actual = (run.outputs or {}).get("full_name", "")
    expected = example.outputs["expected"].get("full_name", "")
    score = 1.0 if actual.strip().lower() == expected.strip().lower() else 0.0
    return {"key": "full_name_match", "score": score}


def skills_overlap(run, example) -> dict:
    """So sánh tập kỹ năng — dùng overlap ratio thay vì exact match, vì LLM
    có thể diễn đạt khác chút (vd "SQL" vs "Structured Query Language") mà
    vẫn coi là đúng nếu đa số khớp.
    """
    actual = {s.strip().lower() for s in (run.outputs or {}).get("skills", [])}
    expected = {s.strip().lower() for s in example.outputs["expected"].get("skills", [])}
    if not expected:
        return {"key": "skills_overlap", "score": 1.0 if not actual else 0.5}

    overlap = len(actual & expected) / len(expected)
    return {"key": "skills_overlap", "score": round(overlap, 2)}


def experience_count_match(run, example) -> dict:
    actual = len((run.outputs or {}).get("experience", []))
    expected = example.outputs["expected"].get("num_experience_entries", 0)
    score = 1.0 if actual == expected else 0.0
    return {"key": "experience_count_match", "score": score}


def education_count_match(run, example) -> dict:
    actual = len((run.outputs or {}).get("education", []))
    expected = example.outputs["expected"].get("num_education_entries", 0)
    score = 1.0 if actual == expected else 0.0
    return {"key": "education_count_match", "score": score}


def year_experience_close_enough(run, example) -> dict:
    """LLM tính total_years_experience có thể lệch chút do làm tròn khác
    nhau — chấp nhận sai số 0.5 năm thay vì đòi khớp tuyệt đối.
    """
    actual = (run.outputs or {}).get("total_years_experience")
    expected = example.outputs["expected"].get("total_years_experience")
    if actual is None or expected is None:
        return {"key": "years_experience_close_enough", "score": 0.0}
    score = 1.0 if abs(actual - expected) <= 0.5 else 0.0
    return {"key": "years_experience_close_enough", "score": score}


EXTRACTION_EVALUATORS = [
    full_name_match,
    skills_overlap,
    experience_count_match,
    education_count_match,
    year_experience_close_enough,
]


def tool_selection_match(run, example) -> dict:
    actual_tool = (run.outputs or {}).get("tool_called")
    expected_tool = example.outputs["expected_tool"]
    score = 1.0 if actual_tool == expected_tool else 0.0
    return {
        "key": "tool_selection_match",
        "score": score,
        "comment": f"expected={expected_tool}, actual={actual_tool}"
    }


AGENT_EVALUATORS = [tool_selection_match]
