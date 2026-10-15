from app.utils import normalize_site_url


class TestNormalizeSiteUrl:
    def test_strips_scheme(self):
        assert normalize_site_url("https://catalog.data.gov") == "catalog.data.gov"
        assert normalize_site_url("http://catalog.data.gov") == "catalog.data.gov"

    def test_strips_trailing_slash(self):
        assert normalize_site_url("https://catalog.data.gov/") == "catalog.data.gov"

    def test_keeps_leading_host_characters(self):
        """The host may begin with any of "https:/", which str.strip would eat."""
        assert normalize_site_url("https://staging.catalog.data.gov") == "staging.catalog.data.gov"
        assert normalize_site_url("https://test.data.gov") == "test.data.gov"
        assert normalize_site_url("http://harvest.data.gov") == "harvest.data.gov"

    def test_leaves_a_bare_host_and_port_alone(self):
        assert normalize_site_url("0.0.0.0:8080") == "0.0.0.0:8080"
