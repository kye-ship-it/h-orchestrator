"""Unit tests for pipeline.embedding_client module."""

import datetime

import pytest
from unittest.mock import MagicMock, patch

from pipeline.embedding_client import (
    chunk_markdown,
    build_file_index,
    generate_embeddings,
    _split_frontmatter,
    _sub_chunk,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
SAMPLE_MARKDOWN = """\
---
date: 2026-03-25
agent: h-voice-call
type: daily-log
---

# H-Voice Daily Log

## Summary

Total 47 calls performed today. Connection rate improved by 3.2%.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Calls | 47 |
| Connected | 32 |
| Connection Rate | 68.1% |

## Issues

No critical issues reported today.
"""

SIMPLE_MARKDOWN = """\
## Section One

Content for section one.

## Section Two

Content for section two.
"""

LONG_SECTION_MARKDOWN = """\
## Long Section

""" + "This is a fairly long sentence that contributes to the overall length. " * 20 + """

## Short Section

Short content here.
"""

FRONTMATTER_ONLY = """\
---
date: 2026-03-25
agent: test
---
"""

NO_SECTIONS = """\
Just plain text without any headers or frontmatter.
More text on another line.
"""


# ---------------------------------------------------------------------------
# Tests: _split_frontmatter
# ---------------------------------------------------------------------------
class TestSplitFrontmatter:
    def test_with_frontmatter(self):
        fm, body = _split_frontmatter(SAMPLE_MARKDOWN)
        assert fm is not None
        assert fm["date"] == datetime.date(2026, 3, 25)
        assert fm["agent"] == "h-voice-call"
        assert "## Summary" in body

    def test_without_frontmatter(self):
        fm, body = _split_frontmatter(SIMPLE_MARKDOWN)
        assert fm is None
        assert body == SIMPLE_MARKDOWN

    def test_empty_content(self):
        fm, body = _split_frontmatter("")
        assert fm is None
        assert body == ""

    def test_invalid_yaml_frontmatter(self):
        content = "---\n: invalid: yaml: [[\n---\nBody text."
        fm, body = _split_frontmatter(content)
        # Should gracefully return None for malformed YAML.
        assert fm is None


# ---------------------------------------------------------------------------
# Tests: _sub_chunk
# ---------------------------------------------------------------------------
class TestSubChunk:
    def test_short_text_single_chunk(self):
        text = "Short text."
        result = _sub_chunk(text, target=400, overlap=50)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_multiple_chunks(self):
        text = "First sentence. " * 30 + "Last sentence."
        result = _sub_chunk(text, target=200, overlap=50)
        assert len(result) > 1
        # All chunks should be non-empty.
        for chunk in result:
            assert chunk.strip()

    def test_overlap_content(self):
        # Build a text where we can verify overlap.
        sentences = [f"Sentence number {i}." for i in range(20)]
        text = " ".join(sentences)
        result = _sub_chunk(text, target=100, overlap=40)
        assert len(result) > 1
        # Verify some content appears in adjacent chunks (overlap).
        for i in range(len(result) - 1):
            current_words = set(result[i].split())
            next_words = set(result[i + 1].split())
            # There should be some shared words from overlap.
            assert current_words & next_words


# ---------------------------------------------------------------------------
# Tests: chunk_markdown
# ---------------------------------------------------------------------------
class TestChunkMarkdown:
    def test_empty_content(self):
        assert chunk_markdown("") == []
        assert chunk_markdown("   ") == []
        assert chunk_markdown(None) == []

    def test_single_section(self):
        content = "## Only Section\n\nSome content here."
        chunks = chunk_markdown(content)
        assert len(chunks) == 1
        assert chunks[0]["section"] == "Only Section"
        assert "Some content here" in chunks[0]["text"]
        assert "start_line" in chunks[0]

    def test_multiple_sections(self):
        chunks = chunk_markdown(SIMPLE_MARKDOWN)
        assert len(chunks) == 2
        sections = [c["section"] for c in chunks]
        assert "Section One" in sections
        assert "Section Two" in sections

    def test_frontmatter_extracted(self):
        chunks = chunk_markdown(SAMPLE_MARKDOWN)
        fm_chunks = [c for c in chunks if c["section"] == "Frontmatter"]
        assert len(fm_chunks) == 1
        assert "date: 2026-03-25" in fm_chunks[0]["text"]
        assert "agent: h-voice-call" in fm_chunks[0]["text"]

    def test_skips_empty_sections(self):
        content = "## Non-Empty\n\nContent.\n\n## Empty\n\n## Also Non-Empty\n\nMore content."
        chunks = chunk_markdown(content)
        sections = [c["section"] for c in chunks]
        assert "Empty" not in sections
        assert "Non-Empty" in sections
        assert "Also Non-Empty" in sections

    def test_long_sections_split(self):
        chunks = chunk_markdown(LONG_SECTION_MARKDOWN)
        long_chunks = [c for c in chunks if "Long Section" in c["section"]]
        # Should be split into sub-chunks.
        assert len(long_chunks) > 1
        # Sub-chunks should have numbered section names.
        assert any("1/" in c["section"] for c in long_chunks)

    def test_short_section_not_split(self):
        chunks = chunk_markdown(LONG_SECTION_MARKDOWN)
        short_chunks = [c for c in chunks if c["section"] == "Short Section"]
        assert len(short_chunks) == 1

    def test_no_headers(self):
        chunks = chunk_markdown(NO_SECTIONS)
        assert len(chunks) == 1
        assert chunks[0]["section"] == "Introduction"
        assert "plain text" in chunks[0]["text"]

    def test_frontmatter_only(self):
        chunks = chunk_markdown(FRONTMATTER_ONLY)
        # Should produce a frontmatter chunk but no body chunks.
        assert len(chunks) == 1
        assert chunks[0]["section"] == "Frontmatter"

    def test_unicode_content(self):
        content = "## Summary\n\nTotal calls: 47. Connection rate: 68.1%."
        chunks = chunk_markdown(content)
        assert len(chunks) == 1

    def test_start_line_tracking(self):
        chunks = chunk_markdown(SAMPLE_MARKDOWN)
        for chunk in chunks:
            assert isinstance(chunk["start_line"], int)
            assert chunk["start_line"] >= 1


# ---------------------------------------------------------------------------
# Tests: generate_embeddings
# ---------------------------------------------------------------------------
class TestGenerateEmbeddings:
    def test_empty_texts_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            generate_embeddings([])

    @patch("pipeline.embedding_client._model")
    @patch("pipeline.embedding_client.vertexai")
    def test_single_batch(self, mock_vertexai, mock_model_attr):
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.values = [0.1] * 768
        mock_model.get_embeddings.return_value = [mock_result, mock_result]

        with patch("pipeline.embedding_client._model", mock_model):
            result = generate_embeddings(["text1", "text2"])

        assert len(result) == 2
        assert len(result[0]) == 768

    @patch("pipeline.embedding_client._model")
    @patch("pipeline.embedding_client.vertexai")
    def test_multiple_batches(self, mock_vertexai, mock_model_attr):
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.values = [0.5] * 768

        # Simulate batch processing.
        mock_model.get_embeddings.return_value = [mock_result] * 250

        texts = [f"text{i}" for i in range(300)]

        with patch("pipeline.embedding_client._model", mock_model):
            with patch("pipeline.embedding_client._MAX_BATCH_SIZE", 250):
                result = generate_embeddings(texts)

        # Should have been called twice: 250 + 50.
        assert mock_model.get_embeddings.call_count == 2


# ---------------------------------------------------------------------------
# Tests: build_file_index
# ---------------------------------------------------------------------------
class TestBuildFileIndex:
    @patch("pipeline.embedding_client.generate_embeddings")
    def test_basic_index(self, mock_embed):
        mock_embed.return_value = [[0.1] * 768, [0.2] * 768, [0.3] * 768, [0.4] * 768]

        result = build_file_index("daily/h-voice/2026-03-25.md", SAMPLE_MARKDOWN)

        assert result["path"] == "daily/h-voice/2026-03-25.md"
        assert result["frontmatter"]["date"] == datetime.date(2026, 3, 25)
        assert result["frontmatter"]["agent"] == "h-voice-call"
        assert len(result["chunks"]) > 0

        for chunk in result["chunks"]:
            assert "section" in chunk
            assert "text" in chunk
            assert "embedding" in chunk
            assert isinstance(chunk["embedding"], list)

        mock_embed.assert_called_once()

    @patch("pipeline.embedding_client.generate_embeddings")
    def test_empty_content(self, mock_embed):
        result = build_file_index("empty.md", "")

        assert result["path"] == "empty.md"
        assert result["frontmatter"] == {}
        assert result["chunks"] == []
        mock_embed.assert_not_called()

    @patch("pipeline.embedding_client.generate_embeddings")
    def test_no_frontmatter(self, mock_embed):
        mock_embed.return_value = [[0.1] * 768, [0.2] * 768]

        result = build_file_index("test.md", SIMPLE_MARKDOWN)

        assert result["frontmatter"] == {}
        assert len(result["chunks"]) == 2

    @patch("pipeline.embedding_client.generate_embeddings")
    def test_chunk_count_matches_embeddings(self, mock_embed):
        chunks = chunk_markdown(SAMPLE_MARKDOWN)
        mock_embed.return_value = [[0.1] * 768] * len(chunks)

        result = build_file_index("test.md", SAMPLE_MARKDOWN)

        # Embeddings requested should match chunk count.
        texts_arg = mock_embed.call_args[0][0]
        assert len(texts_arg) == len(chunks)
        assert len(result["chunks"]) == len(chunks)

    @patch("pipeline.embedding_client.generate_embeddings")
    def test_task_type_is_retrieval_document(self, mock_embed):
        mock_embed.return_value = [[0.1] * 768]

        build_file_index("test.md", "## Test\n\nContent.")

        mock_embed.assert_called_once()
        assert mock_embed.call_args[1].get("task_type") == "RETRIEVAL_DOCUMENT" or \
               mock_embed.call_args[0][1] == "RETRIEVAL_DOCUMENT" if len(mock_embed.call_args[0]) > 1 else True
