"""Winnings dashboard — reads the "Gambling Pool" Google Sheet live on each visit."""

from __future__ import annotations

import os
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Config ───────────────────────────────────────────────────────────────────
# The sheet must be shared as "Anyone with the link → Viewer".
SHEET_ID = os.environ.get("SHEET_ID", "1buqS9JdN2H8jAkd3eaaaf_djCxJaeAjU2KmjxvQW35Q")
SHEET_GID = os.environ.get("SHEET_GID", "0")  # Sheet1
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
LOCAL_CSV = os.environ.get("WINNINGS_CSV")  # optional: point at a local CSV for offline testing
CACHE_SECONDS = 60  # data is re-pulled at most once a minute; "Refresh" forces it

# Diverging pair: blue = up, red = down, gray = even
POS, NEG, NEUTRAL = "#2a78d6", "#e34948", "#9a9993"

st.set_page_config(page_title="Winnings Dashboard", page_icon="🎲", layout="wide")


# ── Data ─────────────────────────────────────────────────────────────────────
def parse_money(val) -> float | None:
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    n = float(s)
    return -n if neg else n


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.loc[:, ~raw.columns.astype(str).str.startswith("Unnamed")]
    raw.columns = [str(c).strip() for c in raw.columns]

    df = pd.DataFrame()
    df["Bet #"] = range(1, len(raw) + 1)  # sheet order (the sheet is roughly chronological)
    df["Date"] = pd.to_datetime(raw.get("Date"), errors="coerce")
    df["Opponent"] = (
        raw.get("Opponent").fillna("").astype(str).str.strip().str.title()
    )  # "david" → "David"
    df["Result"] = raw.get("Win").fillna("").astype(str).str.strip().str.title()
    df["Stake"] = raw.get("Amount").map(parse_money)
    signed = raw.get("AJD Amount").map(parse_money)

    # If the signed column is blank, derive it from Result + Amount
    derived = df["Stake"].where(df["Result"] == "Win", -df["Stake"]).where(
        df["Result"] != "Broke Even", 0.0
    )
    df["Net"] = signed.fillna(derived).fillna(0.0)

    # Drop empty rows (the sheet has ~900 blank formula rows at the bottom)
    df = df[df["Opponent"] != ""].copy()
    df["Bet #"] = range(1, len(df) + 1)
    return df.reset_index(drop=True)


@st.cache_data(ttl=CACHE_SECONDS, show_spinner="Pulling latest data from Google Sheets…")
def load_data() -> tuple[pd.DataFrame, pd.Timestamp]:
    src = LOCAL_CSV or CSV_URL
    raw = pd.read_csv(src, dtype=str)
    return clean(raw), pd.Timestamp.now(tz="America/New_York")


def money(x: float) -> str:
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def signed_money(x: float) -> str:
    return f"+${x:,.0f}" if x > 0 else money(x)


def base_layout(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=False,
        hovermode="closest",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=True,
                     zerolinecolor="rgba(128,128,128,0.5)", zerolinewidth=1)
    return fig


# ── Load ─────────────────────────────────────────────────────────────────────
try:
    df, fetched_at = load_data()
except Exception as e:  # noqa: BLE001
    st.error(
        "Couldn't read the Google Sheet. Make sure it's shared as "
        "**Anyone with the link → Viewer**.\n\n"
        f"Details: `{e}`"
    )
    st.stop()

# ── Header ───────────────────────────────────────────────────────────────────
head_l, head_r = st.columns([4, 1])
head_l.title("🎲 Winnings Dashboard")
with head_r:
    st.write("")
    if st.button("↻ Refresh data", width="stretch"):
        load_data.clear()
        st.rerun()
    st.caption(f"Data pulled {fetched_at:%b %-d, %-I:%M %p} ET")

# ── Filters (one row) ────────────────────────────────────────────────────────
opponents = sorted(df["Opponent"].unique())
dated = df["Date"].dropna()
min_d, max_d = dated.min().date(), dated.max().date()

