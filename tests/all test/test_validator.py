from src.ingestion.email_intake.validators import (
    run_all_validations,
    validate_extension,
    validate_filename,
    validate_size,
    validate_magic_bytes,
    validate_pdf_integrity,
    compute_content_hash,
)
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    target_filename = sys.argv[1] if len(sys.argv) > 1 else "Sang_DataEngineerintern_CV.pdf"
    file_path = PROJECT_ROOT / target_filename

    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    data = file_path.read_bytes()
    filename = file_path.name

    print(f"Checking: {filename}")
    print(f"Size: {len(data)} bytes")
    print("-" * 40)

    checks = {
        "extension": validate_extension(filename),
        "filename_format": validate_filename(filename),
        "size": validate_size(data),
        "magic_bytes": validate_magic_bytes(data),
        "pdf_integrity": validate_pdf_integrity(data),
    }

    for name, result in checks.items():
        status = "PASS" if result.is_valid else "FAIL"
        detail = f" ({result.reason})" if result.reason else ""
        print(f"[{status}] {name}{detail}")

    print("-" * 40)
    final = run_all_validations(filename, data)
    if final.is_valid:
        content_hash = compute_content_hash(data)
        print(f"RESULT: VALID")
        print(f"SHA256: {content_hash}")
    else:
        print(f"RESULT: INVALID -> {final.reason}")


if __name__ == "__main__":
    main()
