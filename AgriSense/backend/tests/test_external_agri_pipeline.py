import base64
from datetime import datetime
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.core.config import Settings
from app.api.v1.agri_external_data import _parse_upload_records
from app.integrations.agri_external_data_collector import collector

_save_dataset = collector._save


@pytest.fixture(autouse=True)
def prevent_database_persistence(monkeypatch):
    monkeypatch.setattr(collector, "_save", lambda dataset: dataset)


class MockResponse:
    def __init__(self, body, url="https://provider.test/data"):
        self._body = body
        self.url = url

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def test_world_bank_keeps_provider_payload_separate_from_enriched_records(monkeypatch):
    payload = [
        {"page": 1, "pages": 1},
        [{
            "countryiso3code": "TUN", "date": "2022", "value": 1800,
            "indicator": {"id": "AG.YLD.CREL.KG", "value": "Cereal yield", "unit": "kg/ha"},
            "country": {"value": "Tunisia"},
        }],
    ]
    monkeypatch.setattr(collector.httpx, "get", lambda *args, **kwargs: MockResponse(payload))
    dataset = collector.collect_source("world_bank_tunisia_agriculture", ["AG.YLD.CREL.KG"])
    assert dataset["raw"] == [payload]
    assert dataset["records"] != payload
    record = dataset["records"][0]
    assert record["unit"] == "kg/ha"
    assert record["date"] == "2022"
    assert record["geography"]["country_code"] == "TUN"
    assert record["provenance"]["provider"] == "World Bank"


def test_world_bank_forwards_validated_pagination_and_date_params(monkeypatch):
    rows = [{
        "countryiso3code": "TUN", "date": str(year), "value": year,
        "indicator": {"id": "AG.YLD.CREL.KG", "value": "Cereal yield", "unit": "kg/ha"},
        "country": {"value": "Tunisia"},
    } for year in range(2015, 2020)]
    payload = [{"page": 2, "pages": 2}, rows]
    captured = {}

    def mock_get(_url, params, **_kwargs):
        captured.update(params)
        return MockResponse(payload)

    monkeypatch.setattr(collector.httpx, "get", mock_get)
    dataset = collector.collect_source(
        "world_bank_tunisia_agriculture",
        indicators=["AG.YLD.CREL.KG"],
        params={"per_page": "5", "page": "2", "date": "2015:2019"},
    )

    assert captured["per_page"] == 5
    assert captured["page"] == 2
    assert captured["date"] == "2015:2019"
    assert dataset["record_count"] == 5
    assert dataset["requested_parameters"]["params"]["per_page"] == 5


def test_world_bank_rejects_unsupported_or_invalid_params_before_network(monkeypatch):
    monkeypatch.setattr(collector.httpx, "get", lambda **_kwargs: pytest.fail("must reject before request"))
    with pytest.raises(ValueError, match="non pris en charge.*foo"):
        collector.collect_source(
            "world_bank_tunisia_agriculture",
            indicators=["AG.YLD.CREL.KG"],
            params={"foo": "bar"},
        )
    with pytest.raises(ValueError, match="per_page"):
        collector.collect_source(
            "world_bank_tunisia_agriculture",
            indicators=["AG.YLD.CREL.KG"],
            params={"per_page": "1001"},
        )
    with pytest.raises(ValueError, match="date"):
        collector.collect_source(
            "world_bank_tunisia_agriculture",
            indicators=["AG.YLD.CREL.KG"],
            params={"date": "2019:2010"},
        )


