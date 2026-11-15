import httpx

from app.integrations.agri_external_data_collector import collector


def test_soilgrids_values_are_converted_with_d_factor(monkeypatch):
    body = {"properties": {"layers": [{
        "name": "phh2o", "unit_measure": {"d_factor": 10, "mapped_units": "pH*10", "target_units": "-"},
        "depths": [{"label": "0-5cm", "values": {"mean": 81}}],
    }]}}
    monkeypatch.setattr(collector.httpx, "get", lambda url, **kw: httpx.Response(
        200, json=body, request=httpx.Request("GET", url)))
    records, _, _ = collector._soilgrids({"latitude": 35.68, "longitude": 10.1}, 10)
    assert records[0]["values"] == {"phh2o": 8.1}
    assert records[0]["units"] == {"phh2o": "pH"}
    assert records[0]["values_raw"] == {"phh2o": 81}
