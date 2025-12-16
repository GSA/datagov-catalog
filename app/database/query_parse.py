"""
Should support the following:
- Default AND behavior: `health food` = both terms required
- OR operator: `health OR food` = either term
- Exact phrases: `"health food"` = exact phrase match
- Mixed queries: `"health food" OR nutrition` = \
    phrase ("health food") OR term (`nutrition`)
"""

import re
from typing import Any


def parse_search_query(query: str) -> dict[str, Any]:
    """
    Parse search query string into OpenSearch query structure.
    
    Examples of potential outputs based on phrase/term/ use of OR:
        - parse_search_query("health food")
        {'multi_match': {'query': 'health food', 'operator': 'AND', ...}}
        
        - parse_search_query("health OR food")
        {'bool': {'should': [{'multi_match': ...}, {'multi_match': ...}]}}
        
        - parse_search_query('"health food"')
        {'multi_match': {'query': 'health food', 'type': 'phrase', ...}}
    """
    if not query or not query.strip():
        return {"match_all": {}}
    
    query = query.strip()
    
    # Extract quoted phrases
    phrases = []
    phrase_pattern = r'"([^"]+)"'
    
    for match in re.finditer(phrase_pattern, query):
        phrases.append(match.group(1))
    
    # Remove phrases from query to process remaining terms
    remaining = re.sub(phrase_pattern, '', query).strip()
    
    # Clean up orphaned OR operators eg:
    # Remove leading OR (e.g., "OR nutrition" -> "nutrition")
    remaining = re.sub(r'^\s*OR\s+', '', remaining, flags=re.IGNORECASE).strip()
    # Remove trailing OR (e.g., "environment OR" -> "environment")
    remaining = re.sub(r'\s+OR\s*$', '', remaining, flags=re.IGNORECASE).strip()
    
    # Check if there are OR operators in the remaining text
    has_or_operator = ' OR ' in remaining.upper()
    
    # If no special syntax, return simple multi_match (backward compatible)
    if not phrases and not has_or_operator:
        return _build_simple_query(query)
    
    # Build complex query with phrases and/or OR logic
    clauses = []
    
    # Add phrase queries
    for phrase in phrases:
        clauses.append(_build_phrase_query(phrase))
    
    # Process remaining terms
    if remaining:
        # Split by OR operator (case insensitive)
        or_parts = re.split(r'\s+OR\s+', remaining, flags=re.IGNORECASE)
        or_parts = [part.strip() for part in or_parts if part.strip()]
        
        if len(or_parts) > 1:
            # Multiple terms with OR
            for part in or_parts:
                if part:
                    clauses.append(_build_term_query(part))
        elif or_parts:
            # Single term without OR
            clauses.append(_build_term_query(or_parts[0]))
    
    # If multiple clauses OR a single phrase, use bool query
    if len(clauses) > 1:
        # bool helps support the logic needed to do the OR because it works by
        # combining multiple queries and returns the matching resuls "should"
        # means it "should" be found in one of the fields
        # where multi_part searches across fields
        return {"bool": {"should": clauses, "minimum_should_match": 1}}
    elif len(clauses) == 1:
        # Single clause (could be a phrase)
        return clauses[0]
    else:
        # Fallback
        return {"match_all": {}}


def _build_simple_query(query: str) -> dict[str, Any]:
    """Build a simple multi_match query with AND operator."""
    return {
        "multi_match": {
            "query": query,
            "type": "most_fields",
            "fields": [
                "title^5",
                "description^3",
                "publisher^3",
                "keyword^2",
                "theme",
                "identifier",
            ],
            "operator": "AND",
            "zero_terms_query": "all",
        }
    }


def _build_phrase_query(phrase: str) -> dict[str, Any]:
    """Build a multi_match phrase query for exact matching."""
    return {
        "multi_match": {
            "query": phrase,
            "type": "phrase",
            "fields": [
                "title^5",
                "description^3",
                "publisher^3",
                "keyword^2",
                "theme",
                "identifier",
            ],
        }
    }


def _build_term_query(term: str) -> dict[str, Any]:
    """Build term query and remove any whitespace from the term."""
    term = term.strip()
    return {
        "multi_match": {
            "query": term,
            "type": "most_fields",
            "fields": [
                "title^5",
                "description^3",
                "publisher^3",
                "keyword^2",
                "theme",
                "identifier",
            ],
            "operator": "AND",
            "zero_terms_query": "all",
        }
    }
