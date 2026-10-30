"""Initialize only the demo's bucket/collection after its migrations succeed."""
import time


def main():
    from src.storage.minio_client import MinioStorage
    from src.vectorstore.qdrant_client import QdrantStore

    for attempt in range(20):
        try:
            MinioStorage()
            QdrantStore().ensure_collection()
            print("Demo bucket and vector collection are ready.")
            return
        except Exception as error:
            if attempt == 19:
                raise SystemExit("Demo initialization failed: " + type(error).__name__) from None
            time.sleep(2)


if __name__ == "__main__":
    main()