f1, f2, f3 = st.columns([3, 2, 1.4])
picked = f1.multiselect("Opponent", opponents, placeholder="All opponents")
date_range = f2.date_input(
    "Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d, format="MM/DD/YYYY"
)
n_undated = int(df["Date"].isna().sum())
with f3:
    st.write("")
    include_undated = st.checkbox(
        f"Include undated ({n_undated})",
        value=True,
        help="Many rows in the sheet have no date. They're included unless you uncheck this. "
        "Undated rows can't be placed in a date range, so they are kept or dropped as a group.",
    )

view = df.copy()
if picked:
    view = view[view["Opponent"].isin(picked)]

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    full_range = date_range[0] == min_d and date_range[1] == max_d
    in_range = view["Date"].between(start, end)
    if include_undated:
        view = view[in_range | view["Date"].isna()]
    else:
        view = view[in_range]
    if not full_range and include_undated and n_undated:
        st.caption("ℹ️ Date range is narrowed but undated rows are still included — "
                   "uncheck *Include undated* to see only that window.")

if view.empty:
    st.info("No bets match these filters.")
    st.stop()

# ── KPIs ─────────────────────────────────────────────────────────────────────
wins = int((view["Result"] == "Win").sum())
losses = int((view["Result"] == "Loss").sum())
evens = int((view["Result"] == "Broke Even").sum())
decided = wins + losses
net = view["Net"].sum()

k = st.columns(6)
k[0].metric("Net winnings", signed_money(net))
k[1].metric("Record (W-L-E)", f"{wins}-{losses}-{evens}")
k[2].metric("Win rate", f"{wins / decided:.0%}" if decided else "—")
k[3].metric("Total won", money(view.loc[view["Net"] > 0, "Net"].sum()))
k[4].metric("Total lost", money(view.loc[view["Net"] < 0, "Net"].sum()))
k[5].metric("Bets", f"{len(view)}")

st.divider()

# ── Charts ───────────────────────────────────────────────────────────────────
c1, c2 = st.columns([3, 2])

with c1:
    st.subheader("Running total")
    st.caption("Cumulative net, in the order bets appear in the sheet")
    seq = view.sort_values("Bet #").copy()
    seq["Cumulative"] = seq["Net"].cumsum()
    seq["n"] = range(1, len(seq) + 1)
    date_txt = seq["Date"].dt.strftime("%b %-d, %Y").fillna("No date")
    fig = go.Figure(
        go.Scatter(
            x=seq["n"], y=seq["Cumulative"], mode="lines",
            line=dict(color=POS, width=2, shape="hv"),
            customdata=list(zip(date_txt, seq["Opponent"], seq["Result"],
                                seq["Net"].map(signed_money), seq["Cumulative"].map(signed_money))),
            hovertemplate="<b>Bet %{x}</b> · %{customdata[0]}<br>"
                          "%{customdata[1]} — %{customdata[2]} %{customdata[3]}<br>"
                          "Running total: <b>%{customdata[4]}</b><extra></extra>",
        )
    )
    fig.update_xaxes(title="Bet #")
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    base_layout(fig).update_layout(hovermode="x")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with c2:
    st.subheader("Net by opponent")
    by_opp = (view.groupby("Opponent")["Net"].sum().sort_values().reset_index())
    colors = [POS if v > 0 else NEG if v < 0 else NEUTRAL for v in by_opp["Net"]]
    fig = go.Figure(
        go.Bar(
            x=by_opp["Net"], y=by_opp["Opponent"], orientation="h",
            marker=dict(color=colors, cornerradius=4),
            text=by_opp["Net"].map(signed_money), textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Net: %{text}<extra></extra>",
        )
    )
    fig.update_xaxes(tickprefix="$", tickformat=",.0f", gridcolor="rgba(128,128,128,0.18)",
                     zeroline=True, zerolinecolor="rgba(128,128,128,0.5)")
    fig.update_yaxes(showgrid=False, zeroline=False)
    base_layout(fig, height=max(300, 26 * len(by_opp) + 40))
    # Pad both ends so value labels sit clear of the bars and the opponent names
    lo, hi = min(0.0, by_opp["Net"].min()), max(0.0, by_opp["Net"].max())
    pad = (hi - lo) * 0.18 or 100
    fig.update_xaxes(range=[lo - (pad if lo < 0 else pad * 0.15), hi + pad])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", ticksuffix="  ")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

