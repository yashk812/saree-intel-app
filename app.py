import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import json
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict
import numpy as np
import os

st.set_page_config(page_title="Kalyan Silks — Competitive Intel", layout="wide", page_icon="🥻")

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0f0f14; }
[data-testid="stSidebar"] { background: #16161e; border-right: 1px solid #2a2a3a; }
[data-testid="stSidebar"] * { color: #e0e0f0 !important; }
h1, h2, h3 { color: #f5c842 !important; }
.metric-card {
    background: #1e1e2e; border: 1px solid #2a2a3a; border-radius: 10px;
    padding: 18px 22px; text-align: center;
}
.metric-val { font-size: 2.2rem; font-weight: 700; color: #f5c842; }
.metric-lbl { font-size: 0.8rem; color: #888aaa; text-transform: uppercase; letter-spacing: 1px; }
.page-title { color: #f5c842; font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }
.page-sub { color: #888aaa; font-size: 0.9rem; margin-bottom: 20px; }
div[data-testid="stSelectbox"] label, div[data-testid="stMultiSelect"] label { color: #aaaacc !important; }
</style>
""", unsafe_allow_html=True)

# ── Load data ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    # Try geocoded CSV first, fall back to clean CSV
    data_file = "saree_master_geocoded.csv" if os.path.exists("saree_master_geocoded.csv") else "saree_master_clean.csv"
    df = pd.read_csv(data_file)

    with open("city_coords.json") as f:
        city_coords = json.load(f)
    city_coords_lower = {k.lower(): v for k, v in city_coords.items()}

    def get_lat_lng(row):
        # If geocoded CSV has valid coords, use them
        if "lat" in row and pd.notna(row.get("lat")) and row.get("lat") not in [None, ""]:
            try:
                return float(row["lat"]), float(row["lng"])
            except:
                pass
        # Fallback: city lookup
        for key in [str(row.get("City", "")), str(row.get("District", "")), str(row.get("State", ""))]:
            k = key.lower().strip()
            if k in city_coords_lower:
                return city_coords_lower[k]
            for ck, cv in city_coords_lower.items():
                if len(ck) > 4 and (ck in k or k in ck):
                    return cv
        return None, None

    df[["lat", "lng"]] = df.apply(lambda r: pd.Series(get_lat_lng(r)), axis=1)
    df = df.dropna(subset=["lat", "lng"])
    df["lat"] = df["lat"].astype(float)
    df["lng"] = df["lng"].astype(float)

    # Offset stores that share identical coords (same city fallback)
    rng = np.random.default_rng(42)
    coord_counts = defaultdict(int)
    new_lats, new_lngs = [], []
    for _, row in df.iterrows():
        key = (round(row["lat"], 4), round(row["lng"], 4))
        n = coord_counts[key]
        if n > 0:
            angle = (n * 137.5) % 360
            rad = np.radians(angle)
            offset = 0.003 * (1 + n // 8)
            new_lats.append(row["lat"] + offset * np.cos(rad))
            new_lngs.append(row["lng"] + offset * np.sin(rad))
        else:
            new_lats.append(row["lat"])
            new_lngs.append(row["lng"])
        coord_counts[key] += 1
    df["lat"] = new_lats
    df["lng"] = new_lngs

    df["State"] = df["State"].str.strip()
    df["City"] = df["City"].str.strip()
    df["District"] = df["District"].str.strip()
    return df, data_file

df, data_source = load_data()

# ── Company / brand config ─────────────────────────────────────────────────────
COMPANY_COLORS = {
    "Kalyan Silks": "#f5c842",   # Gold — target
    "Pothys":        "#e63946",
    "Marri Retail":  "#2196F3",
    "SSKL Ltd":      "#00BCD4",
    "RS Brothers":   "#FF9800",
    "Nalli":         "#9C27B0",
}

# Focus on domestic India states only (exclude international)
INTL_STATES = {"Oman", "Qatar", "UAE", "Singapore", "UK", "USA", "Canada", "Australia"}
df_india = df[~df["State"].isin(INTL_STATES)].copy()
FOCUS_STATES = sorted(df_india["State"].unique())

# ── Sidebar nav ────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🥻 Kalyan Silks\n### Competitive Intel")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", ["🗺️ Store Map", "📊 Company Stats", "🔍 Expansion Insights", "🔍 City Explorer", "📋 Master Data"])

if data_source == "saree_master_clean.csv":
    st.sidebar.markdown("---")
    st.sidebar.warning("⚠️ Using city-level coordinates.\nRun `geocode_stores.py` for exact store coordinates.", icon="📍")

st.sidebar.markdown("---")
st.sidebar.markdown(f"**{len(df_india)}** India stores · **{df['Company Name'].nunique()}** companies")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: STORE MAP
# ══════════════════════════════════════════════════════════════════════════════
if page == "🗺️ Store Map":
    st.markdown('<div class="page-title">🗺️ Store Map</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">All saree retail stores across India. Toggle companies, filter by geography.</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sel_states = st.multiselect("State", FOCUS_STATES, placeholder="All states")
    with col2:
        avail_dist = sorted(df_india[df_india["State"].isin(sel_states)]["District"].unique()) if sel_states else sorted(df_india["District"].unique())
        sel_district = st.selectbox("District", ["All Districts"] + avail_dist)
    with col3:
        avail_cities = sorted(df_india[df_india["District"] == sel_district]["City"].unique()) if sel_district != "All Districts" else sorted(df_india["City"].unique())
        sel_city = st.selectbox("City", ["All Cities"] + avail_cities)
    with col4:
        sel_companies = st.multiselect("Company", list(COMPANY_COLORS.keys()), default=list(COMPANY_COLORS.keys()), placeholder="All")

    # Filter
    mdf = df_india[df_india["State"].isin(sel_states)] if sel_states else df_india.copy()
    if sel_district != "All Districts": mdf = mdf[mdf["District"] == sel_district]
    if sel_city != "All Cities":        mdf = mdf[mdf["City"] == sel_city]
    mdf = mdf[mdf["Company Name"].isin(sel_companies)]

    zoom = 5 if not sel_states else (8 if sel_district == "All Districts" else 11)
    center_lat = mdf["lat"].mean() if len(mdf) else 15.0
    center_lng = mdf["lng"].mean() if len(mdf) else 79.0

    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom,
                   tiles="CartoDB positron", control_scale=True)
    mc = MarkerCluster(options={"maxClusterRadius": 40, "spiderfyOnMaxZoom": True})

    for _, row in mdf.iterrows():
        company = row["Company Name"]
        color = COMPANY_COLORS.get(company, "#888888")
        is_kalyan = company == "Kalyan Silks"

        popup_html = f"""
        <div style="font-family:sans-serif;min-width:200px">
          <b style="color:{color}">{row['Store Name']}</b><br>
          <span style="color:#666">{row.get('Remaining Address','')}</span><br><br>
          🏙️ {row['City']}, {row['District']}<br>
          📍 {row['State']} — {row['Pincode']}<br>
          🏷️ {row['Brand Name']}
        </div>"""

        folium.CircleMarker(
            location=[row["lat"], row["lng"]],
            radius=9 if is_kalyan else 7,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85 if is_kalyan else 0.6,
            weight=3 if is_kalyan else 1,
            tooltip=row["Store Name"],
            popup=folium.Popup(popup_html, max_width=280),
        ).add_to(mc)

    mc.add_to(m)

    # Legend
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:9999;background:#1e1e2e;
                border:1px solid #333;border-radius:8px;padding:12px 16px;font-family:sans-serif">
    """
    for company, color in COMPANY_COLORS.items():
        count = len(mdf[mdf["Company Name"] == company])
        legend_html += f'<div style="margin:4px 0"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{color};margin-right:8px"></span><span style="color:#ddd;font-size:12px">{company} ({count})</span></div>'
    legend_html += "</div>"
    m.get_root().html.add_child(folium.Element(legend_html))

    col_map, col_stats = st.columns([3, 1])
    with col_map:
        st_folium(m, width="100%", height=580, returned_objects=[])
    with col_stats:
        st.markdown("**Visible stores**")
        for company, color in COMPANY_COLORS.items():
            n = len(mdf[mdf["Company Name"] == company])
            if n:
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:6px 10px;margin:3px 0;background:#1e1e2e;border-left:3px solid {color};border-radius:4px"><span style="color:#ccc;font-size:13px">{company}</span><span style="color:{color};font-weight:700">{n}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="margin-top:10px;color:#888;font-size:12px">Total: <b style="color:#f5c842">{len(mdf)}</b></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: COMPANY STATS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Company Stats":
    st.markdown('<div class="page-title">📊 Company Stats</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Store distribution by company, state and city.</div>', unsafe_allow_html=True)

    sel_states2 = st.multiselect("Filter by State", FOCUS_STATES, placeholder="All states", key="stats_state")
    sdf = df_india[df_india["State"].isin(sel_states2)] if sel_states2 else df_india.copy()

    # Top KPI row
    cols = st.columns(len(COMPANY_COLORS))
    for i, (company, color) in enumerate(COMPANY_COLORS.items()):
        n = len(sdf[sdf["Company Name"] == company])
        with cols[i]:
            st.markdown(f"""<div class="metric-card" style="border-top:3px solid {color}">
                <div class="metric-val" style="color:{color}">{n}</div>
                <div class="metric-lbl">{company}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        # Stores by company bar chart
        company_counts = sdf.groupby("Company Name").size().reset_index(name="Stores")
        company_counts["Color"] = company_counts["Company Name"].map(COMPANY_COLORS)
        fig1 = px.bar(company_counts.sort_values("Stores", ascending=True),
                      x="Stores", y="Company Name", orientation="h",
                      color="Company Name",
                      color_discrete_map=COMPANY_COLORS,
                      title="Stores by Company")
        fig1.update_layout(
            paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
            font_color="#ccc", showlegend=False,
            title_font_color="#f5c842",
            xaxis=dict(gridcolor="#2a2a3a"), yaxis=dict(gridcolor="#2a2a3a"),
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        # Stores by state stacked bar
        state_company = sdf.groupby(["State", "Company Name"]).size().reset_index(name="Stores")
        fig2 = px.bar(state_company, x="State", y="Stores", color="Company Name",
                      color_discrete_map=COMPANY_COLORS, title="Stores by State")
        fig2.update_layout(
            paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
            font_color="#ccc", title_font_color="#f5c842",
            xaxis=dict(gridcolor="#2a2a3a", tickangle=45),
            yaxis=dict(gridcolor="#2a2a3a"),
            margin=dict(l=10, r=10, t=40, b=60)
        )
        st.plotly_chart(fig2, use_container_width=True)

    # City-level heatmap — primary vs compare
    st.markdown("#### City-level presence heatmap")
    all_companies = list(COMPANY_COLORS.keys())

    hm_col1, hm_col2, hm_col3 = st.columns([1, 2, 1])
    with hm_col1:
        primary_co = st.selectbox("Primary company", all_companies, index=0, key="hm_primary")
    with hm_col2:
        default_compare = [c for c in all_companies if c != primary_co]
        compare_cos = st.multiselect("Compare against", [c for c in all_companies if c != primary_co],
                                     default=default_compare, key="hm_compare")
    with hm_col3:
        top_n_hm = st.slider("Top N cities", 5, 50, 30, key="hm_topn")

    selected_cos = [primary_co] + [c for c in compare_cos if c != primary_co]
    city_pivot = (
        sdf[sdf["Company Name"].isin(selected_cos)]
        .groupby(["City", "Company Name"]).size()
        .unstack(fill_value=0)
        .reindex(columns=selected_cos, fill_value=0)
    )
    city_pivot = city_pivot.sort_values(primary_co, ascending=False).head(top_n_hm)

    z_vals = city_pivot.values
    text_vals = [[str(v) if v > 0 else "" for v in row] for row in z_vals]

    primary_color = COMPANY_COLORS.get(primary_co, "#f5c842")
    fig3 = go.Figure(data=go.Heatmap(
        z=z_vals,
        x=city_pivot.columns.tolist(),
        y=city_pivot.index.tolist(),
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=11, color="white"),
        colorscale=[[0, "#1e1e2e"], [0.01, "#1e1e2e"], [0.33, "#2a2a4a"], [0.66, "#e6a020"], [1, primary_color]],
        showscale=True,
        hoverongaps=False,
    ))
    fig3.update_layout(
        paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
        font_color="#ccc", title_font_color="#f5c842",
        title=f"Top {top_n_hm} Cities — {primary_co} vs selected companies",
        height=max(400, top_n_hm * 18),
        margin=dict(l=10, r=10, t=80, b=10),
        xaxis=dict(side="top")
    )
    st.plotly_chart(fig3, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: EXPANSION INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Expansion Insights":
    import math

    st.markdown('<div class="page-title">🔍 Expansion Insights</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Population/store analysis to identify how many new Kalyan Silks stores each city can absorb.</div>', unsafe_allow_html=True)

    tab_city, tab_state = st.tabs(["🏙️ City Opportunities", "🗺️ State Overview"])

    # ── Shared computation ─────────────────────────────────────────────────────
    KALYAN_STATES = set(df_india[df_india["Company Name"] == "Kalyan Silks"]["State"].unique())

    # City-level aggregation
    city_agg = df_india.groupby(["City", "State"]).agg(
        total_stores   = ("Store Name", "count"),
        kalyan_stores  = ("Company Name", lambda x: (x == "Kalyan Silks").sum()),
        pop_2026       = ("pop_2026", "first"),
        lat            = ("lat", "mean"),
        lng            = ("lng", "mean"),
    ).reset_index()
    city_district = df_india.groupby(["City","State"])["District"].agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "").reset_index()
    city_agg = city_agg.merge(city_district, on=["City","State"], how="left")

    comp_stores = df_india[df_india["Company Name"] != "Kalyan Silks"].groupby(["City","State"]).size().reset_index(name="competitor_stores")
    comp_names  = df_india[df_india["Company Name"] != "Kalyan Silks"].groupby(["City","State"])["Company Name"].apply(
        lambda x: ", ".join(sorted(x.unique()))
    ).reset_index(name="competitors_present")
    top_pins_agg = df_india.groupby(["City","State"])["Pincode"].apply(
        lambda x: ", ".join(x.value_counts().head(3).index.astype(str).tolist())
    ).reset_index(name="top_pincodes")
    comp_pins_agg = df_india[df_india["Company Name"] != "Kalyan Silks"].groupby(["City","State"])["Pincode"].apply(
        lambda x: ", ".join(x.value_counts().head(3).index.astype(str).tolist())
    ).reset_index(name="comp_pincodes")

    city_agg = city_agg.merge(comp_stores,    on=["City","State"], how="left")
    city_agg = city_agg.merge(comp_names,     on=["City","State"], how="left")
    city_agg = city_agg.merge(top_pins_agg,   on=["City","State"], how="left")
    city_agg = city_agg.merge(comp_pins_agg,  on=["City","State"], how="left")
    city_agg["competitor_stores"] = city_agg["competitor_stores"].fillna(0).astype(int)

    # ── State PS ratios ────────────────────────────────────────────────────────
    # State PS = state urban pop (sum of city pops in dataset) / total stores in state
    state_pop = df_india.drop_duplicates(subset=["City","State"]).groupby("State")["pop_2026"].sum().reset_index(name="state_urban_pop_2026")
    state_stores = df_india.groupby("State").size().reset_index(name="state_total_stores")
    state_ps_df = state_pop.merge(state_stores, on="State", how="left")
    state_ps_df["state_ps"] = state_ps_df["state_urban_pop_2026"] / state_ps_df["state_total_stores"]
    state_ps_map = dict(zip(state_ps_df["State"], state_ps_df["state_ps"]))

    # Focus-wide fallback avg
    has_pop = city_agg[city_agg["pop_2026"].notna()]
    focus_avg_ps = float(has_pop["pop_2026"].sum() / has_pop["total_stores"].sum()) if len(has_pop) > 0 else 100000.0

    city_agg["state_ps"]      = city_agg["State"].map(state_ps_map).fillna(focus_avg_ps)
    city_agg["city_ps"]       = (city_agg["pop_2026"] / city_agg["total_stores"]).round(0)
    city_agg["stores_needed"] = (city_agg["pop_2026"] / city_agg["state_ps"]).round(0).fillna(0).clip(lower=1).astype(int)
    city_agg["gap_stores"]    = (city_agg["stores_needed"] - city_agg["total_stores"]).clip(lower=0).fillna(0).astype(int)

    def kalyan_stores_to_open(row):
        gap = row["gap_stores"]
        if gap == 0: return 0
        share = 0.8 if row["State"] in KALYAN_STATES else 0.5
        return math.ceil(gap * share)

    city_agg["kalyan_stores_to_open"] = city_agg.apply(kalyan_stores_to_open, axis=1)
    city_agg["kalyan_share_pct"]      = city_agg["State"].apply(lambda s: "80%" if s in KALYAN_STATES else "50%")

    # Tier: distance to nearest Kalyan city
    kalyan_locs = df_india[df_india["Company Name"] == "Kalyan Silks"].dropna(subset=["lat","lng"])
    kalyan_lats = kalyan_locs["lat"].values
    kalyan_lngs = kalyan_locs["lng"].values
    kalyan_city_names = kalyan_locs["City"].values

    def haversine_km(lat1, lng1, lats2, lngs2):
        r = 6371
        dlat = np.radians(lats2 - lat1)
        dlng = np.radians(lngs2 - lng1)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lats2)) * np.sin(dlng/2)**2
        return r * 2 * np.arcsin(np.sqrt(a))

    def get_tier(row):
        if row["kalyan_stores"] > 0: return "P0 (Kalyan present)", row["City"], 0
        if pd.isna(row["lat"]) or pd.isna(row["lng"]): return "P3 (>200km)", None, None
        dists = haversine_km(row["lat"], row["lng"], kalyan_lats, kalyan_lngs)
        idx = dists.argmin(); d = round(float(dists[idx]))
        tier = "P1 (<100km)" if d < 100 else ("P2 (100-200km)" if d < 200 else "P3 (>200km)")
        return tier, kalyan_city_names[idx], d

    city_agg[["tier","nearest_kalyan","nearest_kalyan_km"]] = city_agg.apply(
        lambda r: pd.Series(get_tier(r)), axis=1
    )

    # ── TAB 1: CITY OPPORTUNITIES ──────────────────────────────────────────────
    with tab_city:
        st.caption(f"Each city benchmarked against its **state PS ratio** (state urban pop ÷ state total saree stores). Focus avg: **{int(focus_avg_ps):,}** people/store.")

        with st.expander("🧮 How it works", expanded=False):
            st.markdown(f"""
            **Focus States Avg PS** = Total pop (all focus state cities) ÷ Total stores = **{int(focus_avg_ps):,} people/store**

            | Metric | Formula |
            |--------|---------|
            | **State PS ratio** | Sum of city pops in state ÷ total saree stores in state |
            | **City PS ratio** | City pop ÷ all saree stores in city (Kalyan + competitors) |
            | **Stores city should have** | `round(city pop ÷ state PS ratio)` |
            | **Gap stores** | `max(0, should have − existing)` — total market gap |
            | **Kalyan stores to open** | Existing Kalyan state → 80% of gap · New state → 50% of gap (both rounded up) |
            | **Tier** | P0 = Kalyan present · P1 = <100km · P2 = 100-200km · P3 = >200km from nearest Kalyan city |

            Population: Census of India 2011 extrapolated to 2025 using state-level urban CAGRs.
            """)

        c1, c2, c3 = st.columns(3)
        with c1:
            filter_states = st.multiselect("State", FOCUS_STATES, default=[], key="ins_state", placeholder="All focus states")
        with c2:
            filter_tier = st.multiselect("Tier", ["P0 (Kalyan present)","P1 (<100km)","P2 (100-200km)","P3 (>200km)"],
                                          default=["P1 (<100km)","P2 (100-200km)"], key="ins_tier")
        with c3:
            min_gap = st.slider("Min Kalyan stores to open", 0, 10, 0, key="ins_mingap")

        idf_city = city_agg.copy()
        if filter_states: idf_city = idf_city[idf_city["State"].isin(filter_states)]
        if filter_tier:   idf_city = idf_city[idf_city["tier"].isin(filter_tier)]
        idf_city = idf_city[idf_city["kalyan_stores_to_open"] >= min_gap]
        idf_city = idf_city.sort_values("kalyan_stores_to_open", ascending=False).reset_index(drop=True)
        idf_city.index += 1

        # State PS reference cards
        active_states = filter_states if filter_states else FOCUS_STATES
        ps_cards = state_ps_df[state_ps_df["State"].isin(active_states)].sort_values("state_ps")
        if not ps_cards.empty:
            st.markdown("**State PS Ratios (benchmark):**")
            cols_ps = st.columns(min(len(ps_cards), 6))
            for i, (_, r) in enumerate(ps_cards.iterrows()):
                with cols_ps[i % len(cols_ps)]:
                    st.metric(
                        label=r["State"].replace("Andhra Pradesh","AP").replace("Maharashtra","MH"),
                        value=f"{int(r['state_ps']):,}",
                        help=f"Urban pop: {int(r['state_urban_pop_2026']):,} ÷ {int(r['state_total_stores'])} stores"
                    )

        # State summary cards
        state_summary = idf_city.groupby("State").agg(
            proposed=("kalyan_stores_to_open","sum"),
            num_cities=("City","count"),
        ).reset_index().merge(state_ps_df[["State","state_ps"]], on="State", how="left")
        if not state_summary.empty:
            st.markdown("**Proposed new Kalyan stores by state:**")
            cols_ss = st.columns(min(len(state_summary), 5))
            for i, (_, sr) in enumerate(state_summary.iterrows()):
                with cols_ss[i % len(cols_ss)]:
                    pct = "80%" if sr["State"] in KALYAN_STATES else "50%"
                    st.metric(
                        label=f"🏙️ {sr['State']}",
                        value=f"{int(sr['proposed'])} new stores",
                        delta=f"{int(sr['num_cities'])} cities | PS {int(sr['state_ps']):,}",
                        delta_color="off",
                        help=f"Kalyan share: {pct} of total demand gap"
                    )

        # Bar chart
        top10 = idf_city.head(10)
        if not top10.empty:
            fig_bar = px.bar(top10[::-1], x="kalyan_stores_to_open", y="City",
                             orientation="h", color="State",
                             title="Top 10 Cities — Kalyan Silks Stores to Open",
                             labels={"kalyan_stores_to_open":"Stores to Open","City":"City"})
            fig_bar.update_layout(
                paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
                font_color="#ccc", title_font_color="#f5c842",
                xaxis=dict(gridcolor="#2a2a3a"), yaxis=dict(gridcolor="#2a2a3a"),
                height=380, margin=dict(l=0,r=20,t=40,b=20)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Table
        st.subheader(f"📋 City Opportunities ({len(idf_city)} shown)")
        display_cols = {
            "City":"City", "State":"State", "District":"District", "tier":"Tier",
            "kalyan_stores_to_open":"Kalyan Stores to Open",
            "gap_stores":"Total Gap", "kalyan_share_pct":"Kalyan Share %",
            "kalyan_stores":"Kalyan Stores (now)", "total_stores":"Total Stores",
            "stores_needed":"Stores Should Have",
            "pop_2026":"Pop 2025 (est.)", "city_ps":"City PS Ratio",
            "competitor_stores":"Competitor Stores", "competitors_present":"Competitors",
            "nearest_kalyan":"Nearest Kalyan City", "nearest_kalyan_km":"Distance (km)",
            "comp_pincodes":"Top Competitor PINs",
        }
        show = idf_city[[c for c in display_cols if c in idf_city.columns]].rename(columns=display_cols).copy()
        for col in ["Pop 2025 (est.)","City PS Ratio"]:
            if col in show.columns:
                show[col] = show[col].apply(lambda x: int(x) if pd.notna(x) else None)

        def hl_stores(val):
            if val is None: return ""
            try:
                n = int(val)
                if n >= 5:  return "background-color: #ff9999; color: #000; font-weight: bold"
                if n >= 2:  return "background-color: #ffe066; color: #000; font-weight: bold"
                if n == 1:  return "background-color: #d4f0a0; color: #000"
            except: pass
            return ""

        try:
            styled = show.style.map(hl_stores, subset=["Kalyan Stores to Open"])
        except Exception:
            styled = show.style.applymap(hl_stores, subset=["Kalyan Stores to Open"])

        st.dataframe(styled, use_container_width=True, height=520,
                     column_config={
                         "Pop 2025 (est.)":      st.column_config.NumberColumn(format="%d"),
                         "City PS Ratio":        st.column_config.NumberColumn(format="%d"),
                         "Kalyan Stores to Open":st.column_config.NumberColumn(format="%d"),
                         "Total Gap":            st.column_config.NumberColumn(format="%d"),
                         "Stores Should Have":   st.column_config.NumberColumn(format="%d"),
                         "Distance (km)":        st.column_config.NumberColumn(format="%d"),
                     })

        # Map
        st.subheader("🗺️ Opportunity Map")
        st.caption("Bubble size = Kalyan stores to open. Red=P1, Orange=P2, Grey=P3. Gold = existing Kalyan.")
        map_df = idf_city[idf_city["kalyan_stores_to_open"] > 0].dropna(subset=["lat","lng"]).copy()

        if not map_df.empty:
            m2 = folium.Map(location=[map_df["lat"].mean(), map_df["lng"].mean()],
                            zoom_start=5, tiles="CartoDB positron")
            max_val = max(map_df["kalyan_stores_to_open"].max(), 1)
            tier_color = {"P0 (Kalyan present)":"#f5c842","P1 (<100km)":"#e63946",
                          "P2 (100-200km)":"#FF9800","P3 (>200km)":"#9E9E9E"}

            comp_pincode_map = df_india[df_india["Company Name"] != "Kalyan Silks"].groupby(["City","Pincode"]).size().reset_index(name="stores")

            for _, row in map_df.iterrows():
                val   = int(row["kalyan_stores_to_open"])
                r_sz  = max(5, int(val / max_val * 28))
                color = tier_color.get(row["tier"], "#e63946")
                pop_s = f"{int(row['pop_2026']):,}" if pd.notna(row.get("pop_2026")) else "N/A"
                ps_s  = f"{int(row['city_ps']):,}" if pd.notna(row.get("city_ps")) else "N/A"
                sps_s = f"{int(row['state_ps']):,}" if pd.notna(row.get("state_ps")) else "N/A"

                city_pins = comp_pincode_map[comp_pincode_map["City"] == row["City"]].sort_values("stores", ascending=False).head(5)
                pin_rows_html = "".join(
                    f"<tr><td style='padding:1px 8px 1px 0;color:#ccc'>{p['Pincode']}</td>"
                    f"<td style='color:#f5c842;font-weight:600'>{p['stores']} store{'s' if p['stores']>1 else ''}</td></tr>"
                    for _, p in city_pins.iterrows()
                )
                pin_section = (
                    f"<hr style='margin:4px 0'>"
                    f"<div style='font-size:11px;color:#aaa'>Top competitor pincodes:</div>"
                    f"<table style='font-size:12px;margin-top:2px'>{pin_rows_html}</table>"
                ) if not city_pins.empty else ""

                popup_html = f"""
                <div style='font-family:sans-serif;min-width:230px'>
                  <b style='font-size:14px'>🏙️ {row["City"]}, {row["State"]}</b><br>
                  <span style='color:{color}'><b>{row["tier"]}</b></span><br>
                  <hr style='margin:4px 0'>
                  🆕 <b>Kalyan stores to open: {val}</b> (gap: {int(row.get("gap_stores",0))}, share: {row.get("kalyan_share_pct","?")})<br>
                  🏪 Existing: {int(row["total_stores"])} total (Kalyan: {int(row["kalyan_stores"])})<br>
                  👥 Pop 2025: {pop_s}<br>
                  📐 City PS: {ps_s} | State PS: {sps_s}<br>
                  🏪 Competitors: {int(row.get("competitor_stores",0))}<br>
                  📍 Nearest Kalyan: {row.get("nearest_kalyan","N/A")} ({row.get("nearest_kalyan_km","?")} km)
                  {pin_section}
                </div>"""

                folium.CircleMarker(
                    location=[row["lat"], row["lng"]],
                    radius=r_sz, color=color, fill=True,
                    fill_color=color, fill_opacity=0.75,
                    popup=folium.Popup(popup_html, max_width=270),
                    tooltip=f"{row['City']}: {val} stores to open ({row['tier']})",
                ).add_to(m2)

            # Existing Kalyan stores
            kalyan_cluster = MarkerCluster(name="Kalyan Silks Existing").add_to(m2)
            for _, row in kalyan_locs.iterrows():
                folium.CircleMarker(
                    location=[row["lat"], row["lng"]],
                    radius=7, color="#f5c842", fill=True, fill_color="#f5c842", fill_opacity=1.0,
                    tooltip=f"✅ {row['Store Name']}",
                    popup=folium.Popup(
                        f"<b style='color:#f5c842'>{row['Store Name']}</b><br>{row['City']}, {row['State']}<br>PIN: {row['Pincode']}",
                        max_width=220),
                ).add_to(kalyan_cluster)

            folium.LayerControl().add_to(m2)
            st_folium(m2, width="100%", height=580, returned_objects=[])
        else:
            st.info("No cities match current filters.")

    # ── TAB 2: STATE OVERVIEW ──────────────────────────────────────────────────
    with tab_state:
        st.caption("State-level summary — where Kalyan operates today vs where we're proposing to enter.")

        COMPETITORS = ["Pothys","Marri Retail","SSKL Ltd","RS Brothers","Nalli"]

        bk_by_state   = df_india[df_india["Company Name"]=="Kalyan Silks"].groupby("State").size().reset_index(name="kalyan_stores_current")
        prop_by_state = city_agg.groupby("State").agg(
            kalyan_stores_proposed=("kalyan_stores_to_open","sum"),
            total_gap=("gap_stores","sum"),
        ).reset_index()

        comp_counts = {}
        for comp in COMPETITORS:
            comp_counts[comp] = df_india[df_india["Company Name"]==comp].groupby("State").size().reset_index(name=comp)

        state_tab = state_ps_df[["State","state_urban_pop_2026","state_ps"]].copy()
        state_tab = state_tab.merge(bk_by_state,   on="State", how="left")
        state_tab = state_tab.merge(prop_by_state, on="State", how="left")
        state_tab["kalyan_stores_current"]  = state_tab["kalyan_stores_current"].fillna(0).astype(int)
        state_tab["kalyan_stores_proposed"] = state_tab["kalyan_stores_proposed"].fillna(0).astype(int)
        state_tab["total_gap"]              = state_tab["total_gap"].fillna(0).astype(int)
        state_tab["kalyan_total_proposed"]  = state_tab["kalyan_stores_current"] + state_tab["kalyan_stores_proposed"]
        state_tab["kalyan_share"]           = state_tab["State"].apply(lambda s: "80%" if s in KALYAN_STATES else "50%")
        state_tab["status"]                 = state_tab["kalyan_stores_current"].apply(
            lambda x: "🟡 Existing Market" if x > 0 else "🔵 New Market"
        )
        for comp in COMPETITORS:
            state_tab = state_tab.merge(comp_counts[comp], on="State", how="left")
            state_tab[comp] = state_tab[comp].fillna(0).astype(int)
        state_tab["total_competitor_stores"] = state_tab[COMPETITORS].sum(axis=1).astype(int)
        state_tab = state_tab.sort_values("kalyan_stores_proposed", ascending=False).reset_index(drop=True)
        state_tab.index += 1

        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Focus States", len(state_tab))
        k2.metric("Existing Kalyan Markets", int((state_tab["kalyan_stores_current"]>0).sum()))
        k3.metric("New Markets", int((state_tab["kalyan_stores_current"]==0).sum()))
        k4.metric("Total New Kalyan Stores Proposed", int(state_tab["kalyan_stores_proposed"].sum()))
        st.markdown("---")

        # Bar chart
        fig_s = px.bar(
            state_tab.sort_values("kalyan_stores_proposed"),
            x="kalyan_stores_proposed", y="State", orientation="h",
            color="status",
            color_discrete_map={"🟡 Existing Market":"#f5c842","🔵 New Market":"#1565C0"},
            title="Proposed New Kalyan Silks Stores by State",
            labels={"kalyan_stores_proposed":"New Stores","State":"State"}
        )
        fig_s.update_layout(
            paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
            font_color="#ccc", title_font_color="#f5c842",
            xaxis=dict(gridcolor="#2a2a3a"), yaxis=dict(gridcolor="#2a2a3a"),
            height=420, margin=dict(l=0,r=20,t=40,b=20)
        )
        st.plotly_chart(fig_s, use_container_width=True)

        # Table
        st.subheader("📋 State Overview")
        disp_state = {
            "State":"State", "status":"Status",
            "kalyan_stores_current":"Kalyan Stores (now)",
            "total_gap":"Total Demand Gap", "kalyan_share":"Kalyan Share %",
            "kalyan_stores_proposed":"New Kalyan Stores",
            "kalyan_total_proposed":"Kalyan Total (after)",
            "state_urban_pop_2026":"Urban Pop 2025 (est.)",
            "state_ps":"State PS Ratio",
            "total_competitor_stores":"Total Competitor Stores",
        }
        for comp in COMPETITORS:
            disp_state[comp] = comp

        show_s = state_tab[[c for c in disp_state if c in state_tab.columns]].rename(columns=disp_state).copy()

        def hl_status(val):
            if "Existing" in str(val): return "background-color: #2a2200; color: #f5c842"
            if "New" in str(val):      return "background-color: #0d1e3a; color: #64b5f6"
            return ""

        def hl_proposed(val):
            if val is None: return ""
            try:
                n = int(val)
                if n >= 20: return "background-color: #ff9999; color: #000; font-weight: bold"
                if n >= 5:  return "background-color: #ffe066; color: #000; font-weight: bold"
            except: pass
            return ""

        try:
            styled_s = show_s.style.map(hl_status, subset=["Status"]).map(hl_proposed, subset=["New Kalyan Stores"])
        except Exception:
            styled_s = show_s.style.applymap(hl_status, subset=["Status"]).applymap(hl_proposed, subset=["New Kalyan Stores"])

        st.dataframe(styled_s, use_container_width=True, height=500,
                     column_config={
                         "Urban Pop 2025 (est.)":    st.column_config.NumberColumn(format="%d"),
                         "State PS Ratio":           st.column_config.NumberColumn(format="%d"),
                         "Kalyan Stores (now)":      st.column_config.NumberColumn(format="%d"),
                         "Total Demand Gap":         st.column_config.NumberColumn(format="%d"),
                         "New Kalyan Stores":        st.column_config.NumberColumn(format="%d"),
                         "Kalyan Total (after)":     st.column_config.NumberColumn(format="%d"),
                         "Total Competitor Stores":  st.column_config.NumberColumn(format="%d"),
                         **{comp: st.column_config.NumberColumn(format="%d") for comp in COMPETITORS},
                     })



# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: CITY EXPLORER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 City Explorer":
    import math, requests as req_lib

    GOOGLE_GEO_KEY    = st.secrets.get("GOOGLE_GEO_KEY", os.environ.get("GOOGLE_GEO_KEY", ""))
    ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    COMPETITORS_LIST  = ["Pothys", "Marri Retail", "SSKL Ltd", "RS Brothers", "Nalli"]

    st.title("🔍 City Archetype Explorer")
    st.caption("Deep-dive into representative cities to understand where new Kalyan Silks stores should open.")

    ARCHETYPE_CITIES = {
        "🔴 Bengaluru, KA":       {"City": "Bengaluru",     "State": "Karnataka",      "color": "#C62828"},
        "🟠 Mysuru, KA":          {"City": "Mysuru",         "State": "Karnataka",      "color": "#E65100"},
        "🟡 Chennai, TN":         {"City": "Chennai",        "State": "Tamil Nadu",     "color": "#F9A825"},
        "🟢 Coimbatore, TN":      {"City": "Coimbatore",     "State": "Tamil Nadu",     "color": "#2E7D32"},
        "🔵 Visakhapatnam, AP":   {"City": "Visakhapatnam",  "State": "Andhra Pradesh", "color": "#1565C0"},
        "🟣 Vijayawada, AP":      {"City": "Vijayawada",     "State": "Andhra Pradesh", "color": "#6A1B9A"},
    }

    KALYAN_STATES_CE = set(df_india[df_india["Company Name"] == "Kalyan Silks"]["State"].unique())

    @st.cache_data
    def get_state_ps_ce():
        sp = df_india.drop_duplicates(subset=["City","State"]).groupby("State")["pop_2026"].sum().reset_index(name="sp")
        st_ = df_india.groupby("State").size().reset_index(name="st")
        m = sp.merge(st_, on="State", how="left")
        m["sps"] = m["sp"] / m["st"]
        return dict(zip(m["State"], m["sps"]))

    state_ps_map_ce = get_state_ps_ce()

    def get_city_data_ce(city, state):
        city_df  = df_india[(df_india["City"] == city) & (df_india["State"] == state)].copy()
        kal_df   = city_df[city_df["Company Name"] == "Kalyan Silks"]
        comp_df  = city_df[city_df["Company Name"] != "Kalyan Silks"]
        pop      = city_df["pop_2026"].iloc[0] if len(city_df) > 0 and "pop_2026" in city_df.columns else None
        total    = len(city_df)
        kal_n    = len(kal_df)
        sps      = state_ps_map_ce.get(state, 100000)
        needed   = round(pop / sps) if pop else 0
        gap      = max(0, needed - total)
        share    = 0.8 if state in KALYAN_STATES_CE else 0.5
        kal_gap  = math.ceil(gap * share) if gap > 0 else 0
        comp_bd  = {c: int((city_df["Company Name"] == c).sum()) for c in COMPETITORS_LIST if (city_df["Company Name"] == c).sum() > 0}
        top_pins  = city_df["Pincode"].value_counts().head(5).index.astype(str).tolist()
        comp_pins = comp_df["Pincode"].value_counts().head(10).index.astype(str).tolist()
        kal_pins  = kal_df["Pincode"].value_counts().head(5).index.astype(str).tolist()
        return {
            "city_df": city_df, "kal_df": kal_df, "comp_df": comp_df,
            "pop": pop, "total": total, "kal_n": kal_n, "sps": sps,
            "needed": needed, "gap": gap, "share": share, "kal_gap": kal_gap,
            "comp_bd": comp_bd, "top_pins": top_pins, "comp_pins": comp_pins, "kal_pins": kal_pins,
        }

    def get_ai_rec_ce(city, state, data):
        if "ai_recs_ce" not in st.session_state: st.session_state["ai_recs_ce"] = {}
        if "ai_pins_ce" not in st.session_state: st.session_state["ai_pins_ce"] = {}
        ck = f"{city}_{state}"
        if ck in st.session_state["ai_recs_ce"]:
            return st.session_state["ai_recs_ce"][ck], st.session_state["ai_pins_ce"].get(ck, [])

        n_stores = max(data["kal_gap"], 1)
        comp_str = ", ".join([f"{k}: {v} stores" for k, v in data["comp_bd"].items()]) or "None"
        pop_str  = f"{int(data['pop']):,}" if data["pop"] else "N/A"

        prompt = f"""You are a retail expansion analyst for Kalyan Silks, a premium saree and ethnic wear retailer in India.

City: {city}, {state}
Population (2025 est.): {pop_str}
State PS ratio: {int(data['sps']):,} people/store
Total saree stores: {data['total']} (Kalyan: {data['kal_n']}, Competitors: {data['total'] - data['kal_n']})
Stores city should have: {data['needed']} | New Kalyan stores recommended: {n_stores}
Competitor breakdown: {comp_str}
Top pincodes by store density: {', '.join(data['top_pins'])}
Competitor store pincodes: {', '.join(data['comp_pins'])}
Existing Kalyan pincodes: {', '.join(data['kal_pins']) if data['kal_pins'] else 'None'}

IMPORTANT — use competitor pincodes as primary signals. Areas with multiple competitor stores have proven saree retail demand.

Provide:
1. A 2-sentence market opportunity summary (mention which pincodes/areas have highest competitor density)
2. Exactly {n_stores} specific locality recommendations in {city} with brief reasons — anchor to competitor pincodes
3. Key risks (1-2 lines)

Then on a NEW LINE output exactly this JSON (no markdown, no backticks):
LOCATIONS_JSON: [{{"area": "ShortName", "full_address": "Locality, {city}, {state}, India PINCODE", "pincode": "XXXXXX"}}]

Rules for LOCATIONS_JSON:
- List exactly {n_stores} locations
- "area": short display name (e.g. "Koramangala 5th Block")
- "full_address": VERY specific, geocodable — include street/landmark + neighbourhood + city + state + India + 6-digit pincode (e.g. "Near Forum Mall, Hosur Road, Koramangala, Bengaluru, Karnataka, India 560095")
- "pincode": correct 6-digit PIN for that exact locality
- All locations must be within {city} city limits
Keep total response under 450 words."""

        try:
            r = req_lib.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 800,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            full_text = r.json()["content"][0]["text"]
            rec_text, locations_raw = full_text, []
            if "LOCATIONS_JSON:" in full_text:
                parts         = full_text.split("LOCATIONS_JSON:")
                rec_text      = parts[0].strip()
                try: locations_raw = json.loads(parts[1].strip())
                except: locations_raw = []
            st.session_state["ai_recs_ce"][ck] = rec_text

            # Geocode each via Google
            pins = []
            city_df_g = data["city_df"].dropna(subset=["lat","lng"])
            for loc in locations_raw:
                area     = loc.get("area", "")
                address  = loc.get("full_address", f"{area}, {city}, {state}, India")
                pincode  = loc.get("pincode", "")
                try:
                    gr = req_lib.get(
                        "https://maps.googleapis.com/maps/api/geocode/json",
                        params={"address": address, "key": GOOGLE_GEO_KEY},
                        timeout=8
                    )
                    results = gr.json().get("results", [])
                    if results:
                        loc_g = results[0]["geometry"]["location"]
                        lat_g, lng_g = float(loc_g["lat"]), float(loc_g["lng"])
                        if 6.5 <= lat_g <= 37.5 and 67.5 <= lng_g <= 97.5:
                            pins.append({"area": area, "pincode": pincode, "lat": lat_g, "lng": lng_g})
                            continue
                except: pass
                # fallback: competitor pincode centroid
                if pincode and not city_df_g.empty:
                    pr = city_df_g[city_df_g["Pincode"].astype(str) == str(pincode)]
                    if not pr.empty:
                        pins.append({"area": area, "pincode": pincode,
                                     "lat": pr["lat"].mean(), "lng": pr["lng"].mean() + 0.003 * len(pins)})

            # fill remaining from comp_pins centroids
            if len(pins) < n_stores and not city_df_g.empty:
                for j, pin in enumerate(data["comp_pins"]):
                    if len(pins) >= n_stores: break
                    pr = city_df_g[city_df_g["Pincode"].astype(str) == str(pin)]
                    if not pr.empty:
                        pins.append({"area": f"PIN {pin} area", "pincode": pin,
                                     "lat": pr["lat"].mean(), "lng": pr["lng"].mean() + 0.003 * j})

            st.session_state["ai_pins_ce"][ck] = pins[:n_stores]
            return rec_text, pins[:n_stores]

        except Exception as e:
            err = f"⚠️ Could not generate recommendation: {e}"
            st.session_state["ai_recs_ce"][ck] = err
            st.session_state["ai_pins_ce"][ck]  = []
            return err, []

    # ── City + mode selector ───────────────────────────────────────────────────
    col_sel, col_mode = st.columns([3, 2])
    with col_sel:
        selected_label = st.selectbox("Select a city archetype", list(ARCHETYPE_CITIES.keys()))
    with col_mode:
        mode = st.radio("Mode", ["🤖 Auto Recommend", "✏️ Manual Pin Drop"], horizontal=True)

    cfg   = ARCHETYPE_CITIES[selected_label]
    city  = cfg["City"]; state = cfg["State"]; color = cfg["color"]
    data  = get_city_data_ce(city, state)
    share_lbl = "80% — existing Kalyan state" if data["share"] == 0.8 else "50% — new state for Kalyan"

    st.markdown(f"**{city}, {state}**")
    st.markdown("---")

    # ── KPI row ────────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Kalyan Stores",       data["kal_n"])
    k2.metric("Competitor Stores",   data["total"] - data["kal_n"])
    k3.metric("Population 2025",     f"{int(data['pop']):,}" if data["pop"] else "N/A",
              help=f"State PS ({state}): {int(data['sps']):,} people/store")
    k4.metric("Stores Should Have",  data["needed"], help=f"Total market gap: {data['gap']} stores")
    k5.metric("New Kalyan Stores",   data["kal_gap"], help=share_lbl)

    st.markdown("---")

    # ── Auto mode: pre-fetch AI before map renders ─────────────────────────────
    ck = f"{city}_{state}"
    if mode == "🤖 Auto Recommend" and data["kal_gap"] > 0 and ANTHROPIC_API_KEY:
        if ck not in st.session_state.get("ai_pins_ce", {}):
            with st.spinner(f"Generating AI recommendations for {city}… (~10 sec)"):
                get_ai_rec_ce(city, state, data)
            st.rerun()

    # ── Map + panel layout ─────────────────────────────────────────────────────
    map_col, panel_col = st.columns([3, 1])

    with panel_col:
        st.subheader("🏪 Competitor Breakdown")
        if data["comp_bd"]:
            fig_cb = px.bar(
                x=list(data["comp_bd"].values()),
                y=list(data["comp_bd"].keys()),
                orientation="h",
                color=list(data["comp_bd"].keys()),
                color_discrete_map={k: COMPANY_COLORS.get(k, "#888") for k in data["comp_bd"]},
            )
            fig_cb.update_layout(
                height=260, showlegend=False,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
                font_color="#ccc",
                yaxis_title=None, xaxis_title="Stores",
                xaxis=dict(gridcolor="#2a2a3a"), yaxis=dict(gridcolor="#2a2a3a"),
            )
            st.plotly_chart(fig_cb, use_container_width=True)
        else:
            st.info("No competitor stores in this city.")

        if mode == "✏️ Manual Pin Drop":
            st.subheader("📍 Dropped Pins")
            key_pins = f"dropped_pins_{city}_{state}"
            if key_pins not in st.session_state:
                st.session_state[key_pins] = []
            pins_dropped = st.session_state[key_pins]
            if pins_dropped:
                for i, p in enumerate(pins_dropped):
                    st.markdown(f"{i+1}. `{p['lat']:.4f}, {p['lng']:.4f}`")
                if st.button("🗑️ Clear all pins"):
                    st.session_state[key_pins] = []
                    st.rerun()
            else:
                st.caption("Click the map to drop pins.")

        elif mode == "🤖 Auto Recommend":
            ai_pins_panel = st.session_state.get("ai_pins_ce", {}).get(ck, [])
            if ai_pins_panel:
                st.subheader("📍 AI Pins")
                for i, p in enumerate(ai_pins_panel):
                    st.markdown(f"**{i+1}. {p['area']}**")
                    st.caption(f"PIN {p['pincode']} · {p['lat']:.4f}, {p['lng']:.4f}")
            if not ANTHROPIC_API_KEY:
                st.warning("Add ANTHROPIC_API_KEY to Streamlit secrets.")

    with map_col:
        city_stores = data["city_df"].dropna(subset=["lat","lng"])
        center_lat  = city_stores["lat"].mean() if not city_stores.empty else 15.0
        center_lng  = city_stores["lng"].mean() if not city_stores.empty else 79.0

        m = folium.Map(location=[center_lat, center_lng], zoom_start=13, tiles="CartoDB positron")

        # All competitors — same neutral grey (colour is in bar chart, not map)
        for _, row in data["comp_df"].dropna(subset=["lat","lng"]).iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lng"]],
                radius=8, color="#212121", fill=True,
                fill_color="#B0BEC5", fill_opacity=0.95,
                tooltip=f"⚫ {row['Company Name']}: {row['Store Name']}",
                popup=folium.Popup(
                    f"<b>{row['Store Name']}</b><br>{row['Company Name']}<br>PIN: {row['Pincode']}",
                    max_width=200
                )
            ).add_to(m)

        # Kalyan existing — gold
        for _, row in data["kal_df"].dropna(subset=["lat","lng"]).iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lng"]],
                radius=10, color="#f5c842", fill=True,
                fill_color="#f5c842", fill_opacity=1.0,
                tooltip=f"🥻 Kalyan: {row['Store Name']}",
                popup=folium.Popup(
                    f"<b style='color:#f5c842'>{row['Store Name']}</b><br>Kalyan Silks<br>PIN: {row['Pincode']}",
                    max_width=200
                )
            ).add_to(m)

        key_pins = f"dropped_pins_{city}_{state}"
        if key_pins not in st.session_state:
            st.session_state[key_pins] = []

        if mode == "✏️ Manual Pin Drop":
            for i, p in enumerate(st.session_state[key_pins]):
                folium.Marker(
                    location=[p["lat"], p["lng"]],
                    tooltip=f"📍 Proposed store {i+1}",
                    icon=folium.Icon(color="green", icon="plus", prefix="fa")
                ).add_to(m)
            map_data = st_folium(m, width="100%", height=520,
                                  returned_objects=["last_clicked"],
                                  key=f"map_{city}_{state}_manual")
            if map_data and map_data.get("last_clicked"):
                lc = map_data["last_clicked"]
                new_pin = {"lat": lc["lat"], "lng": lc["lng"]}
                if new_pin not in st.session_state[key_pins]:
                    st.session_state[key_pins].append(new_pin)
                    st.rerun()

        else:
            # Auto: drop AI pins
            ai_pins_map = st.session_state.get("ai_pins_ce", {}).get(ck, [])
            for i, p in enumerate(ai_pins_map):
                folium.Marker(
                    location=[p["lat"], p["lng"]],
                    tooltip=f"📍 Proposed #{i+1}: {p['area']}",
                    popup=folium.Popup(
                        f"<b style='color:#00E5FF'>📍 Proposed Kalyan #{i+1}</b><br>"
                        f"<b>{p['area']}</b><br>PIN: {p['pincode']}<br>AI-recommended",
                        max_width=220
                    ),
                    icon=folium.Icon(color="green", icon="plus", prefix="fa")
                ).add_to(m)
            st_folium(m, width="100%", height=520,
                      returned_objects=[], key=f"map_{city}_{state}_auto")

        # Legend
        legend_html = """
        <div style="position:fixed;bottom:20px;left:20px;z-index:9999;background:#1e1e2e;
                    border:1px solid #333;border-radius:8px;padding:10px 14px;font-family:sans-serif">
          <div style="margin:3px 0"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#f5c842;margin-right:6px"></span><span style="color:#ddd;font-size:11px">Kalyan Silks (existing)</span></div>
          <div style="margin:3px 0"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#616161;margin-right:6px"></span><span style="color:#ddd;font-size:11px">Competitors</span></div>
          <div style="margin:3px 0"><span style="color:#4CAF50;font-size:13px;margin-right:6px">✚</span><span style="color:#ddd;font-size:11px">Proposed location</span></div>
        </div>"""
        m.get_root().html.add_child(folium.Element(legend_html))

        # Download
        st.download_button(
            "⬇️ Download map as HTML",
            data=m._repr_html_(),
            file_name=f"{city}_expansion_plan.html",
            mime="text/html"
        )

    # ── AI recommendation text (below map, full width) ─────────────────────────
    if mode == "🤖 Auto Recommend":
        ai_text = st.session_state.get("ai_recs_ce", {}).get(ck, "")
        if ai_text:
            st.markdown("---")
            st.subheader("🤖 AI Recommendation")
            st.markdown(ai_text)

    # ── Pincode reference table ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📌 Pincode Reference")
    pin_rows_tbl = []
    for pin in data["top_pins"]:
        pin_s  = data["city_df"][data["city_df"]["Pincode"].astype(str) == str(pin)]
        kal_c  = int((pin_s["Company Name"] == "Kalyan Silks").sum())
        comp_c = int((pin_s["Company Name"] != "Kalyan Silks").sum())
        comps  = ", ".join(sorted(pin_s[pin_s["Company Name"] != "Kalyan Silks"]["Company Name"].unique()))
        proposed = ""
        if mode == "🤖 Auto Recommend":
            ai_pins_t = st.session_state.get("ai_pins_ce", {}).get(ck, [])
            if any(str(p.get("pincode","")) == str(pin) for p in ai_pins_t):
                proposed = "✅ AI Proposed"
        elif mode == "✏️ Manual Pin Drop":
            if st.session_state.get(f"dropped_pins_{city}_{state}"):
                proposed = "📍 Manual pins dropped"
        pin_rows_tbl.append({
            "Pincode":    pin,
            "Type":       "🥻 Kalyan Present" if kal_c > 0 else "⚫ Competitors Only",
            "Kalyan":     kal_c,
            "Competitors":comp_c,
            "Companies":  comps,
            "Status":     proposed,
        })
    if pin_rows_tbl:
        st.dataframe(pd.DataFrame(pin_rows_tbl), use_container_width=True, hide_index=True)



# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: MASTER DATA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Master Data":
    st.markdown('<div class="page-title">📋 Master Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Full cleaned store dataset with all metadata.</div>', unsafe_allow_html=True)

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        sel_states4 = st.multiselect("State", sorted(df["State"].unique()), placeholder="All", key="md_state")
    with col_f2:
        sel_comp4 = st.multiselect("Company", list(COMPANY_COLORS.keys()), placeholder="All", key="md_comp")
    with col_f3:
        search = st.text_input("🔍 Search store name", "")

    fdf = df.copy()
    if sel_states4: fdf = fdf[fdf["State"].isin(sel_states4)]
    if sel_comp4:   fdf = fdf[fdf["Company Name"].isin(sel_comp4)]
    if search:      fdf = fdf[fdf["Store Name"].str.contains(search, case=False, na=False)]

    show_cols = ["Store Name", "Brand Name", "Company Name", "City", "District", "State", "Pincode", "Remaining Address"]
    if "lat" in fdf.columns:
        show_cols += ["lat", "lng"]

    st.markdown(f"**{len(fdf)}** stores")
    st.dataframe(fdf[show_cols].reset_index(drop=True), use_container_width=True, height=500)

    csv_data = fdf[show_cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv_data, file_name="kalyan_silks_intel.csv", mime="text/csv")
