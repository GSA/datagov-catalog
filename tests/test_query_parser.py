from app.database.query_parse import (
    _build_phrase_query,
    _build_simple_query,
    _build_term_query,
    parse_search_query,
)


class TestParseSearchQuery:
    """
    Tests for parse_search_query function to help ensure queries are built as
    as expected. This is to future proof modifications if we add explicit AND
    support.
    """

    def test_empty_query_returns_match_all(self):
        """Test that empty query returns match_all."""
        result = parse_search_query("")
        assert result == {"match_all": {}}

        result = parse_search_query("   ")
        assert result == {"match_all": {}}

        result = parse_search_query(None)
        assert result == {"match_all": {}}

    def test_simple_query_uses_and_operator(self):
        """Test that simple query uses AND operator (backward compatible)."""
        result = parse_search_query("health food")

        assert "multi_match" in result
        assert result["multi_match"]["query"] == "health food"
        assert result["multi_match"]["operator"] == "AND"
        assert result["multi_match"]["type"] == "most_fields"

    def test_single_word_query(self):
        """Test single word query."""
        result = parse_search_query("health")

        assert "multi_match" in result
        assert result["multi_match"]["query"] == "health"
        assert result["multi_match"]["operator"] == "AND"

    def test_query_with_or_operator(self):
        """Test query with OR operator creates bool should query."""
        result = parse_search_query("health OR food")

        assert "bool" in result
        assert "should" in result["bool"]
        assert len(result["bool"]["should"]) == 2
        assert result["bool"]["minimum_should_match"] == 1

        # First clause
        assert result["bool"]["should"][0]["multi_match"]["query"] == "health"
        # Second clause
        assert result["bool"]["should"][1]["multi_match"]["query"] == "food"

    def test_query_with_or_operator_case_insensitive(self):
        """Test that OR operator is case insensitive."""
        result_upper = parse_search_query("health OR food")
        result_lower = parse_search_query("health or food")
        result_mixed = parse_search_query("health Or food")

        # All should produce the same structure
        assert "bool" in result_upper
        assert "bool" in result_lower
        assert "bool" in result_mixed

        assert len(result_upper["bool"]["should"]) == 2
        assert len(result_lower["bool"]["should"]) == 2
        assert len(result_mixed["bool"]["should"]) == 2

    def test_exact_phrase_with_quotes(self):
        """Test exact phrase matching with quotes."""
        result = parse_search_query('"health food"')

        assert "multi_match" in result
        assert result["multi_match"]["query"] == "health food"
        assert result["multi_match"]["type"] == "phrase"
        assert "operator" not in result["multi_match"]

    def test_multiple_phrases(self):
        """Test multiple quoted phrases create OR logic."""
        result = parse_search_query('"health food" "medical research"')

        assert "bool" in result
        assert "should" in result["bool"]
        assert len(result["bool"]["should"]) == 2

        # Both should be phrase queries
        assert result["bool"]["should"][0]["multi_match"]["type"] == "phrase"
        assert result["bool"]["should"][0]["multi_match"]["query"] == "health food"
        assert result["bool"]["should"][1]["multi_match"]["type"] == "phrase"
        assert result["bool"]["should"][1]["multi_match"]["query"] == "medical research"

    def test_phrase_or_term(self):
        """Test combination of exact phrase and OR term."""
        result = parse_search_query('"health food" OR nutrition')

        assert "bool" in result
        assert "should" in result["bool"]
        assert len(result["bool"]["should"]) == 2

        # First should be phrase query
        assert result["bool"]["should"][0]["multi_match"]["type"] == "phrase"
        assert result["bool"]["should"][0]["multi_match"]["query"] == "health food"

        # Second should be regular term query
        assert result["bool"]["should"][1]["multi_match"]["query"] == "nutrition"

    def test_complex_mixed_query(self):
        """Test complex query with phrases, OR, and terms."""
        result = parse_search_query(
            '"climate change" OR environment OR "global warming"'
        )

        assert "bool" in result
        assert "should" in result["bool"]
        assert len(result["bool"]["should"]) == 3

        # Check all three clauses
        queries = [
            clause["multi_match"]["query"] for clause in result["bool"]["should"]
        ]
        assert "climate change" in queries
        assert "environment" in queries
        assert "global warming" in queries

    def test_phrase_with_and_terms(self):
        """Test phrase combined with AND terms."""
        result = parse_search_query('"health statistics" data analysis')

        assert "bool" in result
        assert "should" in result["bool"]
        assert len(result["bool"]["should"]) == 2

        # First is phrase
        assert result["bool"]["should"][0]["multi_match"]["type"] == "phrase"
        assert (
            result["bool"]["should"][0]["multi_match"]["query"] == "health statistics"
        )

        # Second is multi-word AND term
        assert result["bool"]["should"][1]["multi_match"]["query"] == "data analysis"
        assert result["bool"]["should"][1]["multi_match"]["operator"] == "AND"

    def test_fields_are_boosted_correctly(self):
        """Test that field boosting is preserved in all query types."""
        # Test simple query
        simple = parse_search_query("health")
        assert "title^5" in simple["multi_match"]["fields"]
        assert "description^3" in simple["multi_match"]["fields"]

        # Test phrase query
        phrase = parse_search_query('"health food"')
        assert "title^5" in phrase["multi_match"]["fields"]
        assert "description^3" in phrase["multi_match"]["fields"]

        # Test OR query
        or_query = parse_search_query("health OR food")
        for clause in or_query["bool"]["should"]:
            assert "title^5" in clause["multi_match"]["fields"]
            assert "description^3" in clause["multi_match"]["fields"]

    def test_quote_edge_cases(self):
        """Test edge cases with quotes."""
        # Empty quotes
        result = parse_search_query('""')
        # Should still parse but may have empty phrase
        assert result is not None

        # Unclosed quote - regex won't match, treated as regular text
        result = parse_search_query('"health food')
        assert "multi_match" in result
        assert (
            result["multi_match"]["query"] == '"health food'
        )  # Quote becomes part of query

    def test_multiple_or_operators(self):
        """Test multiple OR operators in sequence."""
        result = parse_search_query("health OR food OR nutrition OR wellness")

        assert "bool" in result
        assert "should" in result["bool"]
        assert len(result["bool"]["should"]) == 4

        queries = [
            clause["multi_match"]["query"] for clause in result["bool"]["should"]
        ]
        assert "health" in queries
        assert "food" in queries
        assert "nutrition" in queries
        assert "wellness" in queries

    def test_whitespace_handling(self):
        """Test that extra whitespace is handled correctly."""
        result = parse_search_query("  health   food  ")

        assert "multi_match" in result
        # Query should be cleaned up
        assert "health" in result["multi_match"]["query"]
        assert "food" in result["multi_match"]["query"]


