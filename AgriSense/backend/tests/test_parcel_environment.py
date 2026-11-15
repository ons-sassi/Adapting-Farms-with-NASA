from app.services.frontend_analysis_service import crop_climate_scores
from app.services.parcel_environment import _ra_mm


def _climate(rain, et0, tmean, tmax):
    return {"monthly": [{"month": m, "rain_mm": rain, "et0_mm": et0, "tmean_c": tmean, "tmax_c": tmax} for m in range(1, 13)]}


def test_extraterrestrial_radiation_is_plausible():
    # FAO-56 : ~ 6 mm/j en hiver et ~ 17 mm/j en été vers 35° N
    assert 5 < _ra_mm(35.7, 15) < 8
    assert 15 < _ra_mm(35.7, 180) < 18


def test_water_score_depends_on_rain_and_irrigation():
    crop = {"cycleDays": 120, "kcMid": 1.0, "tBase": 0, "gddMaturity": 1500}
    dry = crop_climate_scores(crop, "03-01", _climate(10, 120, 15, 25), "none")
    irrigated = crop_climate_scores(crop, "03-01", _climate(10, 120, 15, 25), "sprinkler")
    assert dry["eau"] < 0.2 and irrigated["eau"] == 1.0
    assert dry["climat"] is not None


def test_scores_are_none_without_climate():
    assert crop_climate_scores({"cycleDays": 100}, "03-01", None, "none")["eau"] is None
