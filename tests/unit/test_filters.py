from datetime import date, datetime

import pytest

from app.filters import (
    dcatus_to_schema_org_jsonld,
    first_contact_point,
    format_dcat_date,
    format_icon_class,
    format_icon_label,
    format_overlay_label,
    normalized_format_label,
    parse_datetime,
    remove_html_tags,
    resolve_resource_format,
    resource_format_badge,
)


def test_remove_html_tags(html_tags_within_text):
    assert (
        remove_html_tags(html_tags_within_text)
        == "The Division of Drinking Water requires laboratories to \n    submit water quality data directly. The data is received, and published \n    twice monthly on the Division's water quality \n    \n    portal. The resource here now is just a data dictionary for the \n    laboratory analysis data available from that portal, and in the near \n    future we plan to add curated data resources that include laboratory\n    water quality results."
    )


def test_lt_or_gt_not_removed():
    assert remove_html_tags("in x < 0, but also y > 0") == "in x < 0, but also y > 0"


def test_remove_html_tags_none_returns_empty_string():
    assert remove_html_tags(None) == ""


class TestFirstContactPoint:
    """DataService.contactPoint is an array (DCAT-US 3.0); Dataset.contactPoint
    is a single object. Callers that only display one contact need this
    normalized regardless of which shape they got."""

    def test_dict_passthrough(self):
        contact = {"fn": "Test Contact", "hasEmail": "mailto:test@example.gov"}
        assert first_contact_point(contact) == contact

    def test_list_returns_first_dict(self):
        contact = {"fn": "API Support", "hasEmail": "mailto:api@example.gov"}
        assert first_contact_point([contact]) == contact

    def test_empty_list_returns_empty_dict(self):
        assert first_contact_point([]) == {}

    def test_none_returns_empty_dict(self):
        assert first_contact_point(None) == {}


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


class TestResolveResourceFormat:
    """`resolve_resource_format` picks format > mediaType > URL extension."""

    def test_prefers_format_over_media_type(self):
        resource = {"format": "XLSX", "mediaType": "application/xml"}
        assert resolve_resource_format(resource) == "XLSX"

    def test_falls_back_to_media_type(self):
        resource = {"mediaType": "application/json"}
        assert resolve_resource_format(resource) == "application/json"

    def test_falls_back_to_url_extension(self):
        resource = {"downloadURL": "https://example.gov/data/report.csv"}
        assert resolve_resource_format(resource) == "csv"

    def test_accessurl_used_when_no_download_url(self):
        resource = {"accessURL": "https://example.gov/data/report.geojson"}
        assert resolve_resource_format(resource) == "geojson"

    def test_no_usable_field_returns_none(self):
        resource = {"accessURL": "https://example.gov/dataset"}
        assert resolve_resource_format(resource) is None

    def test_non_mapping_returns_none(self):
        assert resolve_resource_format(None) is None


class TestNormalizedFormatLabel:
    """Single source of truth for a resource's format label, shared by cards and the detail page."""

    def test_vendor_mime_maps_to_xlsx_not_xml(self):
        # regex-based matching used to see "xml" inside "spreadsheetml" and mislabel this XML.
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert normalized_format_label(mime) == "XLSX"

    def test_bare_extension(self):
        assert normalized_format_label("PDF") == "PDF"

    def test_unrecognized_format_does_not_default_to_html(self):
        assert normalized_format_label("shp") == "SHP"

    def test_empty_string_returns_file(self):
        assert normalized_format_label("") == "FILE"

    def test_none_returns_file(self):
        assert normalized_format_label(None) == "FILE"

    def test_unknown_vendor_mime_gets_short_generic_label(self):
        assert normalized_format_label("application/vnd.unknown-format") == "UNKN"


