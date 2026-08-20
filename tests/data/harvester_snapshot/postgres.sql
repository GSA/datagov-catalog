--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5 (Debian 17.5-1.pgdg110+1)
-- Dumped by pg_dump version 17.5 (Debian 17.5-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: organization; Type: TABLE DATA; Schema: public; Owner: -
--

SET SESSION AUTHORIZATION DEFAULT;

ALTER TABLE public.organization DISABLE TRIGGER ALL;

COPY public.organization (name, logo, id, organization_type, description, slug, aliases) FROM stdin;
Test Org	https://raw.githubusercontent.com/GSA/datagov-harvester/refs/heads/main/app/static/assets/img/placeholder-organization.png	d925f84d-955b-4cb7-812f-dcfd6681a18f	Federal Government	Fixture org description	fixture-org	{testorg}
\.


ALTER TABLE public.organization ENABLE TRIGGER ALL;

--
-- Data for Name: harvest_source; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.harvest_source DISABLE TRIGGER ALL;

COPY public.harvest_source (organization_id, name, url, notification_emails, frequency, schema_type, source_type, notification_frequency, id, collection_parent_url) FROM stdin;
d925f84d-955b-4cb7-812f-dcfd6681a18f	Test Source	http://localhost:80/dcatus/dcatus.json	{email@example.com}	daily	dcatus1.1: federal	document	always	2f2652de-91df-4c63-8b53-bfced20b276b	\N
\.


ALTER TABLE public.harvest_source ENABLE TRIGGER ALL;

--
-- Data for Name: harvest_job; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.harvest_job DISABLE TRIGGER ALL;

COPY public.harvest_job (harvest_source_id, status, job_type, date_created, date_finished, records_total, records_added, records_updated, records_deleted, records_errored, records_ignored, records_validated, id, records_warned) FROM stdin;
2f2652de-91df-4c63-8b53-bfced20b276b	new	harvest	2026-07-31 17:27:25.11341	2026-07-31 17:27:25.11341	10	2	0	0	8	0	0	6bce761c-7a39-41c1-ac73-94234c139c76	0
2f2652de-91df-4c63-8b53-bfced20b276b	new	harvest	2026-08-04 17:27:25.11341	\N	0	0	0	0	0	0	0	6def0db9-8776-4bae-aeda-201e865853ed	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-01 17:27:25.11341	2026-08-01 17:28:25.11341	85	23	12	3	5	42	80	8def432a-9b21-4d56-87e4-1c3a5b7f8901	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-02 17:27:25.11341	2026-08-02 17:27:25.11341	45	0	0	0	45	0	0	1a2b3c4d-5e6f-7890-abcd-ef1234567890	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-07-29 17:27:25.11341	2026-07-29 17:29:25.11341	67	15	28	7	2	15	65	9f8e7d6c-5b4a-3928-1765-fedcba098765	0
2f2652de-91df-4c63-8b53-bfced20b276b	in_progress	harvest	2026-08-04 17:27:25.11341	2026-08-04 17:31:25.11341	0	0	0	0	0	0	0	4e5f6a7b-8c9d-0123-4567-890abcdef123	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-03 17:27:25.11341	2026-08-03 17:28:25.11341	30	10	5	0	0	5	25	7c8d9e0f-1a2b-4c4d-9e6f-789012345678	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-02 17:27:25.11341	2026-08-02 17:29:25.11341	35	11	6	1	1	6	29	2b3c4d5e-6f7a-4b9c-8d1e-2f3456789abc	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-01 17:27:25.11341	2026-08-01 17:30:25.11341	40	12	7	2	2	7	33	5d6e7f8a-9b0c-4d2e-bf4a-5b6789cdef01	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-07-31 17:27:25.11341	2026-07-31 17:31:25.11341	45	13	8	3	3	8	37	0a1b2c3d-4e5f-4789-abcd-ef0123456789	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-07-30 17:27:25.11341	2026-07-30 17:32:25.11341	50	14	9	4	4	9	41	3f4a5b6c-7d8e-4f01-a345-6789abcdef12	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-07-29 17:27:25.11341	2026-07-29 17:28:25.11341	55	15	10	5	5	5	45	6b7c8d9e-0f1a-4b3c-8d5e-6f789012345a	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-07-28 17:27:25.11341	2026-07-28 17:29:25.11341	60	16	11	6	6	6	49	9e0f1a2b-3c4d-4e6f-b890-abcdef123456	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-03 17:27:25.11341	2026-08-03 17:30:25.11341	65	17	12	7	7	7	53	c2d3e4f5-6a7b-4c9d-8e1f-23456789abcd	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-02 17:27:25.11341	2026-08-02 17:31:25.11341	70	18	13	0	8	8	57	f5a6b7c8-9d0e-4f2a-bb4c-56789def0123	0
2f2652de-91df-4c63-8b53-bfced20b276b	complete	harvest	2026-08-01 17:27:25.11341	2026-08-01 17:32:25.11341	75	19	14	1	9	9	61	56789def-9d0e-4f2a-bb4c-56789def0123	0
\.


ALTER TABLE public.harvest_job ENABLE TRIGGER ALL;

--
-- Data for Name: harvest_record; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.harvest_record DISABLE TRIGGER ALL;

COPY public.harvest_record (identifier, harvest_job_id, harvest_source_id, source_hash, source_raw, date_created, date_finished, ckan_id, action, status, id, parent_identifier, source_transform) FROM stdin;
test_identifier-9	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "Fixture Dataset 1", "identifier": "test-identifier-9"}	2026-08-04 17:27:25.299704	\N	1234	create	success	09f073b3-00e3-4147-ba69-a5d0fd7ce021	\N	\N
test_identifier-10	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "Fixture Dataset 2", "identifier": "test-identifier-10"}	2026-08-04 17:27:25.305713	\N	1235	create	success	09f073b3-00e3-4147-ba69-a5d0fd7ce022	\N	\N
test_identifier-1	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-0", "identifier": "test-0"}	2026-08-04 17:27:25.307938	\N	\N	create	error	0779c855-df20-49c8-9108-66359d82b77c	\N	\N
test_identifier-2	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-1", "identifier": "test-1"}	2026-08-04 17:27:25.310084	\N	\N	create	error	c218c965-3670-45c8-bfcd-f852d71ed917	\N	\N
test_identifier-3	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-2", "identifier": "test-2"}	2026-08-04 17:27:25.312155	\N	\N	create	error	e1f603cc-8b6b-483f-beb4-86bda5462b79	\N	\N
test_identifier-4	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-3", "identifier": "test-3"}	2026-08-04 17:27:25.314259	\N	\N	create	error	1c004473-0802-4f22-a16d-7a2d7559719e	\N	\N
test_identifier-5	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-4", "identifier": "test-4"}	2026-08-04 17:27:25.316277	\N	\N	create	error	deb12fa0-d812-4d6e-98f4-d4f7d776c6b3	\N	\N
test_identifier-6	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-5", "identifier": "test-5"}	2026-08-04 17:27:25.317795	\N	\N	create	error	27b5d5d6-808b-4a8c-ae4a-99f118e282dd	\N	\N
test_identifier-7	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-6", "identifier": "test-6"}	2026-08-04 17:27:25.319301	\N	\N	create	error	c232a2ca-6344-4692-adc2-29f618a2eff3	\N	\N
test_identifier-8	6bce761c-7a39-41c1-ac73-94234c139c76	2f2652de-91df-4c63-8b53-bfced20b276b	\N	{"title": "test-7", "identifier": "test-7"}	2026-08-04 17:27:25.320778	\N	\N	create	error	95021355-bad0-442b-98e9-475ecd849033	\N	\N
\.


