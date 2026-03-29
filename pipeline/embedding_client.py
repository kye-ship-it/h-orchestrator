"""Embedding client using Vertex AI text-embedding-005.

Provides markdown chunking and embedding generation for semantic search
(QMD) indexing of daily logs and reports.
"""

import logging
import re

import vertexai
import yaml
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

from config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    GCP_PROJECT,
    GEMINI_LOCATION,
)

logger = logging.getLogger(__name__)

_model: TextEmbeddingModel | None = None

# Vertex AI batching limit per API call.
_MAX_BATCH_SIZE = 250

# Chunking thresholds (characters).
_MAX_SECTION_LENGTH = 500
_SUB_CHUNK_TARGET = 400
_SUB_CHUNK_OVERLAP = 50


def _ensure_init() -> None:
    """Initialise Vertex AI SDK once per process."""
    global _model
    if _model is None:
        vertexai.init(project=GCP_PROJECT, location=GEMINI_LOCATION)
        _model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
        logger.info(
            "Initialised embedding model %s (dims=%d)",
            EMBEDDING_MODEL,
            EMBEDDING_DIMENSIONS,
        )


def generate_embeddings(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Generate embeddings for a list of texts using Vertex AI.

    Args:
        texts: Texts to embed.
        task_type: Vertex AI task type.

    Returns:
        List of embedding vectors (each 768-dim floats).
    """
    if not texts:
        raise ValueError("texts must be a non-empty list")

    _ensure_init()
    assert _model is not None

    all_embeddings: list[list[float]] = []

    for batch_start in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = texts[batch_start : batch_start + _MAX_BATCH_SIZE]
        inputs = [
            TextEmbeddingInput(text=t, task_type=task_type) for t in batch
        ]
        results = _model.get_embeddings(
            inputs,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )
        all_embeddings.extend(r.values for r in results)
        logger.debug(
            "Embedded batch %d-%d (%d texts)",
            batch_start,
            batch_start + len(batch),
            len(batch),
        )

    logger.info("Generated %d embeddings (task_type=%s)", len(all_embeddings), task_type)
    return all_embeddings


# ---------------------------------------------------------------------------
# Markdown chunking
# ---------------------------------------------------------------------------

def _split_frontmatter(content: str) -> tuple[dict | None, str]:
    """Separate YAML frontmatter from markdown body."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None, content

    try:
        fm = yaml.safe_load(match.group(1))
        if not isinstance(fm, dict):
            fm = None
    except yaml.YAMLError:
        logger.warning("Failed to parse frontmatter YAML")
        fm = None

    body = content[match.end() :]
    return fm, body


def _sub_chunk(text: str, target: int = _SUB_CHUNK_TARGET, overlap: int = _SUB_CHUNK_OVERLAP) -> list[str]:
    """Split a long text into overlapping sub-chunks at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?。])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) > target and current:
            chunks.append(" ".join(current))
            overlap_text = ""
            overlap_sentences: list[str] = []
            for s in reversed(current):
                if len(overlap_text) + len(s) > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_text = " ".join(overlap_sentences)
            current = overlap_sentences
            current_len = len(overlap_text)
        current.append(sentence)
        current_len += len(sentence)

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_markdown(content: str) -> list[dict]:
    """Split markdown content into section-based chunks for embedding."""
    if not content or not content.strip():
        return []

    chunks: list[dict] = []
    fm, body = _split_frontmatter(content)

    fm_lines = 0
    if fm is not None:
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(0)
            fm_lines = fm_text.count("\n")
            fm_summary_parts = [f"{k}: {v}" for k, v in fm.items()]
            fm_summary = "\n".join(fm_summary_parts)
            if fm_summary.strip():
                chunks.append({
                    "section": "Frontmatter",
                    "text": fm_summary,
                    "start_line": 1,
                })

    lines = body.split("\n")
    sections: list[tuple[str, int, list[str]]] = []
    current_section = "Introduction"
    current_start = fm_lines + 1
    current_lines: list[str] = []

    for i, line in enumerate(lines):
        header_match = re.match(r"^##\s+(.+)$", line)
        if header_match:
            if current_lines:
                sections.append((current_section, current_start, current_lines))
            current_section = header_match.group(1).strip()
            current_start = fm_lines + 1 + i
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_section, current_start, current_lines))

    for section_name, start_line, section_lines in sections:
        text = "\n".join(section_lines).strip()
        if not text:
            continue

        if len(text) > _MAX_SECTION_LENGTH:
            sub_chunks = _sub_chunk(text)
            for idx, sc in enumerate(sub_chunks):
                if sc.strip():
                    chunks.append({
                        "section": f"{section_name} ({idx + 1}/{len(sub_chunks)})",
                        "text": sc,
                        "start_line": start_line,
                    })
        else:
            chunks.append({
                "section": section_name,
                "text": text,
                "start_line": start_line,
            })

    return chunks


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

def build_file_index(path: str, content: str) -> dict:
    """Build a search index entry for a single markdown file."""
    fm, _ = _split_frontmatter(content)
    chunks = chunk_markdown(content)

    if not chunks:
        logger.warning("No chunks produced for %s", path)
        return {"path": path, "frontmatter": fm or {}, "chunks": []}

    texts = [c["text"] for c in chunks]
    embeddings = generate_embeddings(texts, task_type="RETRIEVAL_DOCUMENT")

    indexed_chunks = []
    for chunk, embedding in zip(chunks, embeddings):
        indexed_chunks.append({
            "section": chunk["section"],
            "text": chunk["text"],
            "embedding": embedding,
        })

    logger.info("Built index for %s: %d chunks", path, len(indexed_chunks))
    return {
        "path": path,
        "frontmatter": fm or {},
        "chunks": indexed_chunks,
    }
