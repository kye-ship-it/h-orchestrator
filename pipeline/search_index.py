"""GCS-backed embedding index for semantic search (QMD).

Manages a JSON index stored at ``index/embeddings.json`` in the configured
GCS bucket.
"""

import json
import logging

from config import GCS_INDEX_PATH
from embedding_client import build_file_index
from gcs_client import list_files, read_markdown, upload_markdown

logger = logging.getLogger(__name__)


def load_index() -> list[dict]:
    """Load the embedding index from GCS."""
    raw = read_markdown(GCS_INDEX_PATH)
    if raw is None:
        logger.info("No existing index found at %s; starting fresh", GCS_INDEX_PATH)
        return []

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            logger.warning("Index at %s is not a JSON array; resetting", GCS_INDEX_PATH)
            return []
        logger.info("Loaded index with %d entries from %s", len(data), GCS_INDEX_PATH)
        return data
    except json.JSONDecodeError:
        logger.error("Corrupt index at %s; resetting", GCS_INDEX_PATH)
        return []


def save_index(index: list[dict]) -> None:
    """Persist the embedding index to GCS as JSON."""
    payload = json.dumps(index, ensure_ascii=False)
    upload_markdown(payload, GCS_INDEX_PATH)
    logger.info("Saved index with %d entries to %s", len(index), GCS_INDEX_PATH)


def add_to_index(file_entry: dict) -> None:
    """Upsert a file entry in the index."""
    index = load_index()
    path = file_entry["path"]

    index = [e for e in index if e.get("path") != path]
    index.append(file_entry)

    save_index(index)
    logger.info("Upserted index entry for %s", path)


def remove_from_index(path: str) -> None:
    """Remove an entry from the index by its GCS path."""
    index = load_index()
    original_len = len(index)
    index = [e for e in index if e.get("path") != path]

    if len(index) < original_len:
        save_index(index)
        logger.info("Removed index entry for %s", path)
    else:
        logger.info("Path %s not found in index; nothing to remove", path)


def rebuild_index() -> list[dict]:
    """Rebuild the entire embedding index from all .md files in GCS."""
    from config import GCS_DAILY_PREFIX, GCS_REPORTS_PREFIX

    prefixes = [GCS_DAILY_PREFIX, GCS_REPORTS_PREFIX]
    all_paths: list[str] = []

    for prefix in prefixes:
        paths = list_files(prefix)
        md_paths = [p for p in paths if p.endswith(".md")]
        all_paths.extend(md_paths)

    logger.info("Rebuilding index: found %d .md files across prefixes %s", len(all_paths), prefixes)

    index: list[dict] = []
    for path in all_paths:
        content = read_markdown(path)
        if content is None:
            logger.warning("Skipping %s: could not read content", path)
            continue
        try:
            entry = build_file_index(path, content)
            index.append(entry)
        except Exception:
            logger.exception("Failed to build index entry for %s; skipping", path)

    save_index(index)
    logger.info("Index rebuild complete: %d entries", len(index))
    return index
