# Catalog filter evaluation checklist

## 1. Preparation and scope
- [ ] Record analysis start/end dates
- [ ] Confirm current filters
- [ ] Verify OpenSearch fields and metadata sources for each filter
- [ ] Identify New Relic events/attributes and GA4 property/Exploration
- [ ] Document exclusions: bots, monitoring, API requests, internal traffic

## 2. Collect analytics
- [ ] Count active-filter URL appearances for all seven filters
- [ ] Collect selection events, dataset-click metrics, and zero-result rates

## 3. Evaluate filter quality
- [ ] Review search patterns and support issues
- [ ] Evaluate proposed new filters for user demand and metadata readiness

## 4. Report and preserve
- [ ] Write findings and evidence for each existing filter
- [ ] Assign keep / rename / consolidate / remove / insufficient evidence
- [ ] Document candidate filters with supporting evidence
- [ ] Save or version NRQL queries, GA4 setup, and exported results
- [ ] Publish report to catalog wiki and link it to issue

# Analysis focus
| Dimension | Evident to collect |
|-------|-------|
| Demand | Usage rate, support requests, search patterns | 
| Utility | Dataset click-through, zero-result rate, task success |
| Distinctiveness | Overlap with existing filters and keyword search | 
| Metadata quality | Field completeness, consistency, meaningful value distribution | 
| UX cost | Discoverability, cognitive load, mobile usability |

| Decision | Proposed trigger |
|-------|-------|
| Keep | Meaningful adoption or demonstrated value to a target audience | 
| Investigate removal | Under 1% session adoption across repeated periods, without compelling qualitative evidence | 
| Investigate consolidation | Significant purpose overlap and user confusion | 
| Investigate renaming | Usability feedback indicates unclear terminology | 
| Consider adding | Repeated user demand, distinct utility, and sufficiently populated metadata | 
| Use progressive disclosure | Additional filters provide value but increase interface complexity |

# Current UI filters
| UI filter   |      Purpose     |  URL Query Parameter | OpenSearch Field | 
|----------|---------------|-------|--------|
| Geographic Area |  Limit results by location | `spatial_geometry` & `spatial_within` | `spatial_shape` |
| Keywords |   Match dataset keywords   |  `keyword` |  `keyword` |
| Organization | Filter by catalog organization |  `org_slug` | `slug` | 
| Organization Type | Federal, state, local, etc. |  `org_type` | `organization.organization_type` | 
| Publisher Filter | Filter by publisher metadata |  `publisher` | `publisher.normalized` | 
| Spatial Data | Filter by geospatial or non-geospatial datasets | `spatial_filter` | `has_spatial` |
| Data Access | Datasets with downloadable files |  `has_download` | `has_download` |

# New Relic Analysis
the telemetry we send to new relic isn't filtered by bots so the results are skewed. you can certainly
remove some bots by excluding those which have `bot` in the `http-user-agent`. here's some queries for understanding query parameter frequencies in requests. the first counts the frequency of our current filter options. the second query counts filters in our search api which aren't in the UI. 

## Queries
```sql
-- new relic query for counting frequency of query param used in requests
SELECT 
  filter(count(*), WHERE `request` RLIKE '.*[?&]keyword=[^&#]+.*')  AS 'Keyword',
  filter(count(*), WHERE `request` RLIKE '.*[?&]org_slug=[^&#]+.*') AS 'Organization',
  filter(count(*), WHERE `request` RLIKE '.*[?&]org_type=[^&#]+.*') AS 'Organization Type',
  filter(count(*), WHERE `request` RLIKE '.*[?&]publisher=[^&#]+.*') AS 'Publisher',
  filter(count(*), WHERE `request` RLIKE '.*[?&]spatial_filter=[^&#]+.*') AS 'Is Geospatial',
  filter(count(*), WHERE `request` RLIKE '.*[?&]spatial_geometry=[^&#]+.*') AS 'Spatial Search',
  filter(count(*), WHERE `request` RLIKE '.*[?&]has_download=[^&#]+.*') AS 'Data Access'
FROM Log WHERE `space_name` = 'prod' AND `app_name` = 'datagov-catalog-proxy' AND `request` NOT LIKE '/search%'
SINCE 90 days ago

-- similar new relic query but against search api route for filters not in the 
-- UI to understand what we could offer
SELECT
  filter(count(*),
    WHERE `request` RLIKE '.*[?&]access_level=[^&#]+.*'
  ) AS 'Access Level',

  filter(count(*),
    WHERE `request` RLIKE '.*[?&]theme=[^&#]+.*'
  ) AS 'Theme'
FROM Log WHERE `space_name` = 'prod' AND `app_name` = 'datagov-catalog-proxy' AND `request` RLIKE '/search([/?#].*|)'
SINCE 90 days ago
```

## Results
### 10/23/26: request counts per filter query parameter in the last 90 days (new relic)
| Keyword |  Organization | Organization Type | Publisher | Is Geospatial | Spatial Search | Data Access |
|-------|---|---|---|---|---|---|
|  6.44 M | 26.9 k | 49.7 k | 23.2 M | 177 k | 20.1 k | 122 k |

| Access Level | Theme |
|----|----|
| 394 | 658 |

# GA4 analysis
data from google analytics is more accurate to actual user interactions than new relic because bots are filtered from reporting ([source](https://support.google.com/analytics/answer/9888366?hl=en)). You can explore data captured by google analytics via the "[exploration](https://analytics.google.com/analytics/web/?utm_source=marketingplatform.google.com&utm_medium=et&utm_campaign=marketingplatform.google.com%2Fabout%2Fanalytics%2F#/analysis/a42145528p381392243)" tab in GA4. There's already a catalog filter usage report [here](https://analytics.google.com/analytics/web/?utm_source=marketingplatform.google.com&utm_medium=et&utm_campaign=marketingplatform.google.com%2Fabout%2Fanalytics%2F#/analysis/a42145528p381392243/edit/bXrABIpdQSOx7zOYrsMQyw). Unfortunately GA4 exploration doesn't support SQL so the analysis to calculate frequency of query parameter usage is manual (unless we wanted to feed the data into big query). Here's the regular expression used to calculate frequency of query parameters in user requests. The idea is to filter "Page Location" values based on those regular expressions which will give you the frequency (see picture below for example result)

```
^https://catalog\.data\.gov/.*[?&]keyword=[^&#]+.*$
^https://catalog\.data\.gov/.*[?&]org_slug=[^&#]+.*$
^https://catalog\.data\.gov/.*[?&]org_type=[^&#]+.*$
^https://catalog\.data\.gov/.*[?&]publisher=[^&#]+.*$
^https://catalog\.data\.gov/.*[?&]spatial_filter=[^&#]+.*$
^https://catalog\.data\.gov/.*[?&]spatial_geometry=[^&#]+.*$
^https://catalog\.data\.gov/.*[?&]has_download=[^&#]+.*$
```

## Results
### 10/23/26: request counts per filter query parameter in the last 90 days (GA4)
| Keyword |  Organization | Organization Type | Publisher | Is Geospatial | Spatial Search | Data Access |
|-------|---|---|---|---|---|---|
|  158 K | 9.5 k | 12.3 k | 8.4 k | 13.8 k | 17.3 k | 17.7 k |

# Recommendations (potential ideas)
## Add
- temporal & file formats (user requests)

## Remove