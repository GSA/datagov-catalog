from datetime import datetime
from unittest.mock import Mock, patch

from opensearchpy.exceptions import ConnectionTimeout, OpenSearchException
from sqlalchemy.exc import OperationalError

from app.models import Dataset
from tests.fixtures import HARVEST_RECORD_ID


def _insert_dataset(interface, dataset_id, last_harvested):
    dataset = Dataset(
        id=dataset_id,
        slug=dataset_id,
        dcat={"title": dataset_id},
        harvest_record_id=HARVEST_RECORD_ID,
        harvest_source_id="1",
        organization_id="1",
        last_harvested_date=last_harvested,
    )
    interface.db.add(dataset)
    interface.db.commit()
    return dataset


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

    def test_sync_logs_indexing_errors_from_single_page(
        self, cli_runner, interface_with_dataset, mock_opensearch_client
    ):
        """Test that errors from indexing are collected and displayed."""
        # Mock indexing with some errors
        test_errors = [
            {
                "dataset_id": "error-dataset-1",
                "status_code": 400,
                "error_type": "mapper_parsing_exception",
                "error_reason": "failed to parse field [dcat.modified]",
                "caused_by": {"type": "illegal_argument_exception"},
            },
            {
                "dataset_id": "error-dataset-2",
                "status_code": 429,
                "error_type": "es_rejected_execution_exception",
                "error_reason": "rejected execution of coordinating operation",
                "caused_by": None,
            },
        ]

        mock_opensearch_client.index_datasets = Mock(return_value=(98, 2, test_errors))

        with patch.object(Dataset, "query") as mock_query:
            mock_pagination = Mock()
            mock_pagination.pages = 1
            mock_pagination.items = [Mock()] * 100
            mock_query.paginate = Mock(return_value=mock_pagination)

            with patch(
                "app.commands.OpenSearchInterface.from_environment",
                return_value=mock_opensearch_client,
            ):
                result = cli_runner.invoke(args=["search", "sync", "--per_page", "100"])

        assert result.exit_code == 0
        assert "STATS" in result.output
        assert "Total Errors: 2" in result.output
        assert "=" * 20 + "ERRORS" in result.output

        # Check that error details are displayed
        assert "Dataset ID: error-dataset-1" in result.output
        assert "Status Code: 400" in result.output
        assert "Error Type: mapper_parsing_exception" in result.output
        assert "Error Reason: failed to parse field [dcat.modified]" in result.output
        assert "Caused By: {'type': 'illegal_argument_exception'}" in result.output

        assert "Dataset ID: error-dataset-2" in result.output
        assert "Status Code: 429" in result.output
        assert "Error Type: es_rejected_execution_exception" in result.output