def test_nasa_power_labels_modeled_values_and_preserves_response(monkeypatch):
    payload = {
        "properties": {"parameter": {
            "T2M": {"20240101": 17.2},
            "PRECTOTCORR": {"20240101": -999},
        }},
        "parameters": {"T2M": "C", "PRECTOTCORR": "mm/day"},
        "geometry": {"coordinates": [10.1, 36.8, 24]},
    }
    monkeypatch.setattr(collector.httpx, "get", lambda *args, **kwargs: MockResponse(payload))
    dataset = collector.collect_source("nasa_power_point", params={
        "latitude": "36.8", "longitude": "10.1",
        "start": "2024-01-01", "end": "2024-01-01",
        "parameters": "T2M,PRECTOTCORR",
    })
    record = dataset["records"][0]
    assert dataset["raw"] == payload
    assert dataset["raw"] != dataset["records"]
    assert record["date"] == "2024-01-01"
    assert record["coordinates"] == {"latitude": 36.8, "longitude": 10.1}
    assert record["values"] == {"T2M": 17.2, "PRECTOTCORR": None}
    assert record["units"]["PRECTOTCORR"] == "mm/day"
    assert record["data_semantics"] == "modeled_estimate"
    assert record["quality_evidence"]["missing_parameters"] == ["PRECTOTCORR"]


def test_soilgrids_records_keep_depth_units_and_interpolation_semantics(monkeypatch):
    payload = {"properties": {"layers": [{
        "name": "clay", "unit_measure": {"mapped_units": "g/kg"},
        "depths": [{"label": "0-5cm", "values": {"mean": 240}}],
    }]}}
    monkeypatch.setattr(collector.httpx, "get", lambda *args, **kwargs: MockResponse(payload))
    dataset = collector.collect_source("soilgrids_profile", params={
        "latitude": "36.8", "longitude": "10.1",
        "properties": "clay", "depths": "0-5cm",
    })
    assert dataset["raw"] == payload
    record = dataset["records"][0]
    assert record["date"] is None
    assert record["coordinates"] == {"latitude": 36.8, "longitude": 10.1}
    assert record["depth"] == "0-5cm"
    assert record["values"] == {"clay": 240}
    assert record["units"] == {"clay": "g/kg"}
    assert record["data_semantics"] == "interpolated_estimate"
    assert record["quality_evidence"]["spatial_resolution_m"] == 250
    assert record["provenance"]["provider"] == "ISRIC"
    assert dataset["quality_evidence"]["records_with_coordinates"] == 1


def test_import_preserves_original_upload_and_records_provenance(monkeypatch):
    monkeypatch.setattr(collector, "_save", lambda dataset: dataset)
    original = {"filename": "source.csv", "content_base64": base64.b64encode(b"a,b\n1,2").decode()}
    dataset = collector.import_records(
        "onagri_tunisia", [{"date": "2024", "value": 2, "unit": "TND/kg"}],
        "source.csv", observed_at="2024-05-01", raw_payload=original,
    )
    assert dataset["raw"] == original
    assert dataset["records"][0]["data_semantics"] == "unclassified_import"
    assert dataset["records"][0]["provenance"]["source_document"] == "source.csv"
    assert dataset["quality_evidence"]["records_with_date"] == 1
    with pytest.raises(ValueError, match="observed_at"):
        collector.import_records("onagri_tunisia", [{"a": 1}], "source.csv", "not-a-date")


def test_duplicate_is_returned_without_persisting_or_rewriting(monkeypatch):
    duplicate = {"dataset_id": "existing", "records": [{"date": "2024"}], "raw": {"same": True}}
    monkeypatch.setattr(collector, "_existing_duplicate", lambda dataset: duplicate)
    monkeypatch.setattr(collector, "_persist_dataset", lambda dataset: pytest.fail("must not persist duplicate"))
    monkeypatch.setattr(collector, "_write_dataset_files", lambda dataset: pytest.fail("must not rewrite duplicate"))
    saved = _save_dataset({
        "dataset_id": "new", "source_id": "onagri_tunisia",
        "records": [{"date": "2024"}], "raw": {"new": True},
    })
    assert saved is duplicate


def test_persistence_failure_prevents_filesystem_success(monkeypatch):
    def fail_persist(_dataset):
        raise RuntimeError("db down")

    monkeypatch.setattr(collector, "_existing_duplicate", lambda dataset: None)
    monkeypatch.setattr(collector, "_persist_dataset", fail_persist)
    monkeypatch.setattr(collector, "_write_dataset_files", lambda dataset: pytest.fail("must not write files"))
    with pytest.raises(RuntimeError, match="db down"):
        _save_dataset({
            "dataset_id": "new", "source_id": "onagri_tunisia",
            "records": [{"date": "2024"}], "raw": {"payload": True},
        })


