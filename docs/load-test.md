# Performance Testing

To prove out our technology choices (Python/Flask/Postgres full-text search)
we want to load-test our application. The primary metric is response time,
with server load as a secondary metric.

ApacheBench (ab) is a sufficient tool for making concurrent requests to a
single URL and collecting data on the response times.High levels of concurrency
are not present in our observed production traffic. Instead, we are going to
focus on speed of each response rather than the combined effect of 

BLUF: Search API response times are comparable to the current catalog, except
in the situation where there are very many matching datasets. Page load times
in the new system are dramatically better than in the current catalog.

## Search performance

Our search API uses a different technology than our current catalog and so we
want to test the performance of the search API.

Peak traffic on our production search API over the last 4 months peaked at
10,000 requests per hour, or less than half of a request per second. We focus
on response time as a measure of responsiveness and customer experience rather
than performance under extreme load. We will use 10 concurrent requests in
`ab` and run each test for 30 seconds.

 We want to check the performance in three types of situations: no matches,
 few matches, and many matches.

### No matches

A search term like `reallylongtermnomatches` has no datasets that match in
either catalog, so the response time can be less because in an indexed
search system, determining that a term is absent can be optimized. For our new
system (dev) and the current system (catalog) we report the 50th and 95th
percentile for response time, that is, the length of time that half or
almost-all of our requests completed in. 

| System  | 50th percentile (ms) | 95th percentile (ms) |
| ------- | -------------------- | -------------------- |
| dev     | 600                  | 681                  |
| catalog | 636                  | 829                  |

### Few matches

For very specific search terms like `cardiopulmonary resuscitation` the main
work of the application is in locating the matching datasets. Comparing
response time percentiles for that search term:


| System  | 50th percentile (ms) | 95th percentile (ms) |
| ------- | -------------------- | -------------------- |
| dev     | 676                  | 741                  |
| catalog | 654                  | 953                  |


### Many matches

A search term like `data` has incredibly many matches and the work of the
application is primarily in ordering and fetching the first page of API results
from all of those. Comparing response time percentiles for that search term
between the new and existing systems:

| System  | 50th percentile (ms) | 95th percentile (ms) |
| ------- | -------------------- | -------------------- |
| dev     | 3804                 | 10200                |
| catalog | 711                  | 1160                 |

This "many matches" case is where the new system significantly underperforms
the current catalog. We should explore possible ways to improve performance in
this case.

The initial suspicion is that this particular search is not using the search
index in the Postgres database. The dev response time here depends heavily on
the concurrency. With only one concurrent request, the 50th percentile
response time is a very reasonable 1295ms and the 99th percentile response
time is 1454ms.  This concurrency dependency makes sense if the query requires
a full table scan from the database because that is an intensive operation and
multiple concurrent scans would require lots of waiting.

## Page load performance

Our web stack is quite different between the new system and the current
catalog, so we want to know about differences in loading a application web
pages.  One difficulty with comparing against our production catalog is that
it is cached behind AWS CloudFront so further requests to the same page will
show response times only for the cache, not for the web application itself.
Instead, we send an `auth_tkt=1` cookie to
`catalog-prod-admin-datagov.app.cloud.gov` to miss the CloudFront cache.

Production workloads for the entire Catalog web application (behind the cache)
have a sustained levels around 20 requests per second with infrequent sustained
peaks as high as 80 requests per second.

There are at least three basic types of pages in the application: the main
search page, an organization details page, and a dataset details page. The new
catalog is rapidly adding functionality to all of these pages, so the "dev"
numbers below could change as the application changes.

### Main search page

The main search page on the new system does not have a list of datasets
currently, so we can't have an apple-to-apples comparison yet.

### Organization details page

The organization detail page on the current catalog saturates around 6
requests per second using 20 or more concurrent requests. The new system
saturates around 75 requests per second with 100 or more concurrent requests.
To focus on response time, we use the same concurrency setting of 10 from
above. We test with a small-ish organization
`/organization/board-of-governors-of-the-federal-reserve-system`.

| System  | 50th percentile (ms) | 95th percentile (ms) |
| ------- | -------------------- | -------------------- |
| dev     | 724                  | 797                  |
| catalog | 1772                 | 2170                 |


### Dataset detail page

The dataset detail page on the current catalog saturates around 5 requests per
second using 15 or more concurrent requests. The new system saturates around
120 requests per second at 110 concurrent requests. To focus on response time,
we use the same concurrency setting of 10 from above. We test with a dataset
from the above organization `/dataset/household-debt-by-state-county-and-msa`.


| System  | 50th percentile (ms) | 95th percentile (ms) |
| ------- | -------------------- | -------------------- |
| dev     | 596                  | 671                  |
| catalog | 2151                 | 3097                 |