class TestCompareCommand:
    @staticmethod
    def _prepare_environment(interface, hits, monkeypatch):
        monkeypatch.setattr("app.commands.CatalogDBInterface", lambda: interface)

        os_client = Mock()
        os_client.INDEX_NAME = "datasets"
        os_client.client = Mock()
        os_client.client.delete = Mock()
        os_client.index_datasets = Mock(return_value=(1, 0, 0))
        os_client._refresh = Mock()

        monkeypatch.setattr(
            "app.commands.OpenSearchInterface.from_environment",
            lambda: os_client,
        )
        monkeypatch.setattr(
            "app.commands.scan",
            lambda *args, **kwargs: iter(hits),
        )
        return os_client

    def test_compare_reports_discrepancies(
        self, cli_runner, interface_with_harvest_record, monkeypatch
    ):
        _insert_dataset(
            interface_with_harvest_record,
            "db-only",
            datetime(2024, 1, 1, 0, 0, 0),
        )
        _insert_dataset(
            interface_with_harvest_record,
            "stale",
            datetime(2024, 1, 2, 0, 0, 0),
        )

        hits = [
            {
                "_id": "stale",
                "_source": {"last_harvested_date": "2024-01-05T00:00:00Z"},
            },
            {"_id": "extra-only", "_source": {"last_harvested_date": None}},
        ]

        os_client = self._prepare_environment(
            interface_with_harvest_record, hits, monkeypatch
        )

        result = cli_runner.invoke(args=["search", "compare", "--sample-size", "5"])

        assert result.exit_code == 0
        assert "Missing in OpenSearch (should be indexed): 1" in result.output
        assert "Example missing IDs: db-only" in result.output
        assert "Extra in OpenSearch (should be deleted): 1" in result.output
        assert "Example extra IDs: extra-only" in result.output
        assert "Updated in OpenSearch (last_harvested_date differs): 1" in result.output
        assert "stale (DB: 2024-01-02T00:00:00.000+00:00" in result.output
        assert "OS: 2024-01-05T00:00:00.000+00:00" in result.output
        os_client.index_datasets.assert_not_called()
        os_client.client.delete.assert_not_called()
        os_client._refresh.assert_not_called()

    def test_compare_update_indexes_and_deletes(
        self, cli_runner, interface_with_harvest_record, monkeypatch
    ):
        _insert_dataset(
            interface_with_harvest_record,
            "db-only",
            datetime(2024, 2, 1, 0, 0, 0),
        )
        _insert_dataset(
            interface_with_harvest_record,
            "stale",
            datetime(2024, 2, 2, 0, 0, 0),
        )

        hits = [
            {
                "_id": "stale",
                "_source": {"last_harvested_date": "2024-02-05T00:00:00Z"},
            },
            {"_id": "extra-only", "_source": {"last_harvested_date": None}},
        ]

        os_client = self._prepare_environment(
            interface_with_harvest_record, hits, monkeypatch
        )

        result = cli_runner.invoke(args=["search", "compare", "--update"])
        assert result.exit_code == 0
        assert "Updating discrepancies" in result.output
        assert os_client.index_datasets.call_count == 2
        reindexed_sets = [
            {dataset.id for dataset in call.args[0]}
            for call in os_client.index_datasets.call_args_list
        ]
        assert {"db-only"} in reindexed_sets
        assert {"stale"} in reindexed_sets
        os_client.client.delete.assert_called_once()
        delete_call = os_client.client.delete.call_args
        assert delete_call.kwargs["id"] == "extra-only"
        os_client._refresh.assert_called_once()

    def test_compare_harvest_sources_known_on_dataset_error(
        self, cli_runner, interface_with_harvest_record, monkeypatch
    ):
        _insert_dataset(
            interface_with_harvest_record,
            "db-only",
            datetime(2024, 1, 1, 0, 0, 0),
        )
        hits = []

        os_client = self._prepare_environment(
            interface_with_harvest_record, hits, monkeypatch
        )

        test_errors = [
            {
                "dataset_id": "db-only",
                "status_code": 400,
                "error_type": "mapper_parsing_exception",
                "error_reason": "failed to parse field [dcat.modified]",
                "caused_by": {"type": "illegal_argument_exception"},
            }
        ]

        os_client.index_datasets = Mock(return_value=(98, 2, test_errors))

        result = cli_runner.invoke(args=["search", "compare", "--update"])

        assert (
            "Harvest sources not synced with opensearch...\n1 test-source"
            in result.output
        )

    def test_compare_force_update_reindexes_all_datasets(
        self, cli_runner, interface_with_harvest_record, monkeypatch
    ):
        _insert_dataset(
            interface_with_harvest_record,
            "current",
            datetime(2024, 3, 1, 0, 0, 0),
        )
        _insert_dataset(
            interface_with_harvest_record,
            "also-current",
            datetime(2024, 3, 2, 0, 0, 0),
        )

        hits = [
            {
                "_id": "current",
                "_source": {"last_harvested_date": "2024-03-01T00:00:00Z"},
            },
            {
                "_id": "also-current",
                "_source": {"last_harvested_date": "2024-03-02T00:00:00Z"},
            },
        ]

        os_client = self._prepare_environment(
            interface_with_harvest_record, hits, monkeypatch
        )

        result = cli_runner.invoke(args=["search", "compare", "--force-update"])

        assert result.exit_code == 0
        assert "Force re-indexing 2 datasets" in result.output
        assert os_client.index_datasets.call_count == 1
        reindexed_ids = {
            dataset.id for dataset in os_client.index_datasets.call_args.args[0]
        }
        assert reindexed_ids == {"current", "also-current"}
        os_client.client.delete.assert_not_called()
        os_client._refresh.assert_called_once()