class TestResourceFormatBadge:
    """Drives both label and color for search-card pills from one source."""

    def test_vendor_mime_resolves_to_xlsx(self):
        resource = {
            "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        badge = resource_format_badge(resource)
        assert badge["label"] == "XLSX"
        assert badge["format"] == "xlsx"

    def test_format_field_takes_precedence(self):
        resource = {
            "format": "XLSX",
            "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        badge = resource_format_badge(resource)
        assert badge["label"] == "XLSX"

    def test_unrecognized_format_falls_back_to_neutral_color_not_html(self):
        resource = {"format": "some-totally-unknown-format"}
        badge = resource_format_badge(resource)
        assert badge["label"] != "HTML"

        from app.filters import _BADGE_DEFAULT_COLOR

        assert badge["color"] == _BADGE_DEFAULT_COLOR

    def test_missing_format_falls_back_to_neutral_file_badge(self):
        badge = resource_format_badge({})
        assert badge == {
            "format": "file",
            "label": "FILE",
            "color": "#3d4551",
        }

    def test_known_format_has_dedicated_color(self):
        badge = resource_format_badge({"format": "CSV"})
        assert badge["label"] == "CSV"
        assert badge["color"] != "#3d4551"

    @pytest.mark.parametrize("fmt", ["turtle", "kml", "shp", "pptx"])
    def test_label_matches_detail_page_overlay(self, fmt):
        # both read from the same table, so they can't drift apart again.
        badge = resource_format_badge({"format": fmt})
        assert format_icon_label(fmt) == badge["label"]


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


class TestFormatIconClass:
    @pytest.mark.parametrize(
        "fmt, expected",
        [
            ("CSV", "file-icon--csv"),
            ("csv", "file-icon--csv"),
            ("text/csv", "file-icon--csv"),
            ("application/json", "file-icon--json"),
            ("application/xml", "file-icon--xml"),
            ("application/rdf+xml", "file-icon--rdf"),
            ("application/xhtml+xml", "file-icon--html"),
            ("application/geo+json", "file-icon--geojson"),
            ("application/vnd.google-earth.kml+xml", "file-icon--default"),
            (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "file-icon--excel",
            ),
            (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "file-icon--word",
            ),
            ("PDF", "file-icon--pdf"),
            ("ZIP", "file-icon--zip"),
            ("xlsx", "file-icon--excel"),
            ("docx", "file-icon--word"),
            ("HTML", "file-icon--html"),
            ("TXT", "file-icon--text"),
            ("API", "file-icon--api"),
            ("PNG", "file-icon--image"),
            ("KML", "file-icon--default"),
            ("WMS", "file-icon--default"),
            ("SHP", "file-icon--default"),
            ("", "file-icon--default"),
            (None, "file-icon--default"),
        ],
    )
    def test_returns_expected_class(self, fmt, expected):
        assert format_icon_class(fmt) == expected


class TestFormatOverlayLabel:
    @pytest.mark.parametrize(
        "fmt, expected",
        [
            ("CSV", ""),
            ("application/json", ""),
            ("application/rdf+xml", ""),
            ("application/geo+json", ""),
            (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "",
            ),
            ("KML", "KML"),
            ("kml", "KML"),
            ("application/vnd.google-earth.kml+xml", "KML"),
            ("WMS", "WMS"),
            ("WFS", "WFS"),
            ("GML", "GML"),
            ("SHP", "SHP"),
            ("application/octet-stream", "BIN"),
            ("APPLICATION/OCTET-STREAM", "BIN"),
            ("octet-stream", "BIN"),
            ("ARCGIS GEOSERVICES REST API", "REST"),
            ("ArcGIS GeoServices REST API", "REST"),
            ("application/vnd.google-earth.wmts", "WMTS"),
            ("application/x-netcdf", "NETC"),
            ("application/vnd.unknown-format", "UNKN"),
            ("application/vnd.esri.mapserver", "MAPS"),
            ("verylongformatname", "VERY"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_returns_expected_badge(self, fmt, expected):
        assert format_overlay_label(fmt) == expected

    @pytest.mark.parametrize(
        "fmt, expected",
        [
            ("HTML", "HTML"),
            ("application/xhtml+xml", "HTML"),
            ("application/json", ""),
            ("CSV", ""),
            ("application/octet-stream", "BIN"),
            ("ARCGIS GEOSERVICES REST API", "REST"),
            ("KML", "KML"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_returns_expected_icon_label(self, fmt, expected):
        assert format_icon_label(fmt) == expected

    @pytest.mark.parametrize(
        "fmt",
        [
            "application/octet-stream",
            "APPLICATION/OCTET-STREAM",
            "ARCGIS GEOSERVICES REST API",
            "application/vnd.google-earth.kml+xml",
            "application/x-netcdf",
            "application/vnd.unknown-format",
            "application/vnd.esri.mapserver",
            "WMS",
            "verylongformatname",
        ],
    )
    def test_badge_labels_are_short(self, fmt):
        label = format_overlay_label(fmt)
        assert len(label) <= 4