class TestBuildSimpleQuery:
    """Test suite for _build_simple_query helper."""

    def test_builds_multi_match_with_and(self):
        """Test that simple query builder creates AND query."""
        result = _build_simple_query("test query")

        assert result["multi_match"]["query"] == "test query"
        assert result["multi_match"]["operator"] == "AND"
        assert result["multi_match"]["type"] == "most_fields"
        assert result["multi_match"]["zero_terms_query"] == "all"

    def test_includes_all_fields(self):
        """Test that all required fields are included."""
        result = _build_simple_query("test")

        fields = result["multi_match"]["fields"]
        assert "title^5" in fields
        assert "description^3" in fields
        assert "publisher^3" in fields
        assert "keyword^2" in fields
        assert "theme" in fields
        assert "identifier" in fields


class TestBuildPhraseQuery:
    """Test suite for _build_phrase_query helper."""

    def test_builds_phrase_query(self):
        """Test that phrase query builder creates phrase type query."""
        result = _build_phrase_query("exact phrase")

        assert result["multi_match"]["query"] == "exact phrase"
        assert result["multi_match"]["type"] == "phrase"

    def test_includes_all_fields(self):
        """Test that all required fields are included."""
        result = _build_phrase_query("test phrase")

        fields = result["multi_match"]["fields"]
        assert "title^5" in fields
        assert "description^3" in fields
        assert "publisher^3" in fields
        assert "keyword^2" in fields
        assert "theme" in fields
        assert "identifier" in fields


class TestBuildTermQuery:
    """Test suite for _build_term_query helper."""

    def test_multi_word_term_uses_and(self):
        """Test that multi-word terms use AND operator."""
        result = _build_term_query("climate change")

        assert result["multi_match"]["query"] == "climate change"
        assert result["multi_match"]["operator"] == "AND"

    def test_includes_all_fields(self):
        """Test that all required fields are included."""
        result = _build_term_query("test")

        fields = result["multi_match"]["fields"]
        assert "title^5" in fields
        assert "description^3" in fields
        assert "publisher^3" in fields
        assert "keyword^2" in fields
        assert "theme" in fields
        assert "identifier" in fields
