"""Self-Service Analytics — Streamlit dashboard.

Charts for each /metrics/* endpoint plus an "Ask your data" box that calls
/nl-query, shows the generated SQL for transparency, and renders the result as a
table + auto-selected chart. Wires to the FastAPI backend using a logged-in JWT.

Run:  streamlit run dashboard/app.py
(The API must be running, e.g. uvicorn src.api.main:app --port 8000)
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from api_client import ApiClient, ApiError, API_BASE

st.set_page_config(page_title="Olist Analytics", page_icon="📊", layout="wide")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce string-encoded numbers (Decimals arrive as strings) to numeric,
    but only for columns where every value converts cleanly."""
    out = df.copy()
    for c in out.columns:
        s = pd.to_numeric(out[c], errors="coerce")
        if s.notna().all() and len(s) > 0:
            out[c] = s
    return out


def auto_chart(df: pd.DataFrame) -> None:
    """Pick a sensible chart for an arbitrary result set, or skip if none fits."""
    if df.empty or len(df.columns) < 2:
        return
    conv = _numeric(df)
    num_cols = [c for c in conv.columns if pd.api.types.is_numeric_dtype(conv[c])]
    cat_cols = [c for c in conv.columns if c not in num_cols]
    if num_cols and cat_cols:
        st.bar_chart(conv.set_index(cat_cols[0])[num_cols])
    elif len(num_cols) >= 2:
        st.line_chart(conv[num_cols])


def require_login() -> ApiClient:
    """Render the sidebar login and return an authenticated client (or stop)."""
    st.sidebar.header("🔐 Login")
    if "token" in st.session_state:
        st.sidebar.success(f"Signed in as **{st.session_state['username']}** "
                           f"({st.session_state['role']})")
        if st.sidebar.button("Log out"):
            for k in ("token", "username", "role"):
                st.session_state.pop(k, None)
            st.rerun()
        return ApiClient(token=st.session_state["token"])

    with st.sidebar.form("login"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", value="admin123", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        try:
            res = ApiClient().login(username, password)
            st.session_state["token"] = res["access_token"]
            st.session_state["role"] = res["role"]
            st.session_state["username"] = username
            st.rerun()
        except ApiError as e:
            st.sidebar.error(str(e))
        except Exception:  # noqa: BLE001
            st.sidebar.error(f"Cannot reach API at {API_BASE}. Is it running?")
    st.info("👈 Log in to view the dashboard. (default: admin / admin123)")
    st.stop()


# ---------------------------------------------------------------------------
# metric sections
# ---------------------------------------------------------------------------
def section_revenue(api: ApiClient) -> None:
    st.subheader("📈 Revenue trend")
    gran = st.selectbox("Granularity", ["month", "week", "day"], index=0)
    data = api.get("/metrics/revenue", {"granularity": gran})
    df = pd.DataFrame(data["points"])
    if df.empty:
        st.info("No data.")
        return
    df["period"] = pd.to_datetime(df["period"])
    st.line_chart(df.set_index("period")[["revenue", "running_total_revenue"]])
    with st.expander("Month-over-month growth %"):
        st.bar_chart(df.set_index("period")["mom_growth_pct"])


def section_categories(api: ApiClient) -> None:
    st.subheader("🏷️ Top categories by revenue")
    limit = st.slider("How many", 3, 20, 10, key="cat_limit")
    rows = api.get("/metrics/categories/top", {"limit": limit})
    df = pd.DataFrame(rows)
    st.bar_chart(df.set_index("category")["revenue"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def section_aov(api: ApiClient) -> None:
    st.subheader("🧾 Average order value")
    d = api.get("/metrics/aov")
    c1, c2 = st.columns(2)
    c1.metric("Overall AOV", f"R$ {d['overall']['aov']:,.2f}")
    c2.metric("Delivered orders", f"{d['overall']['orders']:,}")
    by_pt = pd.DataFrame(d["by_payment_type"])
    if not by_pt.empty:
        st.caption("AOV by payment type")
        st.bar_chart(by_pt.set_index("payment_type")["aov"])


def section_delivery(api: ApiClient) -> None:
    st.subheader("🚚 Delivery SLA")
    d = api.get("/metrics/delivery-sla")
    c1, c2 = st.columns(2)
    c1.metric("On-time %", f"{d['overall']['on_time_pct']}%")
    c2.metric("Avg delivery days", d["overall"]["avg_delivery_days"])
    df = pd.DataFrame(d["by_state"]).dropna(subset=["on_time_pct"])
    st.caption("On-time % by customer state")
    st.bar_chart(df.set_index("customer_state")["on_time_pct"])


def section_sellers(api: ApiClient) -> None:
    st.subheader("🏪 Seller scorecard")
    limit = st.slider("Top sellers", 5, 25, 10, key="seller_limit")
    rows = api.get("/metrics/sellers/scorecard", {"limit": limit})
    df = pd.DataFrame(rows)
    st.bar_chart(df.set_index("seller_id")["revenue"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def section_repeat(api: ApiClient) -> None:
    st.subheader("🔁 Repeat customers")
    d = api.get("/metrics/repeat-customers")
    c1, c2, c3 = st.columns(3)
    c1.metric("Repeat rate", f"{d['repeat_rate_pct']}%")
    c2.metric("Revenue share (repeat)", f"{d['repeat_revenue_share_pct']}%")
    c3.metric("Repeat customers", f"{d['repeat_customers']:,}")


def section_ask(api: ApiClient) -> None:
    st.subheader("💬 Ask your data")
    role = st.session_state.get("role")
    if role not in ("analyst", "admin"):
        st.info("NL-to-SQL is available to **analyst** and **admin** roles.")
        return
    st.caption("Ask a question in plain English — it's turned into a guarded, "
               "read-only SQL query.")
    question = st.text_input("Question",
                             placeholder="e.g. top 5 product categories by revenue in 2018")
    if st.button("Ask") and question.strip():
        with st.spinner("Generating SQL and running it..."):
            status, body = api.post("/nl-query", {"question": question})
        if status == 200:
            st.code(body["sql"], language="sql")
            df = pd.DataFrame(body["rows"])
            if df.empty:
                st.info("Query returned no rows.")
            else:
                auto_chart(df)
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.error(body.get("detail", "Request failed."))


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------
def main() -> None:
    st.title("📊 Self-Service Analytics — Olist")
    api = require_login()

    section_ask(api)
    st.divider()

    a, b = st.columns(2)
    with a:
        section_revenue(api)
        section_aov(api)
        section_sellers(api)
    with b:
        section_categories(api)
        section_delivery(api)
        section_repeat(api)


if __name__ == "__main__":
    main()
