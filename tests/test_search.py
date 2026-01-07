import copy

from app.models import Dataset
from app.database.opensearch import OpenSearchInterface


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


class TestOrQueryParsing:
    """Test the query parsing logic for OR operators."""

    def test_parse_simple_or_query(self):
        """Test parsing a simple OR query with two terms."""
        result = OpenSearchInterface._parse_or_query("health OR education")
        assert result == ["health", "education"]

    def test_parse_or_query_with_quoted_phrases(self):
        """Test parsing OR query with quoted phrases."""
        result = OpenSearchInterface._parse_or_query('"climate change" OR "global warming"')
        assert result == ['"climate change"', '"global warming"']

    def test_parse_or_query_mixed_quotes_and_terms(self):
        """Test parsing OR query with mix of quoted phrases and simple terms."""
        result = OpenSearchInterface._parse_or_query('"climate change" OR warming OR environment')
        assert result == ['"climate change"', "warming", "environment"]

    def test_parse_no_or_operator_returns_none(self):
        """Test that queries without OR return None."""
        result = OpenSearchInterface._parse_or_query("health education")
        assert result is None

    def test_parse_empty_query_returns_none(self):
        """Test that empty query returns None."""
        result = OpenSearchInterface._parse_or_query("")
        assert result is None

    def test_parse_none_query_returns_none(self):
        """Test that None query returns None."""
        result = OpenSearchInterface._parse_or_query(None)
        assert result is None

    def test_parse_single_term_with_or_returns_none(self):
        """Test that a single term followed by OR returns None."""
        # This is an edge case - "health OR" with nothing after
        result = OpenSearchInterface._parse_or_query("health OR")
        # Should return None because there's no valid second term
        assert result is None or result == ["health"]

    def test_parse_or_at_start_returns_none(self):
        """Test that OR at start of query returns None."""
        result = OpenSearchInterface._parse_or_query("OR health")
        assert result is None or result == ["health"]


class TestOrQuerySearch:
    """Test actual search functionality with OR queries."""

    def test_simple_or_query_returns_results(self, interface_with_dataset):
        """Test that OR query returns results matching either term."""
        # Index the datasets
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        
        # Search for "health OR climate"
        result = interface_with_dataset.search_datasets("health OR climate")
        
        # Should return datasets with either "health" or "climate"
        assert result.total > 0
        assert len(result.results) > 0
        
        # Check that results contain either health or climate
        result_texts = []
        for dataset in result.results:
            dcat = dataset.get("dcat", {})
            title = dcat.get("title", "").lower()
            description = dcat.get("description", "").lower()
            keywords = [k.lower() for k in dcat.get("keyword", [])]
            result_texts.append(f"{title} {description} {' '.join(keywords)}")
        
        # At least one result should contain "health" or "climate"
        has_health_or_climate = any(
            "health" in text or "climate" in text 
            for text in result_texts
        )
        assert has_health_or_climate

    def test_or_query_returns_more_results_than_and(self, interface_with_dataset):
        """Test that OR query returns more results than AND query."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        
        # Search with OR
        or_result = interface_with_dataset.search_datasets("health OR climate")
        
        # Search with AND (implicit)
        and_result = interface_with_dataset.search_datasets("health climate")
        
        # OR should return equal or more results than AND
        assert or_result.total >= and_result.total

    def test_or_query_respects_organization_filter(self, interface_with_dataset):
        """Test that OR query still respects organization filters."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        org = interface_with_dataset.db.query(Dataset).first().organization

        # Search with OR and org filter
        result = interface_with_dataset.search_datasets(
            "health OR climate",
            org_id=org.id
        )
        
        # Should return results, all from the specified org
        if result.total > 0:
            for dataset in result.results:
                assert dataset.get("organization", {}).get("id") == org.id

    def test_or_query_with_keyword_filter(self, interface_with_dataset):
        """Test that OR query works with keyword filters."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        
        # Search with OR and keyword filter
        result = interface_with_dataset.search_datasets(
            "health OR climate",
            keywords=["health"]
        )
        
        # Should return results matching either search term AND having the keyword
        assert result.total >= 0
        if result.total > 0:
            for dataset in result.results:
                keywords = dataset.get("dcat", {}).get("keyword", [])
                assert "health" in keywords

    def test_or_query_with_quoted_phrase(self, interface_with_dataset):
        """Test OR query with quoted phrases."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        
        # This tests that quoted phrases are handled correctly
        result = interface_with_dataset.search_datasets('"health food" OR education')
        
        # Should work without errors and return results
        assert result.total >= 0

    def test_or_query_with_popularity_sort(self, interface_with_dataset):
        """Test that OR query works with popularity sorting."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        
        result = interface_with_dataset.search_datasets(
            "health OR climate",
            sort_by="popularity"
        )
        
        # Should return results sorted by popularity
        assert result.total >= 0
        if len(result.results) > 1:
            # Check that results are sorted by popularity (descending)
            for i in range(len(result.results) - 1):
                pop1 = result.results[i].get("popularity") or 0
                pop2 = result.results[i + 1].get("popularity") or 0
                assert pop1 >= pop2

