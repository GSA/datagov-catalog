import base64
import json

import pytest

from app.search.reader import InvalidCursorError, SearchResult


class TestDecodeSearchAfter:
    """Test cursor decoding validation."""

    def test_decode_search_after_with_valid_cursor(self):
        """Test decoding a valid base64 JSON cursor."""
        cursor_data = [1234567890, "dataset-id-123"]
        encoded = base64.urlsafe_b64encode(
            json.dumps(cursor_data).encode("utf-8")
        ).decode("utf-8")

        result = SearchResult.decode_search_after(encoded)

        assert result == cursor_data
        assert isinstance(result, list)
        assert len(result) == 2

    def test_decode_search_after_with_invalid_base64(self):
        """Test that invalid base64 raises InvalidCursorError."""
        invalid_cursor = "NOTAVALIDCURSOR!@#$"

        with pytest.raises(InvalidCursorError) as exc_info:
            SearchResult.decode_search_after(invalid_cursor)

        assert "Invalid cursor format" in str(exc_info.value)

    def test_decode_search_after_with_invalid_json(self):
        """Test that valid base64 but invalid JSON raises InvalidCursorError."""
        invalid_json = "not valid json at all"
        encoded = base64.urlsafe_b64encode(invalid_json.encode("utf-8")).decode("utf-8")

        with pytest.raises(InvalidCursorError) as exc_info:
            SearchResult.decode_search_after(encoded)

        assert "Invalid cursor format" in str(exc_info.value)

    def test_decode_search_after_with_non_list_value(self):
        """Test that valid JSON but wrong type raises InvalidCursorError."""
        wrong_type = {"key": "value"}
        encoded = base64.urlsafe_b64encode(
            json.dumps(wrong_type).encode("utf-8")
        ).decode("utf-8")

        with pytest.raises(InvalidCursorError) as exc_info:
            SearchResult.decode_search_after(encoded)

        assert "Invalid cursor format" in str(exc_info.value)

    def test_decode_search_after_with_invalid_utf8(self):
        """Test that invalid UTF-8 bytes raise InvalidCursorError."""
        invalid_bytes = b"\xff\xfe\xfd"
        encoded = base64.urlsafe_b64encode(invalid_bytes).decode("utf-8")

        with pytest.raises(InvalidCursorError) as exc_info:
            SearchResult.decode_search_after(encoded)

        assert "Invalid cursor format" in str(exc_info.value)

    def test_decode_search_after_with_empty_string(self):
        """Test that empty string raises InvalidCursorError."""
        with pytest.raises(InvalidCursorError) as exc_info:
            SearchResult.decode_search_after("")

        assert "Invalid cursor format" in str(exc_info.value)
