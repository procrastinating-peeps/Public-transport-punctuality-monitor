import io
import csv
from datetime import datetime
import streamlit as st
import numpy as np
import pandas as pd


# ==========================================
# 1. TIME VALIDATION & DELAY FUNCTIONS
# ==========================================
def parse_and_validate_time(time_str: str) -> int | None:
    if time_str is None:
        return None
    cleaned = str(time_str).strip().upper()
    if cleaned in {"", "NA", "N/A", "NONE", "NULL", "CANCELLED", "MISSING"}:
        return None

    try:
        dt = datetime.strptime(cleaned, "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError:
        raise ValueError(f"Invalid time format '{time_str}'. Expected HH:MM (24-hour).")


def compute_delay_minutes(scheduled_str: str, actual_str: str) -> float | None:
    sched_mins = parse_and_validate_time(scheduled_str)
    if sched_mins is None:
        raise ValueError("Scheduled arrival time cannot be missing.")

    actual_mins = parse_and_validate_time(actual_str)
    if actual_mins is None:
        return None

    diff = actual_mins - sched_mins
    if diff < -720:
        diff += 1440
    elif diff > 720:
        diff -= 1440
    return float(diff)


# ==========================================
# 2. TRIP CLASS
# ==========================================
class Trip:
    ON_TIME_THRESHOLD = 5.0
    EXTREME_THRESHOLD = 20.0

    def __init__(
        self,
        trip_id: str,
        route: str,
        day: str,
        stop_name: str,
        scheduled_time: str,
        actual_time: str,
    ):
        self.trip_id = str(trip_id).strip()
        self.route = str(route).strip()
        self.day = str(day).strip()
        self.stop_name = str(stop_name).strip()
        self.scheduled_time = str(scheduled_time).strip()
        self.actual_time = str(actual_time).strip() if actual_time is not None else ""

        self.delay_mins = compute_delay_minutes(self.scheduled_time, self.actual_time)
        self.status = self._classify_status()

    def _classify_status(self) -> str:
        if self.delay_mins is None:
            return "Cancelled"
        if self.delay_mins < -1.0:
            return "Early"
        if self.delay_mins <= self.ON_TIME_THRESHOLD:
            return "On Time"
        if self.delay_mins <= self.EXTREME_THRESHOLD:
            return "Delayed"
        return "Severe Delay"

    def to_dict(self) -> dict:
        return {
            "trip_id": self.trip_id,
            "route": self.route,
            "day": self.day,
            "stop_name": self.stop_name,
            "scheduled_time": self.scheduled_time,
            "actual_time": self.actual_time if self.delay_mins is not None else "—",
            "delay_mins": self.delay_mins,
            "status": self.status,
            "is_missing": self.delay_mins is None,
            "is_extreme": (self.delay_mins is not None and self.delay_mins > self.EXTREME_THRESHOLD),
        }


# ==========================================
# 3. DATASET & FILE HELPERS
# ==========================================
DEFAULT_SHUTTLE_RECORDS = [
    {"trip_id": "TRP_101", "route": "Route A • Campus Loop", "day": "Monday", "stop_name": "North Gate", "scheduled_time": "08:00", "actual_time": "08:02"},
    {"trip_id": "TRP_102", "route": "Route A • Campus Loop", "day": "Monday", "stop_name": "Central Library", "scheduled_time": "08:15", "actual_time": "08:16"},
    {"trip_id": "TRP_103", "route": "Route A • Campus Loop", "day": "Monday", "stop_name": "Science Hub", "scheduled_time": "08:30", "actual_time": "08:34"},
    {"trip_id": "TRP_104", "route": "Route A • Campus Loop", "day": "Monday", "stop_name": "South Residence", "scheduled_time": "09:00", "actual_time": "09:28"},
    {"trip_id": "TRP_105", "route": "Route A • Campus Loop", "day": "Tuesday", "stop_name": "North Gate", "scheduled_time": "08:00", "actual_time": "08:01"},
    {"trip_id": "TRP_106", "route": "Route A • Campus Loop", "day": "Tuesday", "stop_name": "Central Library", "scheduled_time": "08:15", "actual_time": "08:14"},
    {"trip_id": "TRP_107", "route": "Route A • Campus Loop", "day": "Tuesday", "stop_name": "Science Hub", "scheduled_time": "08:30", "actual_time": "08:32"},
    {"trip_id": "TRP_108", "route": "Route A • Campus Loop", "day": "Wednesday", "stop_name": "North Gate", "scheduled_time": "08:00", "actual_time": "08:03"},

    {"trip_id": "TRP_201", "route": "Route B • City Express", "day": "Monday", "stop_name": "Central Station", "scheduled_time": "08:10", "actual_time": "08:19"},
    {"trip_id": "TRP_202", "route": "Route B • City Express", "day": "Monday", "stop_name": "Tech Park", "scheduled_time": "08:40", "actual_time": "08:52"},
    {"trip_id": "TRP_203", "route": "Route B • City Express", "day": "Monday", "stop_name": "Main Campus", "scheduled_time": "09:10", "actual_time": "CANCELLED"},
    {"trip_id": "TRP_204", "route": "Route B • City Express", "day": "Tuesday", "stop_name": "Central Station", "scheduled_time": "08:10", "actual_time": "08:17"},
    {"trip_id": "TRP_205", "route": "Route B • City Express", "day": "Tuesday", "stop_name": "Tech Park", "scheduled_time": "08:40", "actual_time": "08:55"},
    {"trip_id": "TRP_206", "route": "Route B • City Express", "day": "Wednesday", "stop_name": "Central Station", "scheduled_time": "08:10", "actual_time": ""},
    {"trip_id": "TRP_207", "route": "Route B • City Express", "day": "Wednesday", "stop_name": "Main Campus", "scheduled_time": "09:10", "actual_time": "09:35"},

    {"trip_id": "TRP_301", "route": "Route C • Night Shuttle", "day": "Monday", "stop_name": "Central Library", "scheduled_time": "23:30", "actual_time": "23:31"},
    {"trip_id": "TRP_302", "route": "Route C • Night Shuttle", "day": "Monday", "stop_name": "West Station", "scheduled_time": "23:55", "actual_time": "00:02"},
    {"trip_id": "TRP_303", "route": "Route C • Night Shuttle", "day": "Tuesday", "stop_name": "Central Library", "scheduled_time": "23:30", "actual_time": "23:29"},
    {"trip_id": "TRP_304", "route": "Route C • Night Shuttle", "day": "Tuesday", "stop_name": "West Station", "scheduled_time": "23:55", "actual_time": "23:58"},
    {"trip_id": "TRP_305", "route": "Route C • Night Shuttle", "day": "Wednesday", "stop_name": "Central Library", "scheduled_time": "23:30", "actual_time": "23:33"},
]


def records_to_csv_string(records: list[dict]) -> str:
    output = io.StringIO()
    fieldnames = ["trip_id", "route", "day", "stop_name", "scheduled_time", "actual_time"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def load_trips_from_csv(csv_text: str) -> list[Trip]:
    trips = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        trips.append(
            Trip(
                trip_id=row["trip_id"],
                route=row["route"],
                day=row["day"],
                stop_name=row["stop_name"],
                scheduled_time=row["scheduled_time"],
                actual_time=row.get("actual_time", ""),
            )
        )
    return trips


# ==========================================
# 4. PAGE CONFIGURATION & PROFESSIONAL THEME
# ==========================================
st.set_page_config(
    page_title="Transit Punctuality Monitor",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clean executive styling and cohesive colors
st.markdown(
    """
    <style>
        /* Main background and typography */
        .stApp {
            background-color: #F8FAFC;
            color: #0F172A;
        }
        /* Top Banner */
        .hero-header {
            background: linear-gradient(135deg, #0F2C59 0%, #1E40AF 100%);
            padding: 1.75rem 2rem;
            border-radius: 12px;
            color: #FFFFFF;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 12px rgba(15, 44, 89, 0.12);
        }
        .hero-header h1 {
            margin: 0;
            font-size: 1.85rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: #FFFFFF;
        }
        .hero-header p {
            margin: 0.35rem 0 0 0;
            font-size: 0.98rem;
            color: #CBD5E1;
        }
        /* Metric Cards */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-top: 4px solid #1E40AF;
            padding: 1rem 1.25rem;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.85rem;
            font-weight: 600;
            color: #475569;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.65rem;
            font-weight: 700;
            color: #0F172A;
        }
        /* Sidebar Polish */
        section[data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid #E2E8F0;
        }
        /* Multi-select tags in Navy/Slate instead of bright red */
        span[data-baseweb="tag"] {
            background-color: #EFF6FF !important;
            color: #1E40AF !important;
            border: 1px solid #BFDBFE !important;
        }
        /* Section Headings */
        .section-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #0F2C59;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header Banner
st.markdown(
    """
    <div class="hero-header">
        <h1>Public-Transport Punctuality Monitor</h1>
        <p>Service reliability analytics, arrival delay trends, and schedule adherence diagnostics</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Sidebar Controls ---
st.sidebar.markdown("### Schedule Data")
uploaded_csv = st.sidebar.file_uploader("Upload Route Schedule (CSV)", type=["csv"])
st.sidebar.download_button(
    label="Download Sample Schedule",
    data=records_to_csv_string(DEFAULT_SHUTTLE_RECORDS),
    file_name="shuttle_schedule_records.csv",
    mime="text/csv",
    use_container_width=True,
)

try:
    csv_data = (
        uploaded_csv.getvalue().decode("utf-8")
        if uploaded_csv is not None
        else records_to_csv_string(DEFAULT_SHUTTLE_RECORDS)
    )
    trip_objects = load_trips_from_csv(csv_data)
except Exception as err:
    st.error(f"Schedule Validation Error: {err}")
    st.stop()

df = pd.DataFrame([t.to_dict() for t in trip_objects])

st.sidebar.markdown("---")
st.sidebar.markdown("### View Filters")
all_routes = sorted(df["route"].unique())
all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
present_days = [d for d in all_days if d in df["day"].unique()] + [
    d for d in df["day"].unique() if d not in all_days
]

selected_routes = st.sidebar.multiselect("Transit Routes", options=all_routes, default=all_routes)
selected_days = st.sidebar.multiselect("Service Days", options=present_days, default=present_days)
exclude_extreme = st.sidebar.checkbox("Exclude Severe Delays (>20 min)", value=False)

if not selected_routes or not selected_days:
    st.warning("Please select at least one route and service day from the sidebar.")
    st.stop()

filtered_df = df[df["route"].isin(selected_routes) & df["day"].isin(selected_days)].copy()

# ==========================================
# 5. KEY PERFORMANCE INDICATORS
# ==========================================
valid_trips = filtered_df[~filtered_df["is_missing"]].copy()
if exclude_extreme:
    valid_trips = valid_trips[~valid_trips["is_extreme"]]

delays_arr = valid_trips["delay_mins"].to_numpy(dtype=float)

st.markdown('<div class="section-title">Service Performance Overview</div>', unsafe_allow_html=True)

if len(delays_arr) > 0:
    mean_delay = np.mean(delays_arr)
    median_delay = np.median(delays_arr)
    std_delay = np.std(delays_arr)
    p90_delay = np.percentile(delays_arr, 90)
    otp_rate = np.mean(delays_arr <= Trip.ON_TIME_THRESHOLD) * 100
else:
    mean_delay = median_delay = std_delay = p90_delay = otp_rate = 0.0

missing_count = int(filtered_df["is_missing"].sum())
extreme_count = int(filtered_df["is_extreme"].sum())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("On-Time Rate (≤5 min)", f"{otp_rate:.1f}%")
k2.metric("Average Delay", f"{mean_delay:.1f} min", f"±{std_delay:.1f} min spread", delta_color="off")
k3.metric("Typical Delay (Median)", f"{median_delay:.1f} min")
k4.metric("90th Percentile Delay", f"{p90_delay:.1f} min")
k5.metric("Cancelled / Severe", f"{missing_count} / {extreme_count}")

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 6. CHARTS: DELAY COMPARISON & TIME-SERIES
# ==========================================
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown('<div class="section-title">Average vs. Typical Delay by Route (Minutes)</div>', unsafe_allow_html=True)
    if not valid_trips.empty:
        route_bar_df = (
            valid_trips.groupby("route")["delay_mins"]
            .agg(**{"Average Delay": "mean", "Typical Delay (Median)": "median"})
            .round(2)
        )
        st.bar_chart(
            route_bar_df,
            stack=False,
            color=["#1E40AF", "#0D9488"],  # Navy Blue & Teal
        )
    else:
        st.info("No completed trips available for the selected filters.")

with chart_col2:
    st.markdown('<div class="section-title">Arrival Delay Trend Across Schedule</div>', unsafe_allow_html=True)
    if not valid_trips.empty:
        ts_df = valid_trips.sort_values(["day", "scheduled_time"]).copy()
        ts_df["Schedule Slot"] = ts_df["day"].str[:3] + " " + ts_df["scheduled_time"]
        pivot_ts = ts_df.pivot_table(
            index="Schedule Slot", columns="route", values="delay_mins", aggfunc="mean"
        )
        st.line_chart(
            pivot_ts,
            color=["#1E40AF", "#D97706", "#0D9488"][: len(pivot_ts.columns)],  # Navy, Amber, Teal
        )
    else:
        st.info("No completed trips available for the selected filters.")

st.divider()

# ==========================================
# 7. ROUTE & DAY SUMMARY + JSON EXPORT
# ==========================================
header_col, export_col = st.columns([3, 1])
with header_col:
    st.markdown('<div class="section-title">Route & Day Punctuality Breakdown</div>', unsafe_allow_html=True)
with export_col:
    summary_df = (
        filtered_df.groupby(["route", "day"], as_index=False)
        .agg(
            Scheduled=("trip_id", "count"),
            Completed=("is_missing", lambda s: int((~s).sum())),
            Cancelled=("is_missing", "sum"),
            **{
                "Avg Delay (min)": ("delay_mins", "mean"),
                "Median Delay (min)": ("delay_mins", "median"),
                "On-Time (%)": (
                    "delay_mins",
                    lambda s: (s.dropna() <= Trip.ON_TIME_THRESHOLD).mean() * 100
                    if len(s.dropna())
                    else 0.0,
                ),
            },
        )
        .round(1)
        .rename(columns={"route": "Route", "day": "Day"})
    )
    st.download_button(
        label="Export Summary (JSON)",
        data=summary_df.to_json(orient="records", indent=2),
        file_name="transit_punctuality_summary.json",
        mime="application/json",
        use_container_width=True,
    )

st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# 8. SERVICE INSIGHTS & INCIDENT LOG
# ==========================================
st.markdown('<div class="section-title">Service Reliability Insights & Exceptions</div>', unsafe_allow_html=True)

anomalies_df = filtered_df[filtered_df["is_missing"] | filtered_df["is_extreme"]].copy()

eval_col1, eval_col2 = st.columns([1.15, 1])

with eval_col1:
    st.info(
        "**Key Operational Findings**\n\n"
        "* **Balanced Route Benchmarking:** Relying solely on average delay penalizes high-frequency routes "
        "for isolated traffic incidents (such as a single 28-minute delay on *Route A*). Pairing **Typical Delay (Median)** "
        "with **On-Time Rate** provides an equitable comparison across routes.\n"
        "* **Service Completion Accountability:** *Route B* experienced unfulfilled trips alongside chronic moderate delays. "
        "Tracking cancelled trips separately ensures incomplete schedules do not artificially inflate punctuality metrics."
    )

with eval_col2:
    if not anomalies_df.empty:
        st.markdown(f"**Flagged Service Exceptions ({len(anomalies_df)})**")
        display_anomalies = anomalies_df[
            ["trip_id", "route", "day", "stop_name", "scheduled_time", "status", "delay_mins"]
        ].rename(
            columns={
                "trip_id": "Trip ID",
                "route": "Route",
                "day": "Day",
                "stop_name": "Stop",
                "scheduled_time": "Scheduled",
                "status": "Status",
                "delay_mins": "Delay (min)",
            }
        )
        st.dataframe(display_anomalies, use_container_width=True, hide_index=True)
    else:
        st.success("All scheduled trips operated within normal parameters.")

with st.expander("View Full Trip Schedule Log"):
    log_df = filtered_df[
        ["trip_id", "route", "day", "stop_name", "scheduled_time", "actual_time", "delay_mins", "status"]
    ].rename(
        columns={
            "trip_id": "Trip ID",
            "route": "Route",
            "day": "Day",
            "stop_name": "Stop",
            "scheduled_time": "Scheduled",
            "actual_time": "Actual",
            "delay_mins": "Delay (min)",
            "status": "Status",
        }
    )
    st.dataframe(log_df, use_container_width=True, hide_index=True)