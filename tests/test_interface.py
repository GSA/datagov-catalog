def test_get_organizations_includes_zero_dataset_orgs_with_opensearch_counts(
    interface_with_organization, monkeypatch
):
    monkeypatch.setattr(
        interface_with_organization.opensearch,
        "get_organization_counts",
        lambda size: [{"slug": "test-org", "count": 4}],
    )

    organizations = interface_with_organization.get_organizations()

    assert len(organizations) == 2
    assert organizations[0]["slug"] == "test-org"

    by_slug = {org["slug"]: org for org in organizations}
    assert by_slug["test-org"]["dataset_count"] == 4
    assert by_slug["test-org-filtered"]["dataset_count"] == 0


def test_get_organizations_db_fallback_includes_zero_dataset_orgs(
    interface_with_dataset, monkeypatch
):
    def _raise(_size):
        raise RuntimeError("OpenSearch unavailable")

    monkeypatch.setattr(
        interface_with_dataset.opensearch, "get_organization_counts", _raise
    )

    organizations = interface_with_dataset.get_organizations()
    by_slug = {org["slug"]: org for org in organizations}

    assert len(organizations) == 2
    assert by_slug["test-org"]["dataset_count"] > 0
    assert by_slug["test-org-filtered"]["dataset_count"] == 0


def test_get_top_publishers_returns_top_100(interface_with_dataset, monkeypatch):
    captured_size = None

    def _get_publisher_counts(size):
        nonlocal captured_size
        captured_size = size
        return [
            {"name": "Agency Beta", "count": 1},
            {"name": "Agency Alpha", "count": 1},
        ]

    monkeypatch.setattr(
        interface_with_dataset.opensearch,
        "get_publisher_counts",
        _get_publisher_counts,
    )

    publishers = interface_with_dataset.get_top_publishers()

    assert captured_size == 100
    assert publishers == [
        {"name": "Agency Alpha", "count": 1},
        {"name": "Agency Beta", "count": 1},
    ]
