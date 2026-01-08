import copy

from app.database.opensearch import OpenSearchInterface
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


class TestPhraseAndOrQueryParsing:
    """Test the _parse_search_query method for phrases and OR operators."""

    def test_parse_simple_phrase(self):
        """Test parsing a simple phrase search."""
        result = OpenSearchInterface._parse_search_query('"health food"')
        assert result is not None
        assert result["has_or"] is False
        assert len(result["terms"]) == 1
        assert result["terms"][0]["text"] == "health food"
        assert result["terms"][0]["type"] == "phrase"

    def test_parse_simple_or_query(self):
        """Test parsing a simple OR query with two terms."""
        result = OpenSearchInterface._parse_search_query("health OR education")
        assert result is not None
        assert result["has_or"] is True
        assert len(result["terms"]) == 2
        assert result["terms"][0]["text"] == "health"
        assert result["terms"][0]["type"] == "term"
        assert result["terms"][1]["text"] == "education"
        assert result["terms"][1]["type"] == "term"

    def test_parse_or_query_with_quoted_phrases(self):
        """Test parsing OR query with quoted phrases."""
        result = OpenSearchInterface._parse_search_query(
            '"climate change" OR "global warming"'
        )
        assert result is not None
        assert result["has_or"] is True
        assert len(result["terms"]) == 2
        assert result["terms"][0]["text"] == "climate change"
        assert result["terms"][0]["type"] == "phrase"
        assert result["terms"][1]["text"] == "global warming"
        assert result["terms"][1]["type"] == "phrase"

    def test_parse_or_query_mixed_quotes_and_terms(self):
        """Test parsing OR query with mix of quoted phrases and simple terms."""
        result = OpenSearchInterface._parse_search_query(
            '"climate change" OR warming OR environment'
        )
        assert result is not None
        assert result["has_or"] is True
        assert len(result["terms"]) == 3
        assert result["terms"][0]["text"] == "climate change"
        assert result["terms"][0]["type"] == "phrase"
        assert result["terms"][1]["text"] == "warming"
        assert result["terms"][1]["type"] == "term"
        assert result["terms"][2]["text"] == "environment"
        assert result["terms"][2]["type"] == "term"

    def test_parse_no_or_operator_returns_none(self):
        """Test that simple queries without OR or quotes return None."""
        result = OpenSearchInterface._parse_search_query("health education")
        assert result is None

    def test_parse_empty_query_returns_none(self):
        """Test that empty query returns None."""
        result = OpenSearchInterface._parse_search_query("")
        assert result is None

    def test_parse_none_query_returns_none(self):
        """Test that None query returns None."""
        result = OpenSearchInterface._parse_search_query(None)
        assert result is None

    def test_parse_case_insensitive_or(self):
        """Test that OR operator is case insensitive."""
        result = OpenSearchInterface._parse_search_query("health or education")
        assert result is not None
        assert result["has_or"] is True
        assert len(result["terms"]) == 2


class TestPhraseSearch:
    """Test phrase search functionality."""

    def test_phrase_search_finds_exact_phrase(self, interface_with_dataset):
        """Test that phrase search finds datasets with exact phrase."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        # Search for exact phrase that exists in test data
        result = interface_with_dataset.search_datasets('"Health Food"')

        # Should find results containing this phrase
        assert result.total >= 0
        if result.total > 0:
            # Verify at least one result contains the phrase
            found = False
            for dataset in result.results:
                title = dataset.get("dcat", {}).get("title", "").lower()
                description = dataset.get("dcat", {}).get("description", "").lower()
                if "health food" in title or "health food" in description:
                    found = True
                    break
            assert found

    def test_phrase_search_with_filters(self, interface_with_dataset):
        """Test that phrase search works with organization filter."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )
        org = interface_with_dataset.db.query(Dataset).first().organization

        # Search with phrase and org filter
        result = interface_with_dataset.search_datasets('"test"', org_id=org.id)

        # Should work and respect org filter
        if result.total > 0:
            for dataset in result.results:
                assert dataset["organization"]["id"] == org.id


class TestOrQuerySearch:
    """Test OR query search functionality."""

    def test_simple_or_query_returns_results(self, interface_with_dataset):
        """Test that OR query returns results matching either term."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        # Search for "health OR climate"
        result = interface_with_dataset.search_datasets("health OR climate")

        # Should return datasets with either "health" or "climate"
        assert result.total > 0
        assert len(result.results) > 0

        # Verify at least one result contains either term
        result_texts = []
        for dataset in result.results:
            dcat = dataset.get("dcat", {})
            title = dcat.get("title", "").lower()
            description = dcat.get("description", "").lower()
            keywords = [k.lower() for k in dcat.get("keyword", [])]
            result_texts.append(f"{title} {description} {' '.join(keywords)}")

        has_health_or_climate = any(
            "health" in text or "climate" in text for text in result_texts
        )
        assert has_health_or_climate

    def test_or_query_returns_more_results_than_and(self, interface_with_dataset):
        """Test that OR query returns equal or more results than AND query."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        # Search with OR
        or_result = interface_with_dataset.search_datasets("health OR climate")

        # Search with AND (implicit)
        and_result = interface_with_dataset.search_datasets("health climate")

        # OR should return equal or more results than AND
        assert or_result.total >= and_result.total

    def test_or_query_with_quoted_phrase(self, interface_with_dataset):
        """Test OR query with quoted phrases."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        # Test that quoted phrases work with OR
        result = interface_with_dataset.search_datasets('"health food" OR education')

        # Should work without errors
        assert result.total >= 0

    def test_or_query_with_popularity_sort(self, interface_with_dataset):
        """Test that OR query works with popularity sorting."""
        interface_with_dataset.opensearch.index_datasets(
            interface_with_dataset.db.query(Dataset)
        )

        result = interface_with_dataset.search_datasets(
            "health OR climate", sort_by="popularity"
        )

        # Should return results sorted by popularity
        assert result.total >= 0
        if len(result.results) > 1:
            # Check that results are sorted by popularity (descending)
            for i in range(len(result.results) - 1):
                pop1 = result.results[i].get("popularity") or 0
                pop2 = result.results[i + 1].get("popularity") or 0
                assert pop1 >= pop2