ALTER TABLE public.harvest_record ENABLE TRIGGER ALL;

--
-- Data for Name: dataset; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.dataset DISABLE TRIGGER ALL;

COPY public.dataset (slug, dcat, organization_id, harvest_source_id, harvest_record_id, popularity, last_harvested_date, translated_spatial, id) FROM stdin;
fixture-dataset-1	{"title": "Fixture Dataset 1", "keyword": ["environment", "monitoring", "federal"], "license": "https://creativecommons.org/licenses/by/4.0/", "spatial": "-124.733253,24.544245,-66.954811,49.388611", "modified": "2024-01-15", "temporal": "2020-01-01T00:00:00Z/2023-12-31T23:59:59Z", "publisher": {"name": "Test Org", "@type": "org:Organization"}, "bureauCode": ["000:00"], "identifier": "test-identifier-9", "accessLevel": "public", "description": "A sample federal dataset for testing purposes. Contains environmental monitoring data.", "programCode": ["000:000"], "contactPoint": {"fn": "Data Steward", "@type": "vcard:Contact", "hasEmail": "mailto:data@example.gov"}, "distribution": [{"@type": "dcat:Distribution", "title": "Fixture Dataset 1 CSV", "mediaType": "text/csv", "downloadURL": "https://example.gov/data/dataset-1.csv"}]}	d925f84d-955b-4cb7-812f-dcfd6681a18f	2f2652de-91df-4c63-8b53-bfced20b276b	09f073b3-00e3-4147-ba69-a5d0fd7ce021	0	2026-07-31 17:27:25.11341	\N	a1b2c3d4-e5f6-7890-abcd-ef1234567891
fixture-dataset-2	{"title": "Fixture Dataset 2", "keyword": ["demographics", "survey", "population"], "license": "https://creativecommons.org/publicdomain/zero/1.0/", "modified": "2024-03-22", "publisher": {"name": "Test Org", "@type": "org:Organization"}, "bureauCode": ["000:00"], "identifier": "test-identifier-10", "accessLevel": "public", "description": "A secondary sample dataset for testing. Contains demographic survey results.", "programCode": ["000:001"], "contactPoint": {"fn": "Survey Coordinator", "@type": "vcard:Contact", "hasEmail": "mailto:survey@example.gov"}, "distribution": [{"@type": "dcat:Distribution", "title": "Fixture Dataset 2 JSON", "mediaType": "application/json", "downloadURL": "https://example.gov/data/dataset-2.json"}, {"@type": "dcat:Distribution", "title": "Fixture Dataset 2 Excel", "mediaType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "downloadURL": "https://example.gov/data/dataset-2.xlsx"}]}	d925f84d-955b-4cb7-812f-dcfd6681a18f	2f2652de-91df-4c63-8b53-bfced20b276b	09f073b3-00e3-4147-ba69-a5d0fd7ce022	0	2026-07-31 17:27:25.11341	\N	b2c3d4e5-f6a7-8901-bcde-f12345678902
\.


ALTER TABLE public.dataset ENABLE TRIGGER ALL;

--
-- Data for Name: locations; Type: TABLE DATA; Schema: public; Owner: -
--

ALTER TABLE public.locations DISABLE TRIGGER ALL;

COPY public.locations (name, type, display_name, the_geom, type_order, id) FROM stdin;
\.


ALTER TABLE public.locations ENABLE TRIGGER ALL;

--
-- PostgreSQL database dump complete
--

