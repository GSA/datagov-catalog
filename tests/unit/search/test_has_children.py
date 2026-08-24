def test_get_identifiers_with_children_returns_only_matching_parents(
    interface_with_dataset,
):
    identifiers = [
        "https://subdomain.domain/parent/example.shp.iso.xml",
        "https://example.gov/series/annual-report",
        "no-such-identifier",
    ]

    result = interface_with_dataset.get_identifiers_with_children(identifiers)

    assert result == {
        "https://subdomain.domain/parent/example.shp.iso.xml",
        "https://example.gov/series/annual-report",
    }


def test_get_identifiers_with_children_empty_input_returns_empty_set(
    interface_with_dataset,
):
    assert interface_with_dataset.get_identifiers_with_children([]) == set()
