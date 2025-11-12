from app.models import Dataset


def test_search(interface_with_dataset):
    result = interface_with_dataset.search_datasets("test")
    assert len(result) > 0

    result = interface_with_dataset.search_datasets("description")
    assert len(result) > 0

    # no search results
    result = interface_with_dataset.search_datasets("nonexistentword")
    assert len(result) == 0


def test_multiple(interface_with_dataset):
    """Test multiple search terms format."""

    # "test" and "description" are both in the source document
    result = interface_with_dataset.search_datasets("test description")
    assert len(result) > 0

    # nonexistent isn't there so and should match nothing
    result = interface_with_dataset.search_datasets("test nonexistentword")
    assert len(result) == 0


def test_search_popularity_sort(interface_with_dataset):
    """Search returns results when using the popularity sort."""
    result = interface_with_dataset.search_datasets("test", sort_by="popularity")
    assert len(result) > 0


def test_search_by_keywords(interface_with_dataset):
    """Test searching datasets by exact keyword match."""
    # Search by single keyword
    result = interface_with_dataset.search_by_keywords(keywords=["health"])
    assert len(result) > 0
    assert any(
        "health" in dataset.get("dcat", {}).get("keyword", [])
        for dataset in result.results
    )

    # Search by multiple keywords
    result = interface_with_dataset.search_by_keywords(keywords=["health", "education"])
    assert len(result) > 0

    # Search by non-existent keyword
    result = interface_with_dataset.search_by_keywords(keywords=["nonexistent"])
    assert len(result) == 0
