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


def test_search_with_keyword(interface_with_dataset):
    """Test searching datasets by exact keyword match."""
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(2):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        dataset_dict["dcat"]["title"] = f"test-{i}"
        dataset_dict["dcat"]["keyword"] =["health", "education"]
        interface_with_dataset.db.add(Dataset(**dataset_dict))
    interface_with_dataset.db.commit()

    # Index datasets in OpenSearch
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )
    # Search by single keyword
    result = interface_with_dataset.search_datasets(keywords=["health"])
    assert len(result) > 0
    assert all(
        "health" in dataset.get("dcat", {}).get("keyword", [])
        for dataset in result.results
    )

    # Search by multiple keywords
    result = interface_with_dataset.search_datasets(keywords=["health", "education"])
    assert len(result) > 0
    assert all(
        "health" in dataset.get("dcat", {}).get("keyword", []) and
        "education" in dataset.get("dcat", {}).get("keyword", [])
        for dataset in result.results
    )

    # Search by non-existent keyword
    result = interface_with_dataset.search_datasets(keywords=["nonexistent"])
    assert len(result) == 0
    assert result.results == []


def test_stop_words_removed_from_search_queries(interface_with_dataset):
    """Searching with stop words yields the same results as without them."""
    without_stop_word = interface_with_dataset.search_datasets("health food")
    with_stop_word = interface_with_dataset.search_datasets("health and food")

    assert without_stop_word.total > 0
    assert without_stop_word.total == with_stop_word.total
    assert {dataset["slug"] for dataset in without_stop_word.results} == {
        dataset["slug"] for dataset in with_stop_word.results
    }
    
