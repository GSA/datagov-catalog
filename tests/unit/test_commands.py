from datetime import datetime
from unittest.mock import Mock

from tests.helpers import add_dataset_with_harvest_record


def _insert_dataset(interface, dataset_id, last_harvested):
    dataset = add_dataset_with_harvest_record(
        interface,
        dict(
            id=dataset_id,
            slug=dataset_id,
            dcat={"title": dataset_id},
            harvest_source_id="1",
            organization_id="1",
            last_harvested_date=last_harvested,
        ),
    )
    interface.db.commit()
    return dataset


class TestCompareCommand:
    @staticmethod
    def _prepare_environment(interface, hits, monkeypatch):
        monkeypatch.setattr("app.commands.CatalogDBInterface", lambda s: interface)

        os_client = Mock()
        os_client.INDEX_NAME = "datasets"
        os_client.client = Mock()
        os_client.client.delete = Mock()
        os_client.index_datasets = Mock(return_value=(1, 0, 0))
        os_client._refresh = Mock()

        writer_mock = Mock()
        writer_mock.INDEX_NAME = "datasets"
        writer_mock.client = Mock()
        writer_mock.index_dataset_batches.return_value = None
        writer_mock.delete = Mock()

        monkeypatch.setattr(
            "app.commands.OpenSearchClient.from_environment",
            lambda: os_client,
        )
        monkeypatch.setattr(
            "app.commands.OpenSearchWriter",
            lambda *args, **kwargs: writer_mock,
        )

        monkeypatch.setattr(
            "app.commands.OpenSearchReader.scan_index",
            lambda *args, **kwargs: iter(hits),
        )
        return os_client, writer_mock

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

        os_client, _writer_mock = self._prepare_environment(
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

        os_client, writer_mock = self._prepare_environment(
            interface_with_harvest_record, hits, monkeypatch
        )

        result = cli_runner.invoke(args=["search", "compare", "--update"])
        assert result.exit_code == 0
        assert "Updating discrepancies" in result.output
        assert writer_mock.index_dataset_batches.call_count == 2
        reindexed_sets = [
            {dataset for dataset in call.args[0]}
            for call in writer_mock.index_dataset_batches.call_args_list
        ]
        assert {"db-only"} in reindexed_sets
        assert {"stale"} in reindexed_sets
        os_client.client.delete.assert_called_once()
        delete_call = os_client.client.delete.call_args
        assert delete_call.kwargs["id"] == "extra-only"
        writer_mock._refresh.assert_called_once()

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

        os_client, writer_mock = self._prepare_environment(
            interface_with_harvest_record, hits, monkeypatch
        )

        result = cli_runner.invoke(args=["search", "compare", "--force-update"])

        assert result.exit_code == 0
        # because of mocking "index_dataset_batches" the logs
        # from the data-access repo are swallowed
        assert writer_mock.index_dataset_batches.call_count == 1
        reindexed_ids = {
            dataset for dataset in writer_mock.index_dataset_batches.call_args.args[0]
        }
        assert reindexed_ids == {"current", "also-current"}
        writer_mock.client.delete.assert_not_called()
        writer_mock._refresh.assert_called_once()
