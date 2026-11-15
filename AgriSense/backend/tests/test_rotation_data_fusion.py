from app.engine.rotation.data_fusion import fuse_observations


def test_fusion_does_not_mutate_soil_values():
    soil_values = {
        "source": "soilgrids",
        "sampled_at": "2026-01-01",
        "ph": 7.2,
    }

    result = fuse_observations([], soil_values=soil_values)

    assert soil_values == {
        "source": "soilgrids",
        "sampled_at": "2026-01-01",
        "ph": 7.2,
    }
    assert result["donnees_fusionnees"]["ph"] == 7.2
    assert result["provenance"]["ph"]["source"] == "soilgrids"
    assert result["provenance"]["ph"]["observed_at"] == "2026-01-01"
    assert result["provenance"]["ph"]["quality_status"] == "unverified"
    assert result["qualite"]["variables_validees"] == 0


def test_fusion_does_not_mark_farmer_profile_as_validated():
    result = fuse_observations([], parcel_values={"latitude": 36.8})

    assert result["provenance"]["latitude"]["quality_status"] == "unverified"
    assert result["qualite"]["variables_validees"] == 0
