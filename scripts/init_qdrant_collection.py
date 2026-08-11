# create collection cv_chunks trong qdrant + payload index

from src.vectorstore.qdrant_client import QdrantStore
import logging
import sys
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    store = QdrantStore()
    store.ensure_collection()
    logging.info("Qdrant collection sẵn sàng.")


if __name__ == '__main__':
    main()
