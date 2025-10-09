def test_search(interface_with_dataset):
    result = interface_with_dataset.search_datasets("test")
    assert len(result) > 0

    result = interface_with_dataset.search_datasets("description")
    assert len(result) > 0

    # no search results
    result = interface_with_dataset.search_datasets("nonexistentword")
    assert len(result) == 0


def test_websearch(interface_with_dataset):
    """Test search queries in websearch format."""

    # "test description" is the source document
    result = interface_with_dataset.search_datasets("test AND description")
    assert len(result) > 0

    # nonexistent isn't there so and should match nothing
    result = interface_with_dataset.search_datasets("test AND nonexistentword")
    assert len(result) == 0

    # test is there, so this should match
    result = interface_with_dataset.search_datasets("test OR -description")
    assert len(result) > 0

    # negation should match nothing
    result = interface_with_dataset.search_datasets("-description")
    assert len(result) == 0
