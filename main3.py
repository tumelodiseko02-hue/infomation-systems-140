import io
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure
from scipy import stats

# Same database file that data_capture.py uses. Keep both files in the same folder.
DB_PATH = Path(__file__).parent / "datacapture.sqlite"
# Same login database that your login-details script uses.
LOGIN_DB_PATH = Path(__file__).parent / "login.sqlite"

# Column names match the updated data_capture script, so both programs share tables.
# (Older tables with mixed-case names such as "Treatment_GROUP" are still recognised.)
EXPECTED_COLUMNS = [
    "site", "date", "crop", "treatment_group", "observer", "height", "leaf_count",
    "fresh_weight", "dry_weight", "chlorophyll_spad", "root_length", "yield_readings",
    "ph_readings", "ec", "dissolved_o2", "temp", "humidity", "nitrate", "phosphate",
]
REQUIRED_COLUMNS = {"site", "date", "crop", "observer"}

# Supabase table that receives a copy of every saved record.
SUPABASE_TABLE = "captured_data"

# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
def connect():
    return closing(sqlite3.connect(DB_PATH))


def quote(name: str) -> str:
    """Safely quote a table name (table names cannot use ? placeholders)."""
    return '"' + name.replace('"', '""') + '"'


def list_tables() -> list[str]:
    """Tables in the database that have the Agriminds columns."""
    with connect() as con:
        names = [
            r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        compatible = []
        for n in names:
            cols = {r[1].lower() for r in con.execute(f"PRAGMA table_info({quote(n)})")}
            if all(c.lower() in cols for c in EXPECTED_COLUMNS):
                compatible.append(n)
    return compatible


def create_table(name: str):
    cols = ",\n".join(
        f'"{c}" {"DATE" if c == "date" else "TEXT"}{" NOT NULL" if c in REQUIRED_COLUMNS else ""}'
        for c in EXPECTED_COLUMNS
    )
    with connect() as con:
        con.execute(f"CREATE TABLE IF NOT EXISTS {quote(name)}(\n{cols}\n)")
        con.commit()


def save_record(table: str, record: dict):
    cols = ", ".join(quote(c) for c in record)
    marks = ", ".join("?" for _ in record)
    with connect() as con:
        con.execute(f"INSERT INTO {quote(table)} ({cols}) VALUES ({marks})", tuple(record.values()))
        con.commit()


def load_records(table: str) -> pd.DataFrame:
    with connect() as con:
        # rowid lets us identify rows even though the table has no id column
        df = pd.read_sql_query(
            f"SELECT rowid AS id, * FROM {quote(table)} ORDER BY rowid DESC", con
        )
    df.columns = [c.lower() for c in df.columns]
    return df


def delete_record(table: str, rowid: int):
    with connect() as con:
        con.execute(f"DELETE FROM {quote(table)} WHERE rowid = ?", (rowid,))
        con.commit()


# --------------------------------------------------------------------------- #
# Supabase helpers (credentials come from .streamlit/secrets.toml, not the code)
# --------------------------------------------------------------------------- #
def get_supabase():
    """Return (client, None) or (None, reason)."""
    try:
        from supabase import create_client
    except ImportError:
        return None, "The 'supabase' package is not installed (pip install supabase)."
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except Exception:
        return None, "Supabase credentials not found in .streamlit/secrets.toml."
    try:
        return create_client(url, key), None
    except Exception as e:
        return None, f"Could not connect to Supabase: {e}"


def upload_to_supabase(record: dict):
    client, err = get_supabase()
    if err:
        return False, f"Saved locally only. {err}"
    try:
        client.table(SUPABASE_TABLE).insert(record).execute()
        return True, "Also uploaded to Supabase."
    except Exception as e:
        return False, f"Saved locally, but the Supabase upload failed: {e}"


def fetch_supabase():
    client, err = get_supabase()
    if err:
        return None, err
    try:
        rows = client.table(SUPABASE_TABLE).select("*").execute().data
        return pd.DataFrame(rows), None
    except Exception as e:
        return None, f"Could not read from Supabase: {e}"


# --------------------------------------------------------------------------- #
# Login helpers (same `details` table as the login script: id, username, pin)
# --------------------------------------------------------------------------- #
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60


def init_login_db():
    """Create the users table if missing. Never drops it, so users survive reruns."""
    with closing(sqlite3.connect(LOGIN_DB_PATH)) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS details("
            "id INTEGER PRIMARY KEY, username TEXT UNIQUE, pin INTEGER UNIQUE)"
        )
        if con.execute("SELECT COUNT(*) FROM details").fetchone()[0] == 0:
            # Starter users from the login script. Change or remove before sharing the code.
            con.execute("INSERT INTO details(id, username, pin) VALUES (1, 'tumelo', 4478)")
            con.execute("INSERT INTO details(id, username, pin) VALUES (2, 'katliso', 7228)")
        con.commit()


def check_login(username: str, pin_text: str):
    """Return the username if the details are correct, otherwise None."""
    if not username.strip() or not pin_text.strip().isdigit():
        return None
    with closing(sqlite3.connect(LOGIN_DB_PATH)) as con:
        row = con.execute(
            "SELECT username FROM details WHERE username=? AND pin=?",
            (username.strip(), int(pin_text.strip())),
        ).fetchone()
    return row[0] if row else None


# --------------------------------------------------------------------------- #
# Confidence interval (same method as "The real CI chart.py")
# --------------------------------------------------------------------------- #
def mean_and_conf_interval(data, confidence=0.95):
    data = np.asarray(data, dtype=float)
    n = len(data)
    mean = data.mean()
    sem = stats.sem(data)
    half = stats.t.ppf((1 + confidence) / 2, n - 1) * sem   # = stats.t.interval(...)
    return mean, mean - half, mean + half


# --------------------------------------------------------------------------- #
# Sidebar: choose or create a table
# --------------------------------------------------------------------------- #
def on_create_table():
    name = st.session_state.get("new_table_name", "").strip()
    if not name:
        st.session_state.table_msg = ("error", "Please enter a table name.")
    elif name.lower().startswith("sqlite_"):
        st.session_state.table_msg = ("error", "That name is reserved by SQLite.")
    else:
        create_table(name)
        st.session_state.table = name          # select it automatically
        st.session_state.new_table_name = ""
        st.session_state.table_msg = ("success", f"Table '{name}' is ready.")


st.set_page_config(page_title="Agriminds", page_icon="🌱", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "home"

init_login_db()

# ---------- LOGIN GATE: nothing below runs until the user is logged in ----------
if not st.session_state.get("user"):
    st.title("🌱 Agriminds")
    st.subheader("Log in")

    with st.form("login_form"):
        username = st.text_input("Username")
        pin = st.text_input("PIN", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if submitted:
        wait = int(st.session_state.get("locked_until", 0) - time.time())
        if wait > 0:
            st.error(f"Too many failed attempts. Try again in {wait} seconds.")
        else:
            user = check_login(username, pin)
            if user:
                st.session_state.user = user
                st.session_state.failed = 0
                st.rerun()
            else:
                st.session_state.failed = st.session_state.get("failed", 0) + 1
                if st.session_state.failed >= MAX_ATTEMPTS:
                    st.session_state.locked_until = time.time() + LOCKOUT_SECONDS
                    st.session_state.failed = 0
                st.error("Incorrect username or PIN.")
    st.stop()

tables = list_tables()

with st.sidebar:
    st.write(f"👤 Logged in as **{st.session_state.user}**")
    if st.button("Log out"):
        for key in ("user", "page", "table"):
            st.session_state.pop(key, None)
        st.rerun()
    st.divider()
    st.header("🗄️ Database")
    if tables:
        st.selectbox("Active table", tables, key="table")
    else:
        st.info("No tables yet. Create one below.")
    with st.expander("Create new table", expanded=not tables):
        st.text_input("New table name", key="new_table_name")
        st.button("Create table", on_click=on_create_table)
    if "table_msg" in st.session_state:
        kind, text = st.session_state.pop("table_msg")
        (st.error if kind == "error" else st.success)(text)
    st.caption(f"File: {DB_PATH.name}")

table = st.session_state.get("table") if tables else None

# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
# ---------- HOME ----------
if st.session_state.page == "home":
    st.title("🌱 Agriminds: Agritrial MVP")
    st.write("What would you like to do?")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Record Data", type="primary", width="stretch"):
            st.session_state.page = "trial"
            st.rerun()
    with col2:
        if st.button("View Data", width="stretch"):
            st.session_state.page = "view"
            st.rerun()
    with col3:
        if st.button("Analysis (CI chart)", width="stretch"):
            st.session_state.page = "analysis"
            st.rerun()
    if table:
        st.caption(f"Active table: **{table}**")

# ---------- TRIAL INFORMATION ----------
elif st.session_state.page == "trial":
    if not table:
        st.warning("Create a table in the sidebar first.")
        if st.button("← Back"):
            st.session_state.page = "home"
            st.rerun()
        st.stop()

    st.header(f"Trial Information  ·  table: {table}")
    site = st.text_input("Site ID")
    trial_date = st.date_input("Date")
    crop = st.text_input("Crop name")
    treatment = st.text_input("Treatment group")
    observer = st.text_input("Observer", value=st.session_state.user)

    st.header("🌻 Plant Metrics")
    height = st.number_input("Height (cm)", min_value=0.0)
    leaf_count = st.number_input("Leaf Count", min_value=0)
    fresh_weight = st.number_input("Fresh Weight (g)", min_value=0.0)
    dry_weight = st.number_input("Dry Weight (g)", min_value=0.0)
    chlorophyll = st.number_input("Chlorophyll Index (SPAD)", min_value=0.0)
    root_length = st.number_input("Root Length (cm)", min_value=0.0)
    yield_readings = st.number_input("Yield", min_value=0.0)

    st.header("🌤️ Environmental")
    ph = st.number_input("pH", min_value=0.0, max_value=14.0, value=7.0)
    ec = st.number_input("EC (mS/cm)", min_value=0.0)
    dissolved = st.number_input("Dissolved Oxygen (mg/L)", min_value=0.0)
    temp = st.number_input("Temperature (°C)")
    humidity = st.number_input("Humidity (%)", min_value=0.0, max_value=100.0)
    nitrate = st.number_input("Nitrate (mg/L)", min_value=0.0)
    phosphate = st.number_input("Phosphate (mg/L)", min_value=0.0)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save record", type="primary", width="stretch"):
            if not site.strip() or not crop.strip() or not observer.strip():
                st.error("Site ID, Crop and Observer are required.")
            else:
                record = {
                    "site": site.strip(),
                    "date": str(trial_date),
                    "crop": crop.strip(),
                    "treatment_group": treatment.strip(),
                    "observer": observer.strip(),
                    "height": str(height),
                    "leaf_count": str(leaf_count),
                    "fresh_weight": str(fresh_weight),
                    "dry_weight": str(dry_weight),
                    "chlorophyll_spad": str(chlorophyll),
                    "root_length": str(root_length),
                    "yield_readings": str(yield_readings),
                    "ph_readings": str(ph),
                    "ec": str(ec),
                    "dissolved_o2": str(dissolved),
                    "temp": str(temp),
                    "humidity": str(humidity),
                    "nitrate": str(nitrate),
                    "phosphate": str(phosphate),
                }
                save_record(table, record)
                st.success(f"Record saved to '{table}'.")
                ok, msg = upload_to_supabase(record)
                (st.success if ok else st.warning)(msg)
    with c2:
        if st.button("← Back", width="stretch"):
            st.session_state.page = "home"
            st.rerun()

# ---------- VIEW DATA ----------
elif st.session_state.page == "view":
    st.header(f"View Data  ·  table: {table or '-'}")
    if not table:
        st.info("Create a table in the sidebar first.")
    else:
        df = load_records(table)
        if df.empty:
            st.info("Nothing to show yet.")
        else:
            f1, f2 = st.columns(2)
            crops = f1.multiselect("Filter by crop", sorted(df["crop"].dropna().unique()))
            groups = f2.multiselect(
                "Filter by treatment group", sorted(df["treatment_group"].dropna().unique())
            )
            if crops:
                df = df[df["crop"].isin(crops)]
            if groups:
                df = df[df["treatment_group"].isin(groups)]

            st.caption(f"{len(df)} record(s)")
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button("Download CSV", df.to_csv(index=False),
                               f"{table}.csv", "text/csv")

            with st.expander("Delete a record"):
                rid = st.number_input("Record ID (the 'id' column)", min_value=1, step=1)
                if st.button("Delete"):
                    delete_record(table, int(rid))
                    st.rerun()

    if st.button("← Back"):
        st.session_state.page = "home"
        st.rerun()

# ---------- ANALYSIS: CONFIDENCE INTERVAL CHART ----------
elif st.session_state.page == "analysis":
    st.header("📊 Confidence interval chart")

    source = st.radio(
        "Data source",
        ["Local table", "Supabase (captured_data)", "Upload CSV"],
        horizontal=True,
    )
    df = None
    if source == "Local table":
        if table:
            df = load_records(table).drop(columns=["id"])
            st.caption(f"Using table: **{table}**")
        else:
            st.info("Create or select a table in the sidebar first.")
    elif source.startswith("Supabase"):
        df, err = fetch_supabase()
        if err:
            st.error(err)
    else:
        uploaded = st.file_uploader("CSV file (e.g. AgriTrial Data Canola.csv)", type="csv")
        if uploaded:
            df = pd.read_csv(uploaded)

    if df is not None and df.empty:
        st.info("No data found in this source yet.")
    elif df is not None:
        ignore = {"id", "created_at"}
        columns = [c for c in df.columns if c.lower() not in ignore]
        numeric_cols = [
            c for c in columns if pd.to_numeric(df[c], errors="coerce").notna().sum() >= 2
        ]

        def pick(options, prefs):
            lowered = [o.lower() for o in options]
            for p in prefs:
                if p.lower() in lowered:
                    return lowered.index(p.lower())
            return 0

        if not numeric_cols:
            st.warning("No numeric columns with at least 2 values were found.")
            st.stop()

        c1, c2, c3 = st.columns(3)
        group_col = c1.selectbox(
            "Group column", columns, index=pick(columns, ["Block", "treatment_group"])
        )
        variable = c2.selectbox(
            "Variable", numeric_cols, index=pick(numeric_cols, ["Mg", "yield_readings"])
        )
        level = c3.select_slider("Confidence level (%)", options=[90, 95, 99], value=95)

        labels = df[group_col].astype(str).str.strip()
        values = pd.to_numeric(df[variable], errors="coerce")
        available = sorted(labels[values.notna()].unique())
        default = [g for g in ["Control", "Combined"] if g in available] or available[:2]
        chosen = st.multiselect("Groups to compare", available, default=default)

        rows, skipped = [], []
        for g in chosen:
            data = values[(labels == g) & values.notna()]
            if len(data) < 2:
                skipped.append(g)
                continue
            m, lo, hi = mean_and_conf_interval(data, level / 100)
            rows.append({"group": g, "n": len(data), "mean": m, "lower": lo, "upper": hi})

        if skipped:
            st.warning(f"Skipped (need at least 2 values): {', '.join(skipped)}")

        if rows:
            res = pd.DataFrame(rows)
            with st.expander("Chart labels"):
                ylabel = st.text_input("Y-axis label", value=variable, key=f"y_{variable}")
                title = st.text_input(
                    "Title", value=f"{variable} with {level}% Confidence Interval",
                    key=f"t_{variable}_{level}",
                )

            fig = Figure(figsize=(max(5, 1.8 * len(res) + 2), 4.5))
            ax = fig.subplots()
            ax.errorbar(
                res["group"], res["mean"],
                yerr=[res["mean"] - res["lower"], res["upper"] - res["mean"]],
                fmt="s", capsize=6, color="green",
            )
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            ax.set_xlim(-1, len(res))
            st.pyplot(fig)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
            st.download_button("Download chart (PNG)", buf.getvalue(), "ci_chart.png", "image/png")

            st.dataframe(res.round(3), width="stretch", hide_index=True)
            st.caption(
                "If two intervals do not overlap, the groups likely differ. "
                "Overlapping intervals do not prove they are the same."
            )
        elif not skipped:
            st.info("Choose at least one group.")

    if st.button("← Back"):
        st.session_state.page = "home"
        st.rerun()