"""Load reviewed, immutable prompt revisions from LangSmith at runtime."""

import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langsmith import Client


# Update a commit only after reviewing and testing that LangSmith revision.
DEFAULT_PROMPT_COMMITS: dict[str, str] = {
    "cv-rag-classify-cv": "d5a2c949",
    "cv-rag-extract-cv": "55c22bda",
    "cv-rag-ocr-cv-image": "4a6978f9",
    "cv-rag-extract-jd": "954868c6",
    "cv-rag-agent-system": "73398ad0",
    "cv-rag-evaluate-candidate": "f51f3c34",
    "cv-rag-draft-interview-email": "5a7c8235",
    "cv-rag-generate-interview-questions": "fa79f34f",
    "cv-rag-optimization-analysis": "5727f34c",
}

_PROMPT_VARIABLES: dict[str, frozenset[str]] = {
    "cv-rag-classify-cv": frozenset({"text"}),
    "cv-rag-extract-cv": frozenset({"text"}),
    "cv-rag-ocr-cv-image": frozenset(),
    "cv-rag-extract-jd": frozenset({"text"}),
    "cv-rag-agent-system": frozenset(),
    "cv-rag-evaluate-candidate": frozenset({"criteria_list", "jd", "candidate_id", "profile"}),
    "cv-rag-draft-interview-email": frozenset({"candidate_name", "position", "interview_details"}),
    "cv-rag-generate-interview-questions": frozenset({"cv_text", "max_questions"}),
    "cv-rag-optimization-analysis": frozenset({"allowed_models", "usage_data"}),
}

_COMMIT_PATTERN = re.compile(r"[0-9a-fA-F]{8,40}\Z")


def get_prompt_commit(name: str) -> str:
    """Return the reviewed commit for a known application prompt."""
    try:
        return DEFAULT_PROMPT_COMMITS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown LangSmith prompt: {name}") from exc


def _resolve_commit(name: str, commit: str | None) -> str:
    default_commit = get_prompt_commit(name)
    pinned_commit = default_commit if commit is None else commit
    if not _COMMIT_PATTERN.fullmatch(pinned_commit):
        raise ValueError(f"LangSmith prompt {name} requires an immutable commit SHA")
    return pinned_commit


@lru_cache(maxsize=1)
def _get_client() -> Client:
    load_dotenv()
    return Client()


@lru_cache(maxsize=64)
def _pull_template(name: str, commit: str) -> PromptTemplate:
    prompt = _get_client().pull_prompt(f"{name}:{commit}")
    if not isinstance(prompt, PromptTemplate):
        raise TypeError(f"LangSmith prompt {name}:{commit} must be a text PromptTemplate")
    if prompt.template_format != "f-string":
        raise ValueError(f"LangSmith prompt {name}:{commit} must use f-string format")
    if not prompt.template.strip():
        raise ValueError(f"LangSmith prompt {name}:{commit} is empty")
    pulled_commit = (prompt.metadata or {}).get("lc_hub_commit_hash")
    if pulled_commit is not None and (
        not isinstance(pulled_commit, str)
        or not pulled_commit.lower().startswith(commit.lower())
    ):
        raise ValueError(
            f"LangSmith returned commit {pulled_commit!r} for requested {name}:{commit}"
        )
    expected = _PROMPT_VARIABLES[name]
    actual = frozenset(prompt.input_variables)
    if actual != expected:
        raise ValueError(
            f"LangSmith prompt {name}:{commit} variables {sorted(actual)} "
            f"do not match expected {sorted(expected)}"
        )
    return prompt


def get_prompt_text(name: str, *, commit: str | None = None) -> str:
    """Get raw template text for a known prompt at a pinned commit."""
    return _pull_template(name, _resolve_commit(name, commit)).template


def format_prompt(name: str, *, commit: str | None = None, **variables: object) -> str:
    """Fill a pinned LangSmith template with runtime values."""
    return _pull_template(name, _resolve_commit(name, commit)).format(**variables)
