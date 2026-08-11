from langchain_core.documents import Document

from src.schemas.cv_schema import CVSchema


def build_documents_from_cv(cv_data: CVSchema, candidate_id: str, source_file: str) -> list[Document]:
    """Chunk theo section ngữ nghĩa"""
    docs: list[Document] = []
    for exp in cv_data.experience:
        period = f"{exp.start_date or '?'} - {exp.end_date or 'hiện tại'}"
        content = f"{exp.title} tại {exp.company} ({period})\n{exp.description or ''}".strip()
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "candidate_id": candidate_id,
                    "section_type": "experience",
                    "source_file": source_file,
                },
            )
        )

    for edu in cv_data.education:
        content = f"{edu.degree or ''} {edu.field or ''} tại {edu.school}".strip()
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "candidate_id": candidate_id,
                    "section_type": "education",
                    "source_file": source_file,
                },
            )
        )

    if cv_data.skills:
        docs.append(
            Document(
                page_content=", ".join(cv_data.skills),
                metadata={
                    "candidate_id": candidate_id,
                    "section_type": "skills",
                    "source_file": source_file,
                },
            )
        )
    return docs
