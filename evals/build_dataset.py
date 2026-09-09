from langsmith import Client
import json
import sys

from dotenv import load_dotenv
load_dotenv()


sys.path.insert(0, ".")


EXTRACTION_DATASET_NAME = "cv-extraction-eval"
AGENT_DATASET_NAME = "cv-agent-tool-selection-eval"


def main():
    with open("evals/eval_data.json", encoding="utf-8") as f:
        data = json.load(f)

    client = Client()

    #  Dataset 1: Extraction
    extraction_examples = [
        ex for ex in data["extraction_examples"] if "_comment" not in ex
    ]
    if extraction_examples:
        if not client.has_dataset(dataset_name=EXTRACTION_DATASET_NAME):
            client.create_dataset(
                EXTRACTION_DATASET_NAME,
                description="Đánh giá độ chính xác LLM structured extraction từ CV thật",
            )
        client.create_examples(
            dataset_name=EXTRACTION_DATASET_NAME,
            examples=[
                {"inputs": {"raw_text": ex["raw_text"]}, "outputs": {"expected": ex["expected"]}}
                for ex in extraction_examples
            ],
        )
        print(f"Đã upload {len(extraction_examples)} example vào dataset '{EXTRACTION_DATASET_NAME}'")
    else:
        print("Không có extraction_examples hợp lệ (còn để nguyên template?) — bỏ qua.")

    # Dataset 2: Agent tool selection
    agent_examples = [ex for ex in data["agent_examples"] if "_comment" not in ex]
    if agent_examples:
        if not client.has_dataset(dataset_name=AGENT_DATASET_NAME):
            client.create_dataset(
                AGENT_DATASET_NAME,
                description="Đánh giá Agent có chọn đúng tool theo câu hỏi không",
            )
        client.create_examples(
            dataset_name=AGENT_DATASET_NAME,
            examples=[
                {
                    "inputs": {"question": ex["question"]},
                    "outputs": {"expected_tool": ex["expected_tool"]},
                }
                for ex in agent_examples
            ],
        )
        print(f"Đã upload {len(agent_examples)} example vào dataset '{AGENT_DATASET_NAME}'")
    else:
        print("Không có agent_examples hợp lệ — bỏ qua.")


if __name__ == "__main__":
    main()
