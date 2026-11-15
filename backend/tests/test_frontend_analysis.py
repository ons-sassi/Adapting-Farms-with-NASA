from datetime import date

from app.api.v1.frontend_bridge import _geometry_to_db, _geometry_to_front
from app.services.frontend_analysis_service import run_analysis
from app.services.frontend_catalog import get_crop, list_crops


def test_catalog_lists_tunisian_crops():
    crops = list_crops(eligible_only=True)
    ids = {c["id"] for c in crops}
    assert {"ble-dur", "orge", "pois-chiche", "sorgho"} <= ids
    assert get_crop("pois-chiche")["nFixer"] is True


def test_geometry_round_trip():
    points = [[35.68, 10.09], [35.69, 10.10], [35.67, 10.11]]
    assert _geometry_to_front(_geometry_to_db(points)) == points


def test_analysis_returns_scored_rotations():
    result = run_analysis(
        {"crops": ["ble-dur", "orge", "pois-chiche", "feve-feverole", "sorgho"],
         "priorities": {"water": 5, "soil": 4}, "horizon": 4, "constraints": {"forbidden": ["orge"]}},
        {"irrigationType": "drip", "zone": "Dorsale et Tell (Kairouan)", "crop": "Blé dur"},
        7.8, today=date(2026, 11, 15),
    )
    assert result["rotations"], result.get("notice")
    best = result["rotations"][0]
    assert len(best["years"]) == 4 and "orge" not in best["years"]
    assert 0 <= best["score"] <= 100
    assert result["recommendedId"] in {r["id"] for r in result["rotations"]}
    # La 1re culture ne répète pas la famille du blé (règle de rupture sanitaire).
    assert get_crop(best["years"][0])["familyLatin"] != "Gramineae"
