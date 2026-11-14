
import pandas as pd

from common.connectors import init_gee, fetch_gpm_daily, fetch_gpm_monthly

# Configuration
LAT = 35.6815
LON = 10.102

START = "2025-01-01"
END = "2026-11-14"  # date exclusive

init_gee(project="nasa-challenge123456789")

print("1. Récupération des données GPM Daily...")
daily = fetch_gpm_daily(LAT, LON, START, END)

print("Nombre de jours récupérés :", len(daily))
print(daily.head())

# Vérification des dates
daily.index = pd.to_datetime(daily.index)
daily = daily.sort_index()

# Construction du calendrier quotidien complet
calendar = pd.date_range(
    start=START,
    end=pd.Timestamp(END) - pd.Timedelta(days=1),
    freq="D"
)

daily = daily.reindex(calendar)

# Nombre de jours valides par mois
monthly = daily["precip_mm"].resample("MS").agg(
    ["sum", "count"]
)

monthly["expected_days"] = monthly.index.days_in_month

# Un mois est valide uniquement si toutes ses journées sont disponibles
monthly["precip_mm"] = monthly["sum"].where(
    monthly["count"] == monthly["expected_days"]
)

monthly = monthly.drop(columns=["sum"])

print("\n2. Cumuls mensuels reconstruits :")
print(monthly.to_string())

print("\n3. Récupération de GPM Monthly...")
reference = fetch_gpm_monthly(LAT, LON, START, END)

comparison = monthly.join(
    reference.rename("gpm_monthly"),
    how="left"
)

comparison["difference_mm"] = (
    comparison["precip_mm"] - comparison["gpm_monthly"]
)

comparison["difference_percent"] = (
    comparison["difference_mm"]
    / comparison["gpm_monthly"].replace(0, float("nan"))
) * 100

print("\n4. Comparaison GPM Daily / GPM Monthly :")
print(comparison.round(3).to_string())

comparison.to_csv("gpm_daily_monthly_comparison.csv")

print("\nFichier créé : gpm_daily_monthly_comparison.csv")
