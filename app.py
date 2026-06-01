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
page = st.sidebar.radio("Navigate", ["🗺️ Store Map", "📊 Company Stats", "🔍 Expansion Insights", "📋 Master Data"])

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
                   tiles="CartoDB dark_matter", control_scale=True)
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
    st.markdown('<div class="page-title">🔍 Expansion Insights</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Cities where competitors operate but Kalyan Silks has no presence — ranked by opportunity.</div>', unsafe_allow_html=True)

    # Score explainer
    with st.expander("🧮 How the Opportunity Score works", expanded=False):
        st.markdown("""
        For each **city**, we calculate:

        | Component | Formula |
        |-----------|---------|
        | **Competitor Presence** | Count of all non-Kalyan Silks stores in that city |
        | **Kalyan Silks Presence** | Count of Kalyan Silks stores in that city |
        | **Adjacency Bonus** | Kalyan Silks stores within chosen radius (outside this city), capped at max |
        | **Opportunity Score** | `(Competitor Presence × 10) − (Kalyan Silks Presence × 20) + (Adjacency Bonus × 5)` |

        **High score** = lots of competitor activity, little/no Kalyan Silks footprint.
        **Adjacency bonus** surfaces cities near existing Kalyan Silks stores — logical expansion steps.
        """)

    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1, 1, 1])
    with col_f1:
        sel_states3 = st.multiselect("Filter States", FOCUS_STATES, placeholder="All states", key="ins_state")
    with col_f2:
        top_n = st.slider("Top N cities", 5, 40, 20)
    with col_f3:
        radius_km = st.slider("Adjacency radius (km)", 25, 300, 100, step=25)
    with col_f4:
        adj_cap = st.slider("Adjacency cap", 1, 10, 5)

    idf = df_india[df_india["State"].isin(sel_states3)] if sel_states3 else df_india.copy()

    kalyan = idf[idf["Company Name"] == "Kalyan Silks"].copy()
    competitors = idf[idf["Company Name"] != "Kalyan Silks"].copy()
    kalyan_cities = set(kalyan["City"].str.lower().unique())

    # Build city-level score table
    city_comp = competitors.groupby(["City", "State"]).size().reset_index(name="Competitor Stores")
    city_kalyan = kalyan.groupby("City").size().reset_index(name="Kalyan Silks Stores")
    city_kalyan["City_lower"] = city_kalyan["City"].str.lower()

    city_comp["has_kalyan"] = city_comp["City"].str.lower().isin(kalyan_cities)
    city_comp["Kalyan Silks Stores"] = city_comp["City"].str.lower().map(
        city_kalyan.set_index("City_lower")["Kalyan Silks Stores"]
    ).fillna(0).astype(int)

    # Haversine adjacency bonus
    kalyan_coords = kalyan.groupby("City")[["lat", "lng"]].mean()

    def adjacency_bonus(city_row):
        """Count Kalyan Silks stores within radius_km of this city, capped at adj_cap."""
        city_coords_row = idf[idf["City"] == city_row["City"]][["lat", "lng"]].mean()
        if pd.isna(city_coords_row["lat"]):
            return 0
        clat, clng = np.radians(city_coords_row["lat"]), np.radians(city_coords_row["lng"])
        bonus = 0
        for _, kr in kalyan.iterrows():
            if kr["City"].lower() == city_row["City"].lower():
                continue
            klat, klng = np.radians(kr["lat"]), np.radians(kr["lng"])
            dlat, dlng = klat - clat, klng - clng
            a = np.sin(dlat/2)**2 + np.cos(clat) * np.cos(klat) * np.sin(dlng/2)**2
            dist = 6371 * 2 * np.arcsin(np.sqrt(a))
            if dist <= radius_km:
                bonus += 1
        return min(bonus, adj_cap)

    city_comp["Adjacency Bonus"] = city_comp.apply(adjacency_bonus, axis=1)
    city_comp["Opportunity Score"] = (
        city_comp["Competitor Stores"] * 10
        - city_comp["Kalyan Silks Stores"] * 20
        + city_comp["Adjacency Bonus"] * 5
    )
    city_comp = city_comp.sort_values("Opportunity Score", ascending=False)

    white_space = city_comp[~city_comp["has_kalyan"]].head(top_n).copy()

    # ── Charts row ─────────────────────────────────────────────────────────────
    col_ins1, col_ins2 = st.columns([3, 2])

    with col_ins1:
        st.markdown("#### 🟡 White Space Cities")
        if len(white_space) == 0:
            st.info("No white-space cities found for selected filters.")
        else:
            fig_opp = px.bar(
                white_space, x="Opportunity Score", y="City",
                orientation="h", color="State",
                title=f"Top {top_n} Opportunity Cities",
                hover_data=["Competitor Stores", "Adjacency Bonus", "State"]
            )
            fig_opp.update_layout(
                paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
                font_color="#ccc", title_font_color="#f5c842",
                yaxis=dict(autorange="reversed", gridcolor="#2a2a3a"),
                xaxis=dict(gridcolor="#2a2a3a"),
                margin=dict(l=10, r=10, t=40, b=10),
                showlegend=True, height=max(300, top_n * 22)
            )
            st.plotly_chart(fig_opp, use_container_width=True)

    with col_ins2:
        st.markdown("#### 📊 Competitor breakdown in top cities")
        if len(white_space) > 0:
            top_cities = white_space.head(15)["City"].tolist()
            comp_breakdown = competitors[competitors["City"].isin(top_cities)].groupby(
                ["City", "Company Name"]
            ).size().reset_index(name="count")
            fig_bd = px.bar(comp_breakdown, x="count", y="City", color="Company Name",
                            orientation="h", color_discrete_map=COMPANY_COLORS,
                            title="Who's in those cities")
            fig_bd.update_layout(
                paper_bgcolor="#0f0f14", plot_bgcolor="#1e1e2e",
                font_color="#ccc", title_font_color="#f5c842",
                yaxis=dict(autorange="reversed", gridcolor="#2a2a3a"),
                xaxis=dict(gridcolor="#2a2a3a"),
                margin=dict(l=10, r=10, t=40, b=10),
                height=max(300, 15 * 22)
            )
            st.plotly_chart(fig_bd, use_container_width=True)

    # ── Detailed table ─────────────────────────────────────────────────────────
    st.markdown("#### 📋 Detailed opportunity table")
    disp = white_space[["City", "State", "Competitor Stores", "Kalyan Silks Stores", "Adjacency Bonus", "Opportunity Score"]].copy()
    st.dataframe(disp.reset_index(drop=True), use_container_width=True, height=350)

    # ── Map ────────────────────────────────────────────────────────────────────
    st.markdown("#### 🗺️ Opportunity map")
    m2 = folium.Map(location=[15.0, 79.0], zoom_start=6, tiles="CartoDB dark_matter")

    for _, row in kalyan.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lng"]],
            radius=10, color="#f5c842", fill=True, fill_color="#f5c842",
            fill_opacity=0.9, weight=2,
            tooltip=f"✅ {row['Store Name']}",
            popup=folium.Popup(
                f"<b style='color:#f5c842'>{row['Store Name']}</b><br>📍 {row['City']}, {row['State']} — {row['Pincode']}",
                max_width=250
            )
        ).add_to(m2)

    city_coords_map = idf.groupby("City")[["lat","lng"]].mean().to_dict("index")
    for _, row in white_space.iterrows():
        city = row["City"]
        if city not in city_coords_map:
            continue
        clat = city_coords_map[city]["lat"]
        clng = city_coords_map[city]["lng"]
        score = row["Opportunity Score"]
        radius = max(6, min(22, score / 4))
        folium.CircleMarker(
            location=[clat, clng],
            radius=radius,
            color="#e63946", fill=True, fill_color="#e63946",
            fill_opacity=0.55, weight=1,
            tooltip=f"🎯 {city} — score {score}",
            popup=folium.Popup(
                f"<b style='color:#e63946'>{city}</b>, {row['State']}<br>"
                f"Competitor stores: <b>{row['Competitor Stores']}</b><br>"
                f"Kalyan Silks stores: <b>{row['Kalyan Silks Stores']}</b><br>"
                f"Adjacency bonus: <b>{row['Adjacency Bonus']}</b><br>"
                f"Opportunity score: <b>{score}</b>",
                max_width=260
            )
        ).add_to(m2)

    m2.get_root().html.add_child(folium.Element("""
    <div style="position:fixed;bottom:30px;left:30px;z-index:9999;background:#1e1e2e;
                border:1px solid #333;border-radius:8px;padding:12px 16px;font-family:sans-serif">
      <div style="margin:4px 0"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#f5c842;margin-right:8px"></span><span style="color:#ddd;font-size:12px">Kalyan Silks (existing)</span></div>
      <div style="margin:4px 0"><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e63946;margin-right:8px"></span><span style="color:#ddd;font-size:12px">Opportunity cities (size = score)</span></div>
    </div>"""))

    st_folium(m2, width="100%", height=550, returned_objects=[])


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
