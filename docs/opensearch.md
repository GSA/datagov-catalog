# Opensearch and our use case

Opensearch is a tool for searching large sets of "documents". Documents are
"indexed" and then the index can be queried in many different ways. Opensearch
is not a database for permanent storage of data, but a separate system that
duplicates some aspects of our Postgres data to make them easy to search.

Opensearch is a distributed system with a set of nodes that store the
documents and respond to search queries. Search results are collected up from
nodes and returned in response to queries from the API. We use Opensearch from
AWS brokered to us via Cloud.gov <https://docs.cloud.gov/platform/services/aws-elasticsearch/>.

## Limitations

Because it is a distributed system, Opensearch needs to store the search
results on a node to serve them back. For this reason, it consumes many
resources to store a large number of results for random-access pagination.
Opensearch limits random-access pagination to 10,000 results. Larger search
results can be extracted, but pages of those search results can't be "jumped"
to by choice. Instead, with one page of results from a sorted search, the sort
value from the last result can be used to ask for the next page of results.
Opensearch calls this parameter of the query `search_after`. Arbitrarily large
result sets can be paged through in this way, using information from each page
to fetch the next one.

## Indexing

Because Opensearch is alongside our Postgres database, we have to synchronize
the contents of our database with the searchable index in Opensearch.
Currently, we do this in a daily batch operation. A command `flask search
sync` is available for this. It clears the Opensearch index and then indexes
every dataset from Postgres into Opensearch.

## Paginated search

As described above, we need to provide a `search_after` parameter to the
Opensearch query API to get the next page of search results. That parameter is
a list of the sort keys that were used to sort the search results. In our API,
to make the formatting and escaping easier, we don't want to use a list as a
query parameter. Instead, we form an opaque `after` string that can be
provided with an `after=...` query parameter to get the next page of results.
The `after` string is a base64-encoded JSON serialization of the actual
`search_after` list. The `search` endpoint in `app/routes.py` handles the
`after` string and the passes it to the `search_datasets` method of our
database interface which decodes it and sends the actual `search_after` value
to our Opensearch interface's `search` method.

Another aspect of pagination that is complicated by this approach is that
there is no obvious way to know from an Opensearch search result if there will
be any more search results available on the next call using `search_after`. If
we ask for a page with 20 search results and get 20 results back, it doesn't
tell us if using the last result in `search_after` will give any results or
not. This makes for an awkward user experience where a user might click for
"More results" and get none back. To work around this, we use a trick where
when we want a page with 20 results, we ask Opensearch for 21 results and if
there is a 21st result in the response, we know that there will be at least 1
response in the next request for 20 results. This is handled in
`app/database/opensearch.py` and our `SearchResult` object uses
`search_after=None` when there are no more results available.
