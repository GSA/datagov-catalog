
def test_search(interface_with_dataset):
    # test is in the title
    result = interface_with_dataset.search_datasets("test")
    assert len(result) > 0

    # description is only in the description
    result = interface_with_dataset.search_datasets("description")
    assert len(result) > 0

    # no search results
    result = interface_with_dataset.search_datasets("nonexistentword")
    assert len(result) == 0


