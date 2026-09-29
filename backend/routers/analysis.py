import os
import pandas as pd
from fastapi import APIRouter

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PARQUET = os.path.join(BASE, "parquet_data")


def _read(name, columns=None):
    path = os.path.join(PARQUET, f"{name}.parquet")
    if not os.path.exists(path):
        return None
    try:
        return pd.read_parquet(path, columns=columns)
    except Exception:
        return pd.read_parquet(path)


@router.get("/passenger-flow")
def get_analysis_passenger_flow():
    """Passenger-flow aggregations derived from raw parquet data
    (tickets, passengers, trips). Feeds the segmentation / weekly views
    that are not part of the dashboard passenger-flow summary."""
    passengers = _read("passengers")
    tickets = _read("tickets")
    trips = _read("trips")

    if passengers is None or tickets is None or trips is None:
        return {
            "status": "data_unavailable",
            "reason": "Raw parquet data is missing. Run the data generator and 00_csv_to_parquet first.",
        }

    # Passenger types (segmentation) from card_type counts.
    passenger_types = []
    if "card_type" in passengers.columns:
        counts = passengers["card_type"].value_counts()
        passenger_types = [
            {"name": str(k), "value": int(v)} for k, v in counts.items()
        ]

    # Hourly ticket purchases.
    hourly_tickets = []
    ts = pd.to_datetime(tickets["purchase_timestamp"], errors="coerce")
    if ts.notna().any():
        hourly = tickets.assign(_h=ts.dt.hour).groupby("_h").size()
        hourly_tickets = [
            {"hour": int(k), "tickets": int(v)} for k, v in hourly.items()
        ]

    # Weekday volume from trip start times.
    weekday_volume = []
    st = pd.to_datetime(trips["start_time"], errors="coerce")
    if st.notna().any():
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        wd = st.dt.dayofweek.value_counts()
        weekday_volume = [
            {"day": days[int(k)], "trips": int(v)} for k, v in wd.items()
        ]

    # Monthly registrations from passenger registration dates.
    monthly_registrations = []
    if "registration_date" in passengers.columns:
        rd = pd.to_datetime(passengers["registration_date"], errors="coerce")
        if rd.notna().any():
            mon = rd.dt.to_period("M").value_counts().sort_index()
            monthly_registrations = [
                {"month": str(k), "registrations": int(v)} for k, v in mon.items()
            ]

    return {
        "hourly_tickets": hourly_tickets,
        "weekday_volume": weekday_volume,
        "monthly_registrations": monthly_registrations,
        "passenger_types": passenger_types,
    }