"""Unit tests for pipeline.gcs_client module with mocked GCS."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from google.cloud.exceptions import NotFound

from pipeline.gcs_client import (
    upload_markdown,
    read_markdown,
    list_files,
    get_previous_day_report,
    store_daily_report,
    _daily_report_path,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_storage_client():
    """Patch google.cloud.storage.Client and return mocks."""
    with patch("pipeline.gcs_client.storage.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        yield {
            "client_cls": mock_cls,
            "client": mock_client,
            "bucket": mock_bucket,
        }


@pytest.fixture
def mock_blob(mock_storage_client):
    """Create and return a mock blob attached to the mock bucket."""
    blob = MagicMock()
    mock_storage_client["bucket"].blob.return_value = blob
    return blob


# ---------------------------------------------------------------------------
# Tests: upload_markdown
# ---------------------------------------------------------------------------
class TestUploadMarkdown:
    def test_upload_success(self, mock_storage_client, mock_blob):
        content = "# Daily Report\nSome content here."
        path = "daily/h-voice/2026-03-24.md"

        result = upload_markdown(content, path)

        mock_storage_client["bucket"].blob.assert_called_once_with(path)
        mock_blob.upload_from_string.assert_called_once_with(
            content, content_type="text/markdown; charset=utf-8"
        )
        assert "gs://" in result
        assert path in result

    def test_upload_empty_content(self, mock_storage_client, mock_blob):
        result = upload_markdown("", "empty.md")
        mock_blob.upload_from_string.assert_called_once()
        assert "gs://" in result

    def test_upload_unicode(self, mock_storage_client, mock_blob):
        content = "# Report\n한국어 테스트 日本語テスト"
        result = upload_markdown(content, "unicode.md")
        mock_blob.upload_from_string.assert_called_once_with(
            content, content_type="text/markdown; charset=utf-8"
        )
        assert "gs://" in result


# ---------------------------------------------------------------------------
# Tests: read_markdown
# ---------------------------------------------------------------------------
class TestReadMarkdown:
    def test_read_existing_file(self, mock_storage_client, mock_blob):
        expected = "# Hello World"
        mock_blob.download_as_text.return_value = expected

        result = read_markdown("daily/h-voice/2026-03-24.md")

        assert result == expected
        mock_blob.download_as_text.assert_called_once_with(encoding="utf-8")

    def test_read_missing_file(self, mock_storage_client, mock_blob):
        mock_blob.download_as_text.side_effect = NotFound("not found")

        result = read_markdown("nonexistent.md")

        assert result is None

    def test_read_empty_file(self, mock_storage_client, mock_blob):
        mock_blob.download_as_text.return_value = ""

        result = read_markdown("empty.md")

        assert result == ""


# ---------------------------------------------------------------------------
# Tests: list_files
# ---------------------------------------------------------------------------
class TestListFiles:
    def test_list_files_returns_sorted(self, mock_storage_client):
        mock_blob_a = MagicMock()
        mock_blob_a.name = "daily/h-voice/2026-03-22.md"
        mock_blob_b = MagicMock()
        mock_blob_b.name = "daily/h-voice/2026-03-24.md"
        mock_blob_c = MagicMock()
        mock_blob_c.name = "daily/h-voice/2026-03-23.md"

        mock_storage_client["bucket"].list_blobs.return_value = [
            mock_blob_b,
            mock_blob_a,
            mock_blob_c,
        ]

        result = list_files("daily/h-voice/")

        assert result == [
            "daily/h-voice/2026-03-22.md",
            "daily/h-voice/2026-03-23.md",
            "daily/h-voice/2026-03-24.md",
        ]
        mock_storage_client["bucket"].list_blobs.assert_called_once_with(
            prefix="daily/h-voice/"
        )

    def test_list_files_empty(self, mock_storage_client):
        mock_storage_client["bucket"].list_blobs.return_value = []

        result = list_files("nonexistent-prefix/")

        assert result == []


# ---------------------------------------------------------------------------
# Tests: get_previous_day_report
# ---------------------------------------------------------------------------
class TestGetPreviousDayReport:
    def test_previous_day_found(self, mock_storage_client, mock_blob):
        expected = "# Previous day report"
        mock_blob.download_as_text.return_value = expected

        result = get_previous_day_report("2026-03-25")

        # Should fetch 2026-03-24
        mock_storage_client["bucket"].blob.assert_called_with(
            "daily/h-voice/2026-03-24.md"
        )
        assert result == expected

    def test_previous_day_not_found(self, mock_storage_client, mock_blob):
        mock_blob.download_as_text.side_effect = NotFound("not found")

        result = get_previous_day_report("2026-03-25")

        assert result is None

    def test_previous_day_across_month_boundary(self, mock_storage_client, mock_blob):
        expected = "# March 31 report"
        mock_blob.download_as_text.return_value = expected

        result = get_previous_day_report("2026-04-01")

        mock_storage_client["bucket"].blob.assert_called_with(
            "daily/h-voice/2026-03-31.md"
        )
        assert result == expected

    def test_invalid_date_format(self, mock_storage_client):
        result = get_previous_day_report("not-a-date")
        assert result is None

    def test_previous_day_year_boundary(self, mock_storage_client, mock_blob):
        expected = "# Dec 31 report"
        mock_blob.download_as_text.return_value = expected

        result = get_previous_day_report("2027-01-01")

        mock_storage_client["bucket"].blob.assert_called_with(
            "daily/h-voice/2026-12-31.md"
        )
        assert result == expected


# ---------------------------------------------------------------------------
# Tests: store_daily_report
# ---------------------------------------------------------------------------
class TestStoreDailyReport:
    def test_store_uses_correct_path(self, mock_storage_client, mock_blob):
        content = "# Report content"
        result = store_daily_report(content, "2026-03-24")

        expected_path = "daily/h-voice/2026-03-24.md"
        mock_storage_client["bucket"].blob.assert_called_with(expected_path)
        mock_blob.upload_from_string.assert_called_once_with(
            content, content_type="text/markdown; charset=utf-8"
        )
        assert "2026-03-24.md" in result


# ---------------------------------------------------------------------------
# Tests: _daily_report_path helper
# ---------------------------------------------------------------------------
class TestDailyReportPath:
    def test_path_format(self):
        path = _daily_report_path("2026-03-24")
        assert path == "daily/h-voice/2026-03-24.md"

    def test_path_preserves_date(self):
        path = _daily_report_path("2025-01-01")
        assert "2025-01-01" in path
