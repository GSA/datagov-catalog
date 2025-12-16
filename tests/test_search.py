import copy

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


def test_popularity_sort_orders_results(interface_with_dataset):
    """Explicit popularity sorting should beat relevance."""

    dataset_template = interface_with_dataset.db.query(Dataset).first().to_dict()

    def make_dataset(id_suffix, slug, popularity, title, description):
        dataset_data = copy.deepcopy(dataset_template)
        dataset_data["id"] = id_suffix
        dataset_data["slug"] = slug
        dataset_data["popularity"] = popularity
        dataset_data["dcat"]["title"] = title
        dataset_data["dcat"]["description"] = description
        return Dataset(**dataset_data)

    high_popularity_dataset = make_dataset(
        "popularity-dataset",
        "popularity-dataset",
        10_000,
        "Economic indicators dataset",
        "Contains the term test once for matching.",
    )

    high_score_dataset = make_dataset(
        "relevance-dataset",
        "relevance-dataset",
        5,
        "Test test test dataset for test search",
        "This dataset says test more than the other: test test test.",
    )

    interface_with_dataset.db.add(high_popularity_dataset)
    interface_with_dataset.db.add(high_score_dataset)
    interface_with_dataset.db.commit()
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )

    relevance_sorted = interface_with_dataset.search_datasets(
        "test", sort_by="relevance"
    )
    assert relevance_sorted.results[0]["slug"] == "relevance-dataset"

    popularity_sorted = interface_with_dataset.search_datasets(
        "test", sort_by="popularity"
    )
    assert popularity_sorted.results[0]["slug"] == "popularity-dataset"


def test_search_with_keyword(interface_with_dataset):
    """Test searching datasets by exact keyword match."""
    dataset_dict = interface_with_dataset.db.query(Dataset).first().to_dict()
    for i in range(2):
        dataset_dict["id"] = str(i)
        dataset_dict["slug"] = f"test-{i}"
        dataset_dict["dcat"]["title"] = f"test-{i}"
        dataset_dict["dcat"]["keyword"] = ["health", "education"]
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
        "health" in dataset.get("dcat", {}).get("keyword", [])
        and "education" in dataset.get("dcat", {}).get("keyword", [])
        for dataset in result.results
    )

    # Search by non-existent keyword
    result = interface_with_dataset.search_datasets(keywords=["nonexistent"])
    assert len(result) == 0
    assert result.results == []


def test_search_spatial_geometry(interface_with_dataset):
    """Search_datasets accepts spatial_geometry."""
    interface_with_dataset.opensearch.index_datasets(
        interface_with_dataset.db.query(Dataset)
    )
    results = interface_with_dataset.search_datasets(
        spatial_geometry={"type": "point", "coordinates": [-75, 40]},
        spatial_within=False,
    )
    assert len(results) > 0


def test_stop_words_removed_from_search_queries(interface_with_dataset):
    """Searching with stop words yields the same results as without them."""
    without_stop_word = interface_with_dataset.search_datasets("health food")
    with_stop_word = interface_with_dataset.search_datasets("health and food")

    assert without_stop_word.total > 0
    assert without_stop_word.total == with_stop_word.total
    assert {dataset["slug"] for dataset in without_stop_word.results} == {
        dataset["slug"] for dataset in with_stop_word.results
    }