def test_fingerprint_ignores_retrieval_provenance():
    first = [{"date": "2024-01-01", "value": 4, "provenance": {"retrieved_at": "first"}}]
    later = [{"date": "2024-01-01", "value": 4, "provenance": {"retrieved_at": "later"}}]
    assert collector._records_fingerprint("nasa_power_point", first) == collector._records_fingerprint(
        "nasa_power_point", later
    )


def test_quality_evidence_flags_invalid_dates_and_coordinates():
    evidence = collector._quality_evidence("onagri_tunisia", [
        {"date": "not-a-date", "coordinates": {"latitude": 95, "longitude": 10}, "units": {"x": None}},
    ])
    assert evidence["invalid_dates"] == 1
    assert evidence["invalid_coordinates"] == 1
    assert evidence["records_with_units"] == 0
    assert any("date(s)" in warning for warning in evidence["warnings"])
    assert any("coordonnée(s)" in warning for warning in evidence["warnings"])


def test_gee_sources_are_reported_blocked_and_not_initialized(monkeypatch):
    monkeypatch.setattr("app.core.config.settings", Settings(_env_file=None))
    monkeypatch.setattr(
        "common.connectors.init_gee",
        lambda *args, **kwargs: pytest.fail("GEE initialization must not run"),
    )
    class FakeResult:
        def scalar_one(self):
            return 0

        def mappings(self):
            return self

        def all(self):
            return []

    class FakeConnection:
        def execute(self, *_args, **_kwargs):
            return FakeResult()

    class FakeEngine:
        def connect(self):
            class Context:
                def __enter__(self):
                    return FakeConnection()

                def __exit__(self, *_args):
                    return False
            return Context()

    monkeypatch.setattr(collector, "engine", FakeEngine())
    status = collector.pipeline_status()
    blocked = {item["id"]: item for item in status["configuration_blocked_sources"]}
    assert blocked["gpm_imerg_v07"]["status"] == "configuration_blocked"
    assert "Google Earth Engine n'est pas configuré" in blocked["gpm_imerg_v07"]["reason"]
    with pytest.raises(ValueError, match="Google Earth Engine n'est pas configuré"):
        collector.collect_source("gpm_imerg_v07")


def test_faostat_preserves_full_payload_and_adds_normalized_context(monkeypatch):
    payload = {
        "data": [{
            "Area": "Tunisia", "Area Code (M49)": "788", "Year": "2022",
            "Item": "Wheat", "Value": 123, "Unit": "t",
        }],
        "metadata": {"page": 1},
    }
    monkeypatch.setattr(collector.httpx, "get", lambda *args, **kwargs: MockResponse(payload))
    dataset = collector.collect_source("faostat_crop_production")
    assert dataset["raw"] == payload
    record = dataset["records"][0]
    assert record["date"] == "2022"
    assert record["unit"] == "t"
    assert record["geography"] == {"area": "Tunisia", "area_code": "788"}
    assert record["data_semantics"] == "national_statistic"


def test_xlsx_upload_parser_reads_tabular_values_without_evaluating_formulas():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["date", "yield", "formula"])
    sheet.append([datetime(2024, 1, 2), 3.5, "=1+2"])
    stream = BytesIO()
    workbook.save(stream)
    raw = stream.getvalue()
    records, payload = _parse_upload_records("source.xlsx", raw)
    assert records == [{"date": "2024-01-02T00:00:00", "yield": 3.5, "formula": None}]
    assert base64.b64decode(payload["content_base64"]) == raw


def test_xlsx_parser_rejects_bad_headers_and_invalid_workbooks():
    workbook = Workbook()
    workbook.active.append(["same", "same"])
    stream = BytesIO()
    workbook.save(stream)
    with pytest.raises(ValueError, match="en-têtes"):
        _parse_upload_records("bad.xlsx", stream.getvalue())
    with pytest.raises(ValueError, match="invalide"):
        _parse_upload_records("bad.xlsx", b"not an xlsx")
