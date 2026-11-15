"""
serialisation.py : (dé)sérialisation JSON du résultat de get_donnees_zonales().

Permet de transporter `donnees` d'un service à l'autre (HTTP, file de messages, fichier) :

    payload = donnees_to_json(donnees)            # dict 100 % JSON (NaN -> null)
    donnees = donnees_from_json(payload)          # DataFrames / ndarrays / tuples restaurés
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_TUPLES = ("centroide", "periode")


def _enc(v):
    if isinstance(v, pd.DataFrame):
        data = v.astype(object).where(v.notna(), None).values.tolist()
        return {"__df__": {"columns": [str(c) for c in v.columns],
                           "index": [str(i) for i in v.index],
                           "index_is_date": isinstance(v.index, pd.DatetimeIndex),
                           "index_name": v.index.name, "data": data}}
    if isinstance(v, np.ndarray):
        if v.dtype.kind == "f":
            arr = np.where(np.isnan(v), None, v).tolist() if np.isnan(v).any() else v.tolist()
        else:
            arr = v.tolist()
        return {"__nd__": arr, "dtype": str(v.dtype)}
    if isinstance(v, dict):
        return {k: _enc(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_enc(x) for x in v]
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return None if np.isnan(v) else float(v)
    return v


def _dec(v):
    if isinstance(v, dict):
        if "__df__" in v:
            d = v["__df__"]
            idx = pd.DatetimeIndex(pd.to_datetime(d["index"]), name=d["index_name"]) \
                if d["index_is_date"] else pd.Index(d["index"], name=d["index_name"])
            return pd.DataFrame(d["data"], columns=d["columns"], index=idx).astype(float)
        if "__nd__" in v:
            return np.array(v["__nd__"], dtype=v["dtype"] if v["dtype"] != "float64" else float)
        return {k: _dec(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_dec(x) for x in v]
    return v


def donnees_to_json(donnees: dict) -> dict:
    return _enc(donnees)


def donnees_from_json(payload: dict) -> dict:
    out = _dec(payload)
    for k in _TUPLES:
        if k in out and out[k] is not None:
            out[k] = tuple(out[k])
    return out
