from pydantic import BaseModel, ConfigDict


class CropCalendarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    zone_id: str
    zone_name: str
    usage: str | None
    sow_start_month: int
    sow_start_day: int
    sow_end_month: int
    sow_end_day: int
    harvest_start_month: int
    harvest_start_day: int
    harvest_end_month: int
    harvest_end_day: int
    source: str


class CropSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    eco_port_code: int
    display_name: str
    scientific_name: str
    family: str | None
    category: str | None
    n_fixer: bool | None
    level: str
    rotation_eligible: bool
    cycle_min_days: float | None
    cycle_max_days: float | None
    kc_mid: float | None


class CropDetail(CropSummary):
    life_span: str | None
    ph_min: float | None
    ph_max: float | None
    ph_opt: float | None
    kc_ini: float | None
    kc_end: float | None
    stage_ini_days: int | None
    stage_dev_days: int | None
    stage_mid_days: int | None
    stage_late_days: int | None
    root_depth_max_m: float | None
    depletion_fraction_p: float | None
    t_base: float | None
    t_upper: float | None
    gdd_maturity: float | None
    gdd_yield_start: float | None
    ecology: dict | None
    sources: dict | None
    calendars: list[CropCalendarOut]


class AgroZone(BaseModel):
    zone_id: str
    zone_name: str


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    reference: str
    url: str | None
    accessed_on: str | None
    used_for: str | None
