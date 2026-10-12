import argparse

from dotenv import load_dotenv
from langsmith import Client

from src.llm.prompt_store import DEFAULT_PROMPT_COMMITS, get_prompt_text


def configured_commits() -> list[tuple[str, str]]:
    from src.ops.optimization import active_config

    commits = list(DEFAULT_PROMPT_COMMITS.items())
    active_commit = active_config()["extraction_prompt_version"]
    active_extraction = ("cv-rag-extract-cv", active_commit)
    if active_extraction not in commits:
        commits.append(active_extraction)
    return commits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Đọc cấu hình Ops và liệt kê các commit, không kết nối LangSmith.",
    )
    args = parser.parse_args(argv)

    if not DEFAULT_PROMPT_COMMITS:
        parser.error("Chưa cấu hình commit prompt nào trong DEFAULT_PROMPT_COMMITS.")

    load_dotenv()
    try:
        commits = configured_commits()
    except Exception as exc:
        print(f"Không đọc được commit extraction đang active từ cấu hình Ops: {exc}")
        return 1

    if args.dry_run:
        for name, commit in commits:
            print(f"Sẽ kiểm tra: {name}:{commit}")
        return 0

    client = Client()
    failures = 0
    for name, commit in commits:
        identifier = f"{name}:{commit}"
        try:
            prompt = client.get_prompt(name)
            if prompt is None:
                print(f"Thiếu prompt: {name}")
                failures += 1
                continue
            if prompt.is_public:
                print(f"Prompt đang public: {name}")
                failures += 1
                continue

            pinned = client.pull_prompt_commit(identifier, skip_cache=True)
            if not pinned.commit_hash.startswith(commit):
                print(f"Sai commit: {identifier} -> {pinned.commit_hash}")
                failures += 1
                continue
            if not pinned.manifest or not get_prompt_text(name, commit=commit).strip():
                print(f"Prompt rỗng hoặc không đọc được: {identifier}")
                failures += 1
                continue
            print(f"OK (private): {name}:{pinned.commit_hash}")
        except Exception as exc:
            print(f"Không kiểm tra được {identifier}: {exc}")
            failures += 1

    print(f"Đã kiểm tra {len(commits)} phiên bản prompt; lỗi: {failures}.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
