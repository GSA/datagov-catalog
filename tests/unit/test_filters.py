from datetime import date, datetime

import pytest

from app.filters import (
    dcatus_to_schema_org_jsonld,
    format_dcat_date,
    parse_datetime,
    remove_html_tags,
    simplify_resource_type,
)


def test_remove_html_tags(html_tags_within_text):
    assert (
        remove_html_tags(html_tags_within_text)
        == "The Division of Drinking Water requires laboratories to \n    submit water quality data directly. The data is received, and published \n    twice monthly on the Division's water quality \n    \n    portal. The resource here now is just a data dictionary for the \n    laboratory analysis data available from that portal, and in the near \n    future we plan to add curated data resources that include laboratory\n    water quality results."
    )


def test_lt_or_gt_not_removed():
    assert remove_html_tags("in x < 0, but also y > 0") == "in x < 0, but also y > 0"


def test_dcatus_to_schema_org_jsonld(dcatus_dataset):
    assert dcatus_to_schema_org_jsonld(dcatus_dataset) == {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": "Social Security Number Verification Service (SSNVS) - Data Exchange",
        "description": "SSNVS is a service offered by SSA's Business Services Online (BSO). It is used by employers and certain third-party submitters to verify the accuracy of the names and SSNs of their employees for wage reporting purposes. With SSNVS users may verify up to 10 names and SSNs online for immediate results or upload batch files for overnight processing. SSNVS uses the Numident Online Verification Utility (NOVU) for the online requests and EVS for the batch requests. SSNVS is maintained by OSES and both NOVU and EVS are maintained in OEEAS DIVES Verification System Branch.",
        "url": None,
        "identifier": "US-GOV-SSA-620",
        "keywords": [
            "BSO",
            "Business Services Online",
            "EVS",
            "NOVU",
            "Numident Online Verification Utility",
            "OSES",
            "SSNVS",
        ],
        "license": "https://www.ssa.gov/data/Restricted-Public-Licensing-Information.html",
        "datePublished": None,
        "dateModified": "2016-03-15",
        "publisher": {
            "@type": "Organization",
            "name": "Social Security Administration",
        },
        "distribution": [],
    }

    dcatus_dataset["distribution"] = [
        {
            "@type": "dcat:Distribution",
            "description": "This set of Excel files contains data on students reported as harassed or bullied or disciplined for harassment or bullying on the basis of sex, race, or disability category for all states. Each file contains three spreadsheets: total students, male students, and female students.",
            "downloadURL": "https://civilrightsdata.ed.gov/assets/downloads/2017-2018/School-Climate/Harassment-or-Bullying/Harassment-Bullying-on-basis-of-disability_discplined.xlsx",
            "format": "XLSX",
            "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "title": "On basis of disability - disciplined",
        }
    ]

    # only distribution has changed so no need to check anything other than that
    assert dcatus_to_schema_org_jsonld(dcatus_dataset)["distribution"] == [
        {
            "@type": "DataDownload",
            "encodingFormat": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "contentUrl": "https://civilrightsdata.ed.gov/assets/downloads/2017-2018/School-Climate/Harassment-or-Bullying/Harassment-Bullying-on-basis-of-disability_discplined.xlsx",
        }
    ]

    # distribution is optional so we want to make sure conversion works if its not there
    del dcatus_dataset["distribution"]

    assert dcatus_to_schema_org_jsonld(dcatus_dataset)["distribution"] == []


class TestSimplifyResourceType:
    """
    Tests for `simplify_resource_type`. We should either get a supported
    str based from the regex or a None value.
    """

    def test_mime_type_xml(self):
        assert simplify_resource_type("application/xml") == "xml"

    def test_bare_extension(self):
        assert simplify_resource_type("PDF") == "PDF"

    def test_unused_string_returns_none(self):
        assert simplify_resource_type("shp") is None

    def test_empty_string_returns_none(self):
        assert simplify_resource_type("") is None

    def test_none_returns_none(self):
        assert simplify_resource_type(None) is None


class TestParseDatetime:
    def test_date_only_string_returns_date(self):
        result = parse_datetime("2026-05-01")
        assert type(result) is date
        assert result == date(2026, 5, 1)

    @pytest.mark.parametrize(
        "value",
        [
            "2026-05-01T00:00:00",
            "2026-05-01T00:00:00Z",
            "2026-05-01T00:00:00+00:00",
        ],
    )
    def test_datetime_strings_return_datetime(self, value):
        result = parse_datetime(value)
        assert type(result) is datetime
        assert (result.year, result.month, result.day) == (2026, 5, 1)


class TestFormatDcatDate:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2026-05-01", "May 01, 2026"),
            ("2026-05-01T14:48:00", "May 01, 2026 at 02:48 PM"),
            ("2026-05-01T14:48:00Z", "May 01, 2026 at 02:48 PM"),
            ("2026-05-01T14:48:00+00:00", "May 01, 2026 at 02:48 PM"),
            ("2026-05-01T00:00:00", "May 01, 2026 at 12:00 AM"),
        ],
    )
    def test_round_trip_via_parse_datetime(self, raw, expected):
        assert format_dcat_date(parse_datetime(raw)) == expected
