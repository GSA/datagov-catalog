from unittest.mock import Mock, patch

from opensearchpy.exceptions import ConnectionTimeout, OpenSearchException
from sqlalchemy.exc import OperationalError

from app.models import Dataset


class TestSyncCommand:
    """
    Test the sync command that is used to sync all datasets within the database
    to OpenSearch.
    """

    def test_search_sync_command(self, cli_runner):
        """Test to see the command executes as expected."""
        result = cli_runner.invoke(args=["search", "sync"])
        print(result.output)
        assert "Indexing..." in result.output
        assert " pages of datasets..." in result.output

    def test_sync_succeeds_on_first_attempt(
        self, cli_runner, interface_with_dataset, mock_opensearch_client
    ):
        """Test that sync succeeds without retries when no errors occur."""
        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 2
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(
                    args=["search", "sync", "--start-page", "1", "--per_page", "10"]
                )

        assert "Indexing..." in result.output
        assert "Sync was successful" in result.output
        assert result.exit_code == 0

    def test_sync_retries_on_opensearch_exception(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that sync retries on OpenSearchException and eventually succeeds."""
        # Mock time.sleep to avoid actual delays in tests
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        # Make index_datasets fail twice then succeed
        mock_opensearch_client.index_datasets = Mock(
            side_effect=[
                OpenSearchException("Connection error"),
                OpenSearchException("Connection error"),
                (100, 0, []),
            ]
        )

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(
                    args=["search", "sync", "--start-page", "1", "--per_page", "10"]
                )

        assert "Retrying in" in result.output
        assert "(attempt 1/4)" in result.output
        assert "(attempt 2/4)" in result.output
        assert "Sync was successful" in result.output
        assert result.exit_code == 0
        # Should have been called 3 times total
        assert mock_opensearch_client.index_datasets.call_count >= 3

    def test_sync_retries_on_serialization_failure(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """
        Test that sync retries on PostgreSQL serialization failure.
        """
        # Mock time.sleep to avoid actual delays in tests
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        # Create a mock OperationalError with serialization failure message
        serialization_error = OperationalError(
            "statement",
            "params",
            Exception("canceling statement due to conflict with recovery"),
        )

        # Make index_datasets fail once with serialization error, then succeed
        mock_opensearch_client.index_datasets = Mock(
            side_effect=[serialization_error, (100, 0, [])]
        )

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        assert "Database serialization conflict" in result.output
        assert "Retrying in" in result.output
        assert "Sync was successful" in result.output
        assert result.exit_code == 0

    def test_sync_fails_after_max_retries(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that sync fails after exhausting max retries (3 attempts)."""
        # Mock time.sleep in the commands module to avoid actual delays
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        # Make index_datasets always fail - use a callable that always raises
        def always_fail(*args, **kwargs):
            raise ConnectionTimeout("Persistent connection error")

        mock_opensearch_client.index_datasets = Mock(side_effect=always_fail)

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(
                    args=["search", "sync", "--start-page", "1", "--per_page", "10"]
                )

        assert "Failed after 4 attempts" in result.output
        assert "Sync failed after 4 attempts" in result.output
        assert result.exit_code != 0
        # Should have been called 4 times (initial + 3 retries)
        assert mock_opensearch_client.index_datasets.call_count >= 4

    def test_sync_exponential_backoff(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that retry delays use exponential backoff with 2.0s base."""
        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        monkeypatch.setattr("app.commands.time.sleep", mock_sleep)

        # Make index_datasets fail multiple times
        mock_opensearch_client.index_datasets = Mock(
            side_effect=[
                OpenSearchException("Error 1"),
                OpenSearchException("Error 2"),
                OpenSearchException("Error 3"),
                (100, 0, []),  # Success
            ]
        )

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(
                    args=["search", "sync", "--start-page", "1", "--per_page", "10"]
                )

        # Verify exponential backoff: 2.0, 4.0, 8.0 (base 2.0)
        assert len(sleep_calls) >= 3
        assert sleep_calls[0] == 2.0
        assert sleep_calls[1] == 4.0
        assert sleep_calls[2] == 8.0
        assert result.exit_code == 0

    def test_sync_multiple_pages_with_intermittent_failures(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test sync with multiple pages where some pages fail and retry."""
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        # Make page 2 fail once, others succeed
        call_count = {"count": 0}

        def index_side_effect(*args, **kwargs):
            call_count["count"] += 1
            # Fail on the second page's first attempt (call #2)
            if call_count["count"] == 2:
                raise OpenSearchException("Temporary error on page 2")
            return (100, 0, [])

        mock_opensearch_client.index_datasets = Mock(side_effect=index_side_effect)

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 2  # Multiple pages
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        # Should see retry message for page 2 but overall success
        assert "Retrying in" in result.output
        assert "Sync was successful" in result.output
        assert result.exit_code == 0

    def test_sync_preserves_error_details(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that error messages preserve useful debugging information."""
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        error_message = "Detailed connection error: timeout after 30s"

        # Make index_datasets always fail
        def always_fail(*args, **kwargs):
            raise ConnectionTimeout(error_message)

        mock_opensearch_client.index_datasets = Mock(side_effect=always_fail)

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        # Error output should include the error type
        assert "ConnectionTimeout" in result.output
        assert result.exit_code != 0

    def test_sync_handles_mixed_error_types(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that sync can recover from different types of errors."""
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        # Mix of database and OpenSearch errors
        serialization_error = OperationalError(
            "statement", "params", Exception("conflict with recovery")
        )

        mock_opensearch_client.index_datasets = Mock(
            side_effect=[
                serialization_error,
                OpenSearchException("Connection error"),
                (100, 0, []),  # Success
            ]
        )

        # Mock the paginate call to not raise error (only index_datasets should)
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        assert "Database serialization conflict" in result.output
        assert "Sync was successful" in result.output
        assert result.exit_code == 0

    def test_sync_retry_count_in_output(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that retry messages show correct attempt counts."""
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        mock_opensearch_client.index_datasets = Mock(
            side_effect=[
                OpenSearchException("Error 1"),
                OpenSearchException("Error 2"),
                (100, 0, []),
            ]
        )

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        # Should show attempt 1/4 and 2/4 (out of max 4 total attempts)
        # *Note: attempts are the initial try to query the db followed by 3 retries
        assert "(attempt 1/4)" in result.output
        assert "(attempt 2/4)" in result.output
        assert result.exit_code == 0

    def test_recreate_index_deletes_and_creates(
        self, cli_runner, interface_with_dataset, mock_opensearch_client
    ):
        """Test that --recreate-index deletes and recreates the index."""
        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(
                    args=["search", "sync", "--recreate-index", "--per_page", "10"]
                )

        assert "Deleting entire index to recreate with new schema..." in result.output
        assert "Creating index with new schema..." in result.output
        assert "Verified: keyword.raw field exists" in result.output
        mock_opensearch_client.client.indices.delete.assert_called_once()
        mock_opensearch_client._ensure_index.assert_called_once()
        assert result.exit_code == 0

    def test_without_recreate_index_preserves_schema(
        self, cli_runner, interface_with_dataset, mock_opensearch_client
    ):
        """Test that sync without --recreate-index keeps existing schema."""
        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        assert "Emptying dataset index (keeping existing schema)..." in result.output
        assert "Creating index with new schema..." not in result.output
        mock_opensearch_client.delete_all_datasets.assert_called_once()
        mock_opensearch_client.client.indices.delete.assert_not_called()
        assert result.exit_code == 0

    def test_serialization_error_message_format(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that serialization errors show clear message."""
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        serialization_error = OperationalError(
            "statement",
            "params",
            Exception("canceling statement due to conflict with recovery"),
        )

        mock_opensearch_client.index_datasets = Mock(
            side_effect=[serialization_error, (100, 0, [])]
        )

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        # Should specifically call out database serialization conflict
        assert "Database serialization conflict" in result.output
        assert "OperationalError" in result.output
        assert result.exit_code == 0

    def test_opensearch_error_message_format(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that OpenSearch errors show clear message."""
        monkeypatch.setattr("app.commands.time.sleep", lambda x: None)

        mock_opensearch_client.index_datasets = Mock(
            side_effect=[OpenSearchException("Connection failed"), (100, 0, [])]
        )

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        # Should show OpenSearchException but not call it serialization conflict
        assert "OpenSearchException" in result.output
        assert "Database serialization conflict" not in result.output
        assert result.exit_code == 0

    def test_retry_timing_shown_in_output(
        self, cli_runner, interface_with_dataset, mock_opensearch_client, monkeypatch
    ):
        """Test that retry messages show wait times."""
        sleep_calls = []
        monkeypatch.setattr("app.commands.time.sleep", lambda x: sleep_calls.append(x))

        mock_opensearch_client.index_datasets = Mock(
            side_effect=[OpenSearchException("Error"), (100, 0, [])]
        )

        # Mock Dataset.query to return pages with data
        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 10
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "10"])

        # Should show "Retrying in X.X seconds"
        assert "Retrying in 2.0 seconds..." in result.output
        assert result.exit_code == 0
