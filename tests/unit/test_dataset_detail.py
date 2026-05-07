import json
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from app.utils import hint_from_dict
from tests.fixtures import DATASET_ID, DEFAULT_LAST_HARVESTED_DATE


class TestDatasetDetail:
    """
    Test cases for dataset detail page.
    """

    def test_dataset_interface_by_slug(self, interface_with_dataset):
        dataset = interface_with_dataset.get_dataset_by_slug("test")
        assert dataset is not None
        assert dataset.dcat.get("title") == "test"

    def test_dataset_interface_by_id(self, interface_with_dataset):
        dataset = interface_with_dataset.get_dataset_by_id(DATASET_ID)
        assert dataset is not None
        assert dataset.dcat.get("title") == "test"

    def test_dataset_detail_by_slug(self, interface_with_dataset, db_client):
        """
        Test dataset detail page by using the slug.
        Tests to ensure the page renders correctly and contains expected elements,
        including the Dataset Information box, Metadata Information box.
        """
        ds = interface_with_dataset.get_dataset_by_slug("test")
        ds.dcat = {
            **ds.dcat,
            "issued": "2021-03-15",
            "modified": "2023-06-01",
            "accrualPeriodicity": "R/P1Y",
        }
        interface_with_dataset.db.commit()

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/dataset/test")
        # check response is successful
        assert response.status_code == 200

        soup = BeautifulSoup(response.text, "html.parser")
        # the title includes the publishing organization
        assert soup.title.string == "test org - test"
        # assert the title in the h1 section is the same as the title
        h1 = soup.select_one("main#content h1.dataset-title").text
        assert h1 == "test"
        # check the dataset description is present
        description = soup.select_one(".dataset-description").get_text(strip=True)
        assert description == "this is the test description"

        feedback_button = soup.find("button", id="contact-btn")
        assert feedback_button is not None
        assert feedback_button.get("data-dataset-identifier") == "test"
        assert "Feedback" in feedback_button.get_text(" ", strip=True)

        resources_details = soup.select_one("div.resources-section")
        assert resources_details is not None

        resources_heading = resources_details.select_one("div.resources-section h2")
        assert resources_heading is not None

        resources = resources_details.select("ul li")
        assert len(resources) == 1

        first_resource = resources[0]
        resource_name = first_resource.select_one(".resources-list__name")
        assert "Test CSV" in resource_name.get_text(" ", strip=True)

        # Download button should link to the downloadURL
        download_btn = first_resource.find(
            "a", class_=lambda c: c and "usa-button" in c and "outline" not in c
        )
        assert download_btn is not None
        assert download_btn.get("href") == "https://example.com/test.csv"
        assert "Download" in download_btn.get_text(strip=True)

        search_form = soup.find("form", attrs={"action": "/"})
        assert search_form is not None
        search_input = search_form.find("input", {"name": "q"})
        assert search_input is not None

        sidebar_headings = {
            h.get_text(strip=True): h.find_parent("div", class_="sidebar-section")
            for h in soup.select(".sidebar-section__heading")
        }

        dataset_info_box = sidebar_headings.get("Dataset Information")
        assert dataset_info_box is not None

        dataset_info_items = {
            item.select_one(".sidebar-section__label")
            .get_text(strip=True): item.select_one(".sidebar-section__value")
            .get_text(strip=True)
            for item in dataset_info_box.select(".sidebar-section__item")
        }
        assert "Dataset Issued" in dataset_info_items
        assert dataset_info_items["Dataset Issued"] == "2021-03-15"
        assert "Dataset Last Modified" in dataset_info_items
        assert dataset_info_items["Dataset Last Modified"] == "2023-06-01"
        assert "Accrual Periodicity" in dataset_info_items
        assert dataset_info_items["Accrual Periodicity"] == "R/P1Y"

        metadata_info_box = sidebar_headings.get("Metadata Information")
        assert metadata_info_box is not None

        metadata_items = {
            item.select_one(".sidebar-section__label")
            .get_text(strip=True): item.select_one(".sidebar-section__value")
            .get_text(strip=True)
            for item in metadata_info_box.select(".sidebar-section__item")
        }
        expected_harvested = DEFAULT_LAST_HARVESTED_DATE.strftime(
            "%B %d, %Y at %I:%M %p"
        )
        assert "Metadata Last Checked" in metadata_items
        assert metadata_items["Metadata Last Checked"] == expected_harvested

        harvest_record_item = metadata_items.get("Harvest Record")
        assert harvest_record_item is not None
        harvest_record_link = metadata_info_box.select_one(
            ".sidebar-section__item a[href*='harvest']"
        )
        assert harvest_record_link is not None
        assert "View Raw Data" in harvest_record_link.get_text(strip=True)

    def test_dataset_detail_includes_meta_tags(self, interface_with_dataset, db_client):
        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/dataset/test")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        canonical_link = soup.select_one('link[rel="canonical"]')
        assert canonical_link is not None
        assert canonical_link.get("href").endswith("/dataset/test")

        description_meta = soup.select_one('meta[name="description"]')
        assert description_meta is not None
        assert description_meta.get("content") == "this is the test description"

        robots_meta = soup.select_one('meta[name="robots"]')
        assert robots_meta is not None
        assert robots_meta.get("content") == "index,follow"

        og_title = soup.select_one('meta[property="og:title"]')
        assert og_title is not None
        assert og_title.get("content") == "test org - test"

        og_description = soup.select_one('meta[property="og:description"]')
        assert og_description is not None
        assert og_description.get("content") == "this is the test description"

        og_url = soup.select_one('meta[property="og:url"]')
        assert og_url is not None
        assert og_url.get("content").endswith("/dataset/test")

        social_image_url = db_client.application.config["SOCIAL_IMAGE_URL"]

        og_image = soup.select_one('meta[property="og:image"]')
        assert og_image is not None
        assert og_image.get("content") == social_image_url

        twitter_card = soup.select_one('meta[name="twitter:card"]')
        assert twitter_card is not None
        assert twitter_card.get("content") == "summary_large_image"

        twitter_title = soup.select_one('meta[name="twitter:title"]')
        assert twitter_title is not None
        assert twitter_title.get("content") == "test org - test"

        twitter_description = soup.select_one('meta[name="twitter:description"]')
        assert twitter_description is not None
        assert twitter_description.get("content") == "this is the test description"

        twitter_image = soup.select_one('meta[name="twitter:image"]')
        assert twitter_image is not None
        assert twitter_image.get("content") == social_image_url

    def test_dataset_detail_by_id_redirects_to_slug(
        self, interface_with_dataset, db_client
    ):
        with patch("app.routes.interface", interface_with_dataset):
            dataset_id = interface_with_dataset.get_dataset_by_slug("test").id
            response = db_client.get(f"/dataset/{dataset_id}")

        assert response.status_code == 301
        assert response.headers["Location"].endswith("/dataset/test")

    def test_dataset_detail_404(self, db_client):
        """
        Test that accessing a non-existent dataset by slug or ID returns a 404 error.
        """
        response = db_client.get("/dataset/does-not-exist")
        # check response fails with 404
        assert response.status_code == 404

    def test_dataset_detail_return_to_search(self, interface_with_dataset, db_client):
        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get(
                "/dataset/test", query_string={"from_hint": hint_from_dict({"a": "b"})}
            )
        soup = BeautifulSoup(response.text, "html.parser")
        back_link = soup.find("a", class_="return-link")
        assert back_link is not None
        assert "?a=b" in back_link.get("href")

    def test_dataset_detail_includes_map_assets_when_spatial_polygon(
        self, interface_with_dataset, db_client
    ):
        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/dataset/test")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        # Map container
        map_div = soup.select_one("#dataset-map")
        assert map_div is not None
        assert map_div.get("data-geometry") is not None

        # Leaflet assets (conditionally included)
        leaflet_css = soup.select_one('link[href*="leaflet.css"]')
        leaflet_js = soup.select_one('script[src*="leaflet.js"]')
        view_js = soup.select_one('script[src*="js/view_bbox_map.js"]')
        assert leaflet_css is not None
        assert leaflet_js is not None
        assert view_js is not None

    def test_dataset_detail_includes_map_assets_when_spatial_point(
        self, interface_with_dataset, db_client
    ):
        # Add spatial geometry and ensure map container and Leaflet assets are present
        ds = interface_with_dataset.get_dataset_by_slug("test")
        ds.translated_spatial = {
            "type": "Point",
            "coordinates": [-373.59375715256, -65.778772326728],
        }
        interface_with_dataset.db.commit()

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/dataset/test")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        map_div = soup.select_one("#dataset-map")
        assert map_div is not None
        assert map_div.get("data-bbox") is None

        geometry_attr = map_div.get("data-geometry")
        assert geometry_attr is not None
        assert json.loads(geometry_attr) == ds.translated_spatial

        leaflet_css = soup.select_one('link[href*="leaflet.css"]')
        leaflet_js = soup.select_one('script[src*="leaflet.js"]')
        view_js = soup.select_one('script[src*="js/view_bbox_map.js"]')
        assert leaflet_css is not None
        assert leaflet_js is not None
        assert view_js is not None

    def test_dataset_detail_omits_map_when_spatial_missing(
        self, interface_with_dataset, db_client
    ):
        # Ensure no spatial key and verify no map container or Leaflet assets
        ds = interface_with_dataset.get_dataset_by_slug("test")
        ds.translated_spatial = None
        interface_with_dataset.db.commit()

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/dataset/test")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        # No map container
        assert soup.select_one("#dataset-map") is None

        # No Leaflet assets
        assert soup.select_one('link[href*="leaflet.css"]') is None
        assert soup.select_one('script[src*="leaflet.js"]') is None
        assert soup.select_one('script[src*="js/view_bbox_map.js"]') is None

    @pytest.mark.parametrize(
        "dataset_detail_url",
        [("/dataset/child-harvest-record"), ("/dataset/parent-harvest-record")],
    )
    def test_dataset_detail_collections(
        self, dataset_detail_url, interface_with_dataset, db_client
    ):
        """
        test child and parent dataset detail view
        """

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get(dataset_detail_url)

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        related_datasets_section = soup.select_one("section.usa-section")
        related_datasets_options = related_datasets_section.find_all(
            "div", class_="tablet:grid-col-6"
        )

        # both the tags and collection options are there
        assert len(related_datasets_options) == 2

        # tag content (the subset of tags and the button to show more)
        tags = related_datasets_options[0]
        assert tags.select_one("div.tag-list") is not None

        # not a fan of adding a condition like this but breaking out
        # this test into 2 would introduce a lot of redundancy
        if dataset_detail_url == "/dataset/parent-harvest-record":
            assert tags.select_one("button.usa-button") is not None

        # collection content
        collection = related_datasets_options[1]
        collection_count = soup.select_one("div.text-base-dark")

        assert collection_count.text.strip() == "Includes 1 related dataset"

        collection_link = collection.find(
            "a", href="/?collection=https://subdomain.domain/parent/example.shp.iso.xml"
        )
        assert collection_link is not None

    def test_metadata_landing_page_is_anchor(self, interface_with_dataset, db_client):
        """
        Test that the landingPage key in the Complete Metadata section
        is rendered as an anchor tag.
        """
        landing_page_url = "https://example.com/landing-page"
        ds = interface_with_dataset.get_dataset_by_slug("test")
        ds.dcat = {**ds.dcat, "landingPage": landing_page_url}
        interface_with_dataset.db.commit()

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/dataset/test")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        metadata_table = soup.select_one("table.metadata-table")
        assert metadata_table is not None

        landing_page_row = next(
            (
                row
                for row in metadata_table.select("tr")
                if row.select_one("th").get_text(strip=True) == "landingPage"
            ),
            None,
        )
        assert landing_page_row is not None

        anchor = landing_page_row.select_one("td a")
        assert anchor is not None
        assert anchor.get("href") == landing_page_url
        assert anchor.get_text(strip=True) == landing_page_url

    def test_check_jsonld(self, interface_with_dataset, db_client):

        with patch("app.routes.interface", interface_with_dataset):
            response = db_client.get("/dataset/test")

        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")

        jsonld = json.loads(
            soup.find_all("script", {"type": "application/ld+json"})[0].contents[0]
        )

        expected = {
            "@context": "https://schema.org/",
            "@type": "Dataset",
            "dateModified": "2026-03-04",
            "datePublished": None,
            "description": "this is the test description",
            "distribution": [
                {
                    "@type": "DataDownload",
                    "contentUrl": "https://example.com/test.csv",
                    "encodingFormat": "text/csv",
                }
            ],
            "identifier": "test identifier",
            "keywords": ["health", "education", "Health"],
            "license": None,
            "name": "test",
            "publisher": {"@type": "Organization", "name": "test publisher"},
            "url": None,
        }

        assert jsonld == expected
