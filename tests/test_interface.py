def test_get_organizations_includes_zero_dataset_orgs_with_opensearch_counts(
    interface_with_organization, monkeypatch
):
    monkeypatch.setattr(
        interface_with_organization.opensearch,
        "get_organization_counts",
        lambda size: [{"slug": "test-org", "count": 4}],
    )

    organizations = interface_with_organization.get_organizations()

    by_slug = {org["slug"]: org for org in organizations}
    assert "test-org" in by_slug, "Expected 'test-org' in organizations"
    assert "test-org-filtered" in by_slug

    assert by_slug["test-org"]["dataset_count"] == 4
    assert by_slug["test-org-filtered"]["dataset_count"] == 0


def test_get_organizations_db_fallback_includes_zero_dataset_orgs(
    interface_with_dataset, monkeypatch
):
    def _raise(size=None):
        raise RuntimeError("OpenSearch unavailable")

    monkeypatch.setattr(
        interface_with_dataset.opensearch, "get_organization_counts", _raise
    )

    organizations = interface_with_dataset.get_organizations()
    by_slug = {org["slug"]: org for org in organizations}

    # Assert both core fixture orgs are present regardless of any extra orgs
    # loaded from generated CSV fixtures (extra_orgs.csv).
    assert "test-org" in by_slug, "Expected 'test-org' in organizations"
    assert "test-org-filtered" in by_slug

    assert by_slug["test-org"]["dataset_count"] > 0
    assert by_slug["test-org-filtered"]["dataset_count"] == 0