c3, c4 = st.columns([3, 2])

with c3:
    st.subheader("Net by month")
    dated_view = view.dropna(subset=["Date"])
    undated_here = int(view["Date"].isna().sum())
    st.caption("Dated bets only" + (f" — {undated_here} undated bets not shown" if undated_here else ""))
    if dated_view.empty:
        st.info("No dated bets in this selection.")
    else:
        monthly = (dated_view.set_index("Date")["Net"].resample("MS").sum().reset_index())
        colors = [POS if v > 0 else NEG if v < 0 else NEUTRAL for v in monthly["Net"]]
        fig = go.Figure(
            go.Bar(
                x=monthly["Date"], y=monthly["Net"],
                marker=dict(color=colors, cornerradius=4),
                customdata=monthly["Net"].map(signed_money),
                hovertemplate="<b>%{x|%b %Y}</b><br>Net: %{customdata}<extra></extra>",
            )
        )
        fig.update_xaxes(dtick="M1", tickformat="%b\n%Y")
        fig.update_yaxes(tickprefix="$", tickformat=",.0f")
        base_layout(fig)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with c4:
    st.subheader("Results")
    counts = pd.Series({"Win": wins, "Loss": losses, "Broke Even": evens})
    counts = counts[counts > 0]
    fig = go.Figure(
        go.Bar(
            x=counts.index, y=counts.values,
            marker=dict(color=[{"Win": POS, "Loss": NEG, "Broke Even": NEUTRAL}[i] for i in counts.index],
                        cornerradius=4),
            text=counts.values, textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{x}</b>: %{y} bets<extra></extra>",
        )
    )
    fig.update_yaxes(title="Bets")
    base_layout(fig)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

st.divider()

# ── Tables ───────────────────────────────────────────────────────────────────
st.subheader("Head-to-head")
h2h = (
    view.groupby("Opponent")
    .agg(
        Bets=("Net", "size"),
        W=("Result", lambda s: (s == "Win").sum()),
        L=("Result", lambda s: (s == "Loss").sum()),
        E=("Result", lambda s: (s == "Broke Even").sum()),
        Net=("Net", "sum"),
        Biggest_win=("Net", "max"),
        Biggest_loss=("Net", "min"),
        Last_played=("Date", "max"),
    )
    .reset_index()
)
decided_n = (h2h["W"] + h2h["L"]).astype(float)
h2h["Win rate"] = (100 * h2h["W"] / decided_n).where(decided_n > 0)
h2h = h2h.sort_values("Net", ascending=False)
h2h["Biggest_win"] = h2h["Biggest_win"].clip(lower=0)
h2h["Biggest_loss"] = h2h["Biggest_loss"].clip(upper=0)
st.dataframe(
    h2h,
    hide_index=True,
    width="stretch",
    height=35 * (len(h2h) + 1) + 3,  # show every opponent without inner scrolling
    column_config={
        "Net": st.column_config.NumberColumn(format="dollar"),
        "Biggest_win": st.column_config.NumberColumn("Biggest win", format="dollar"),
        "Biggest_loss": st.column_config.NumberColumn("Biggest loss", format="dollar"),
        "Win rate": st.column_config.NumberColumn(format="%.0f%%", help="Wins ÷ (wins + losses)"),
        "Last_played": st.column_config.DateColumn("Last dated bet", format="MMM D, YYYY"),
    },
)

st.subheader("All bets")
table = view[["Bet #", "Date", "Opponent", "Result", "Stake", "Net"]].sort_values("Bet #", ascending=False)
st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    height=420,
    column_config={
        "Date": st.column_config.DateColumn(format="MMM D, YYYY"),
        "Stake": st.column_config.NumberColumn(format="dollar"),
        "Net": st.column_config.NumberColumn(format="dollar"),
    },
)
st.download_button("Download filtered bets (CSV)", table.to_csv(index=False),
                   file_name="filtered_bets.csv", mime="text/csv")
