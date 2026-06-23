"""
dashboard.py
============
Componentes visuales del dashboard Streamlit:
  · KPI cards
  · Tabla principal con formato condicional
  · Gráfico interactivo Plotly
  · CSS personalizado — se adapta al tema activo de Streamlit:
      oscuro  → estética neón (verde + naranja), sin cambios
      claro   → paleta corporativa (azul/verde profundo + naranja quemado)
"""

from __future__ import annotations

import calendar
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from typing import Optional


# ──────────────────────────────────────────────────────────────────
#  DETECCIÓN DE TEMA Y PALETAS
# ──────────────────────────────────────────────────────────────────

def _theme_is_dark() -> bool:
    """Tema activo en Settings → Theme. Por defecto oscuro si no se puede determinar."""
    try:
        return st.context.theme.type != "light"
    except Exception:
        return True


_PALETTE = {
    True: dict(   # ── Oscuro (neón) — idéntico al diseño original ──
        black="#000000", black2="#080808", dark="#101010", dark2="#161616",
        green="#00FF41", green2="#39FF14", orange="#FF6600", amber="#FFB300", red="#FF3333",
        text="#C8FFC8", text_muted="#2E7D42",
        border="#0A2B0A", border_orange="#3B1800", card_bg="#070707", row_alt="#0B0B0B",
        lime="#76FF03", yellow="#FFD600",
        glow_green="0 0 8px rgba(0,255,65,0.5)",
        glow_orange="0 0 8px rgba(255,102,0,0.5)",
        glow_amber="0 0 8px rgba(255,179,0,0.5)",
        glow_lime="0 0 8px rgba(118,255,3,0.5)",
        glow_yellow="0 0 8px rgba(255,214,0,0.5)",
        glow_title="0 0 12px rgba(0,255,65,0.4)",
        card_shadow="0 0 16px rgba(0,255,65,0.12)",
        nan_color="#1A4A1A", flat_color="#00FF41",
        grad_low=(0, 255, 65), grad_mid=(255, 179, 0), grad_high=(255, 51, 51), grad_alpha=(0.08, 0.10),
        sens_bg="rgba(255,102,0,0.12)", sens_text="#FF8C00", sens_border="rgba(255,102,0,0.3)",
        sens_divider="#1A0800",
        sens_glow="0 0 24px rgba(255,102,0,0.08)",
        sens_progress_glow="0 0 6px rgba(255,102,0,0.5)",
        sens_headline_glow="0 0 16px rgba(255,102,0,0.55)",
        delta_shadow="0 0 5px rgba(0,0,0,0.4)",
        good="#00FF41", bad="#FF3333",
        btn_text="#000000",
        chart_paper="#000000", chart_plot="#070707", chart_font="#00FF41", chart_title="#00FF41",
        chart_grid="#0A2B0A", chart_axis_title="#2E7D42", chart_tick="#2E7D42",
        chart_legend_bg="rgba(0,0,0,0.85)", chart_legend_border="#0A2B0A", chart_legend_text="#C8FFC8",
        chart_hover_bg="#080808", chart_hover_border="#FF6600", chart_hover_text="#C8FFC8",
        chart_spike="#FF6600",
        chart_vrect="rgba(255,102,0,0.05)", chart_vline="rgba(255,102,0,0.45)", chart_vline_text="#FF6600",
        welcome_shadow="0 0 40px rgba(0,255,65,0.06)",
        welcome_icon_glow="0 0 20px rgba(0,255,65,0.6)",
        brand_title="#00FF41", brand_credit="#9EFFB0", glow_brand="0 0 8px rgba(0,255,65,0.5)",
        series=dict(
            TXF=("#FFD600", "solid", 2.5),
            TXR=("#76FF03", "solid", 2.5),
            TX2=("#00FF41", "solid", 2.0),
            TX1=("#FF6600", "dashdot", 2.0),
            Predespacho=("#FFB300", "dot", 2.0),
            PB_Diario=("#FF4500", "solid", 1.5),
            PB_PromMes=("#FF8C00", "dash", 2.0),
        ),
    ),
    False: dict(  # ── Claro (corporativo) ──
        black="#F5F7FA", black2="#FFFFFF", dark="#FFFFFF", dark2="#EEF1F6",
        green="#1565C0", green2="#0B3D91", orange="#D35400", amber="#B7860B", red="#C0392B",
        text="#1B2733", text_muted="#5B6B82",
        border="#DCE2EA", border_orange="#E8D5C4", card_bg="#FFFFFF", row_alt="#F0F3F8",
        lime="#2E7D32", yellow="#8D6E00",
        glow_green="none", glow_orange="none", glow_amber="none", glow_lime="none", glow_yellow="none",
        glow_title="none",
        card_shadow="0 4px 14px rgba(15,23,42,0.08)",
        nan_color="#C7CDD6", flat_color="#1565C0",
        grad_low=(46, 125, 50), grad_mid=(183, 134, 11), grad_high=(192, 57, 43), grad_alpha=(0.10, 0.14),
        sens_bg="rgba(211,84,0,0.08)", sens_text="#D35400", sens_border="rgba(211,84,0,0.35)",
        sens_divider="#E3E7EE",
        sens_glow="0 4px 18px rgba(15,23,42,0.06)",
        sens_progress_glow="none",
        sens_headline_glow="none",
        delta_shadow="none",
        good="#2E7D32", bad="#C0392B",
        btn_text="#FFFFFF",
        chart_paper="#FFFFFF", chart_plot="#FFFFFF", chart_font="#1B2733", chart_title="#0B3D91",
        chart_grid="#E7EAF0", chart_axis_title="#5B6B82", chart_tick="#5B6B82",
        chart_legend_bg="rgba(255,255,255,0.92)", chart_legend_border="#DCE2EA", chart_legend_text="#1B2733",
        chart_hover_bg="#FFFFFF", chart_hover_border="#D35400", chart_hover_text="#1B2733",
        chart_spike="#D35400",
        chart_vrect="rgba(211,84,0,0.06)", chart_vline="rgba(211,84,0,0.55)", chart_vline_text="#D35400",
        welcome_shadow="0 10px 30px rgba(15,23,42,0.10)",
        welcome_icon_glow="none",
        brand_title="#1B5E20", brand_credit="#2E7D32", glow_brand="none",
        series=dict(
            TXF=("#B7860B", "solid", 2.5),
            TXR=("#2E7D32", "solid", 2.5),
            TX2=("#1565C0", "solid", 2.0),
            TX1=("#D35400", "dashdot", 2.0),
            Predespacho=("#6D4C41", "dot", 2.0),
            PB_Diario=("#00796B", "solid", 1.5),
            PB_PromMes=("#757575", "dash", 2.0),
        ),
    ),
}


def _p() -> dict:
    return _PALETTE[_theme_is_dark()]


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: inyectar CSS
# ──────────────────────────────────────────────────────────────────

def inject_css() -> None:
    p = _p()
    st.markdown(
        f"""
        <style>
        :root {{
          --black:         {p['black']};
          --black2:        {p['black2']};
          --dark:          {p['dark']};
          --dark2:         {p['dark2']};
          --neon-green:    {p['green']};
          --neon-green2:   {p['green2']};
          --neon-orange:   {p['orange']};
          --amber:         {p['amber']};
          --red:           {p['red']};
          --text:          {p['text']};
          --text-muted:    {p['text_muted']};
          --border:        {p['border']};
          --border-orange: {p['border_orange']};
          --card-bg:       {p['card_bg']};
          --row-alt:       {p['row_alt']};
        }}

        html, body, [class*="css"] {{
          font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
          background-color: var(--black) !important;
          color: var(--text) !important;
        }}

        section[data-testid="stSidebar"] {{
          background-color: var(--black2) !important;
          border-right: 1px solid var(--border);
        }}
        section[data-testid="stSidebar"] .stSelectbox label,
        section[data-testid="stSidebar"] .stTextInput label,
        section[data-testid="stSidebar"] .stNumberInput label,
        section[data-testid="stSidebar"] p {{
          color: var(--text-muted) !important;
          font-size: 0.82rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }}

        h1 {{ color: var(--neon-green) !important; font-weight: 700; letter-spacing: -0.02em; }}
        h2, h3 {{ color: var(--text-muted) !important; font-weight: 600; }}

        hr {{ border-color: var(--border) !important; }}

        .kpi-card {{
          background: var(--card-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 18px 20px 14px;
          text-align: center;
          transition: border-color 0.2s, box-shadow 0.2s;
        }}
        .kpi-card:hover {{
          border-color: {p['green']};
          box-shadow: {p['card_shadow']};
        }}
        .kpi-label {{
          font-size: 0.70rem;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 6px;
        }}
        .kpi-value {{
          font-size: 1.65rem;
          font-weight: 700;
          letter-spacing: -0.02em;
        }}
        .kpi-green  {{ color: {p['green']};  text-shadow: {p['glow_green']}; }}
        .kpi-orange {{ color: {p['orange']}; text-shadow: {p['glow_orange']}; }}
        .kpi-amber  {{ color: {p['amber']};  text-shadow: {p['glow_amber']}; }}
        .kpi-lime   {{ color: {p['lime']};   text-shadow: {p['glow_lime']}; }}
        .kpi-yellow {{ color: {p['yellow']}; text-shadow: {p['glow_yellow']}; }}
        .kpi-sub {{
          font-size: 0.70rem;
          color: var(--text-muted);
          margin-top: 4px;
        }}

        .stDataFrame thead th {{
          background: var(--black2) !important;
          color: var(--text-muted) !important;
          font-size: 0.74rem !important;
          text-transform: uppercase !important;
          letter-spacing: 0.06em !important;
        }}
        .stDataFrame tbody tr:nth-child(even) {{ background: var(--row-alt) !important; }}

        div.stButton > button {{
          background: {p['orange']};
          color: {p['btn_text']};
          border: none;
          border-radius: 6px;
          font-weight: 700;
          letter-spacing: 0.04em;
          transition: background 0.15s, box-shadow 0.15s;
        }}
        div.stButton > button:hover {{
          background: {p['amber']};
          box-shadow: {p['card_shadow']};
        }}

        div.stDownloadButton > button {{
          background: {p['green']} !important;
          color: {p['btn_text']} !important;
          border: none;
          border-radius: 6px;
          font-weight: 700;
        }}
        div.stDownloadButton > button:hover {{
          box-shadow: {p['card_shadow']};
        }}

        .stAlert {{ background: var(--card-bg) !important; border-color: var(--border) !important; }}

        div[data-testid="metric-container"] {{
          background: var(--card-bg);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 14px 16px;
        }}
        div[data-testid="metric-container"] label {{ color: var(--text-muted) !important; }}
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
          color: {p['green']} !important;
          font-weight: 700;
          text-shadow: {p['glow_green']};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: KPI Cards
# ──────────────────────────────────────────────────────────────────

# Clase de color alternada por KPI (el color real lo resuelve el CSS según el tema)
_KPI_COLOR_CLASS = {
    "Promedio PB Mes":      "kpi-orange",
    "Promedio Predespacho": "kpi-green",
    "Promedio TX1":         "kpi-orange",
    "Promedio TX2":         "kpi-green",
    "Promedio TXR":         "kpi-lime",
    "Promedio TXF":         "kpi-yellow",
}

_SKIP_KPI_KEYS = {"Promedio Mejor Versión"}

def render_kpis(summary: dict) -> None:
    """Muestra los KPIs del mes en cards horizontales."""
    filtered = {k: v for k, v in summary.items() if k not in _SKIP_KPI_KEYS}
    cols = st.columns(len(filtered))
    icons = {
        "Promedio PB Mes":      ("⚡", "$/kWh"),
        "Promedio Predespacho": ("📋", "$/kWh"),
        "Promedio TX1":         ("1️⃣", "$/kWh"),
        "Promedio TX2":         ("2️⃣", "$/kWh"),
        "Promedio TXR":         ("🔄", "$/kWh"),
        "Promedio TXF":         ("✅", "$/kWh"),
    }

    for col, (key, val) in zip(cols, filtered.items()):
        icon, unit = icons.get(key, ("📊", "$/kWh"))
        display = f"{val:,.2f}" if val is not None else "—"
        color_cls = _KPI_COLOR_CLASS.get(key, "kpi-green")
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                  <div class="kpi-label">{icon} {key}</div>
                  <div class="kpi-value {color_cls}">{display}</div>
                  <div class="kpi-sub">{unit}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: Tabla principal
# ──────────────────────────────────────────────────────────────────

# Columna fuente de precio → columna booleana que indica techado por PEP
_CAPPED_FLAG_SRC = {
    "TX1":       "TX1_Techado",
    "TX2":       "TX2_Techado",
    "TXR":       "TXR_Techado",
    "TXF":       "TXF_Techado",
    "PB_Diario": "Mejor_Version_Techado",
}


def render_table(df: pd.DataFrame) -> None:
    """
    Muestra la tabla con gradiente de color por magnitud de precio
    (bajo → medio → alto), adaptado al tema claro/oscuro activo.
    Filas proyectadas (Es_Sensibilidad=True) se resaltan en naranja.
    """
    p = _p()

    # Índices de filas proyectadas (antes de cualquier transformación)
    sens_indices: set = set()
    if "Es_Sensibilidad" in df.columns:
        sens_indices = set(df.index[df["Es_Sensibilidad"] == True].tolist())

    numeric_cols = [
        "Predespacho", "TX1", "TX2", "TXR", "TXF",
        "Diferencia_Version",
        "Predespacho_PromMes", "TX1_PromMes", "TX2_PromMes", "TXR_PromMes", "TXF_PromMes",
        "PB_Diario", "PB_PromMes",
    ]

    display_cols = {
        "Fecha":               "Fecha",
        "Predespacho":         "Predespacho",
        "TX1":                 "TX1",
        "TX2":                 "TX2",
        "TXR":                 "TXR",
        "TXF":                 "TXF",
        "Diferencia_Version":  "Δ Versión",
        "Predespacho_PromMes": "Pred PromMes",
        "TX1_PromMes":         "TX1 PromMes",
        "TX2_PromMes":         "TX2 PromMes",
        "TXR_PromMes":         "TXR PromMes",
        "TXF_PromMes":         "TXF PromMes",
        "PB_Diario":           "PB Diario",
        "Mejor_Version_Nombre":"Versión",
        "PB_PromMes":          "PB PromMes",
    }

    # Columna de sensibilidad cuando hay filas proyectadas
    has_sens_col = "Sensibilidad" in df.columns and df["Sensibilidad"].notna().any()
    if has_sens_col:
        display_cols["Sensibilidad"] = "Sens. ⚡"

    available = [c for c in display_cols if c in df.columns]
    disp = df[available].copy()
    disp = disp.rename(columns={k: v for k, v in display_cols.items() if k in available})

    if "Fecha" in disp.columns:
        disp["Fecha"] = disp["Fecha"].astype(str)

    num_disp = [display_cols[c] for c in numeric_cols if c in available]

    def color_gradient(series: pd.Series):
        """Interpola entre los tres colores de la paleta activa según la magnitud del valor."""
        low, mid, high = p["grad_low"], p["grad_mid"], p["grad_high"]
        alpha_base, alpha_scale = p["grad_alpha"]
        valid = series.dropna()
        if valid.empty:
            return [""] * len(series)
        mn, mx = valid.min(), valid.max()
        styles = []
        for v in series:
            if pd.isna(v):
                styles.append(f"color: {p['nan_color']}")
                continue
            if mn == mx:
                styles.append(f"color: {p['flat_color']}; font-weight: 600")
                continue
            ratio = (v - mn) / (mx - mn)
            if ratio <= 0.5:
                t = ratio * 2
                r = int(low[0] + (mid[0] - low[0]) * t)
                g = int(low[1] + (mid[1] - low[1]) * t)
                b = int(low[2] + (mid[2] - low[2]) * t)
            else:
                t = (ratio - 0.5) * 2
                r = int(mid[0] + (high[0] - mid[0]) * t)
                g = int(mid[1] + (high[1] - mid[1]) * t)
                b = int(mid[2] + (high[2] - mid[2]) * t)
            alpha = alpha_base + alpha_scale * ratio
            styles.append(
                f"color: rgb({r},{g},{b}); "
                f"background-color: rgba({r},{g},{b},{alpha:.2f}); "
                f"font-weight: 600"
            )
        return styles

    # Columnas que deben formatearse como número (incluye Sensibilidad si aplica)
    all_num_fmt = num_disp + (["Sens. ⚡"] if has_sens_col and "Sens. ⚡" in disp.columns else [])
    styled = disp.style.format(
        {c: "{:,.2f}" for c in all_num_fmt if c in disp.columns},
        na_rep="—",
    )

    # Gradiente solo en columnas de precio real (no en Sensibilidad)
    for col in num_disp:
        if col in disp.columns:
            styled = styled.apply(color_gradient, subset=[col])

    # Resaltar filas proyectadas
    if sens_indices:
        def highlight_sens_row(row: pd.Series) -> list:
            if row.name in sens_indices:
                return [
                    f"background-color:{p['sens_bg']};"
                    f"color:{p['sens_text']};font-weight:600;"
                    f"border-top:1px solid {p['sens_border']};"
                ] * len(row)
            return [""] * len(row)
        styled = styled.apply(highlight_sens_row, axis=1)

    # Marcar celdas techadas por el PEP con 🔻 (sobrescribe el formato solo en esas celdas)
    has_capped = False
    for src, flag_col in _CAPPED_FLAG_SRC.items():
        label = display_cols.get(src)
        if src not in available or label not in disp.columns or flag_col not in df.columns:
            continue
        flags = df[flag_col].fillna(False).astype(bool)
        capped_idx = [i for i in df.index[flags] if i in disp.index]
        if capped_idx:
            has_capped = True
            styled = styled.format("{:,.2f} 🔻", subset=pd.IndexSlice[capped_idx, label], na_rep="—")

    st.dataframe(styled, use_container_width=True, height=500)
    if has_capped:
        st.caption("🔻 Precio techado por el PEP (Precio de Escasez Ponderado) en al menos una hora del día.")


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: Gráfico interactivo Plotly
# ──────────────────────────────────────────────────────────────────

def render_chart(
    df: pd.DataFrame,
    show_predespacho: bool = True,
    show_tx1: bool = True,
    show_tx2: bool = True,
    show_txr: bool = True,
    show_txf: bool = True,
    show_pb: bool = True,
    show_prom: bool = True,
    show_sensitivity: bool = False,
) -> None:
    """Gráfico de serie temporal interactivo — paleta adaptada al tema claro/oscuro activo."""
    p = _p()
    sc = p["series"]
    fecha = df["Fecha"].astype(str)

    # Separar datos reales de proyecciones de sensibilidad
    has_sens = show_sensitivity and "Es_Sensibilidad" in df.columns
    if has_sens:
        sens_mask = df["Es_Sensibilidad"] == True
        real_mask = ~sens_mask
    else:
        real_mask = pd.Series([True] * len(df), index=df.index)
        sens_mask = ~real_mask
    fecha_real = df.loc[real_mask, "Fecha"].astype(str)

    fig = go.Figure()

    # ── Series principales ─────────────────────────────────────────
    # Calidad ascendente: Predespacho < TX1 < TX2 < TXR < TXF
    series_config = [
        ("TXF",         "TXF",         *sc["TXF"],         show_txf),
        ("TXR",         "TXR",         *sc["TXR"],         show_txr),
        ("TX2",         "TX2",         *sc["TX2"],         show_tx2),
        ("TX1",         "TX1",         *sc["TX1"],         show_tx1),
        ("Predespacho", "Predespacho", *sc["Predespacho"], show_predespacho),
        ("PB_Diario",   "PB Diario",   *sc["PB_Diario"],   show_pb),
        ("PB_PromMes",  "Prom Mensual",*sc["PB_PromMes"],  show_prom),
    ]

    for col, name, color, dash, width, visible in series_config:
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=fecha_real,
            y=df.loc[real_mask, col],
            name=name,
            mode="lines+markers",
            line=dict(color=color, dash=dash, width=width),
            marker=dict(size=4, color=color),
            visible=True if visible else "legendonly",
            hovertemplate=(
                f"<b style='color:{color}'>{name}</b><br>"
                f"Fecha: %{{x}}<br>"
                f"Precio: %{{y:,.2f}} $/kWh<extra></extra>"
            ),
            connectgaps=False,
        ))

    # ── Sensibilidad — trazas proyectadas ────────────────────────
    if has_sens and sens_mask.any():
        last_real_idx = df.index[real_mask][-1] if real_mask.any() else None

        # (col_en_df, nombre_traza, color, flag_visible)
        proj_series = [
            ("PB_Diario",  "PB Diario [sens]", sc["PB_Diario"][0],  show_pb),
            ("PB_PromMes", "Prom Mes [sens]",  sc["PB_PromMes"][0], show_prom),
        ]

        for col, name, color, visible in proj_series:
            if col not in df.columns:
                continue

            # Conectar con el último punto real para continuidad visual
            if last_real_idx is not None:
                connector_x = [str(df.loc[last_real_idx, "Fecha"])]
                connector_v = df.loc[last_real_idx, col]
                connector_y = [float(connector_v) if pd.notna(connector_v) else None]
            else:
                connector_x, connector_y = [], []

            proj_x = connector_x + df.loc[sens_mask, "Fecha"].astype(str).tolist()
            proj_y = connector_y + df.loc[sens_mask, col].tolist()

            if not any(v is not None and not (isinstance(v, float) and np.isnan(v))
                       for v in proj_y):
                continue

            fig.add_trace(go.Scatter(
                x=proj_x,
                y=proj_y,
                name=name,
                mode="lines+markers",
                line=dict(color=color, dash="dot", width=1.8),
                marker=dict(size=5, symbol="circle-open", color=color,
                            line=dict(width=1.5, color=color)),
                visible=True if visible else "legendonly",
                hovertemplate=(
                    f"<b style='color:{color}'>{name}</b><br>"
                    f"Fecha: %{{x}}<br>"
                    f"Precio: %{{y:,.2f}} $/kWh<extra></extra>"
                ),
                connectgaps=False,
            ))

        # Zona sombreada para el período proyectado
        sens_fechas = df.loc[sens_mask, "Fecha"].astype(str)
        fig.add_vrect(
            x0=str(sens_fechas.iloc[0]),
            x1=str(sens_fechas.iloc[-1]),
            fillcolor=p["chart_vrect"],
            layer="below",
            line_width=0,
        )
        if last_real_idx is not None:
            fig.add_vline(
                x=str(df.loc[last_real_idx, "Fecha"]),
                line_width=1,
                line_dash="dash",
                line_color=p["chart_vline"],
                annotation_text="real ↔ sens.",
                annotation_position="top right",
                annotation_font_color=p["chart_vline_text"],
                annotation_font_size=10,
            )

    # ── Layout ─────────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark" if _theme_is_dark() else "plotly_white",
        paper_bgcolor=p["chart_paper"],
        plot_bgcolor=p["chart_plot"],
        font=dict(family="JetBrains Mono, Consolas, monospace", color=p["chart_font"], size=12),
        title=dict(
            text="Precio de Bolsa de Energía — Versiones y Evolución Mensual",
            font=dict(size=14, color=p["chart_title"]),
            x=0.01,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="left",
            x=0,
            bgcolor=p["chart_legend_bg"],
            bordercolor=p["chart_legend_border"],
            borderwidth=1,
            font=dict(color=p["chart_legend_text"]),
        ),
        xaxis=dict(
            title="Fecha",
            title_font=dict(color=p["chart_axis_title"]),
            gridcolor=p["chart_grid"],
            linecolor=p["chart_grid"],
            tickfont=dict(color=p["chart_tick"], size=10),
            tickmode="array",
            tickvals=df["Fecha"].astype(str).tolist(),
            tickangle=-60,
            showspikes=True,
            spikecolor=p["chart_spike"],
            spikemode="across",
            spikethickness=1,
        ),
        yaxis=dict(
            title="Precio ($/kWh)",
            title_font=dict(color=p["chart_axis_title"]),
            gridcolor=p["chart_grid"],
            linecolor=p["chart_grid"],
            tickfont=dict(color=p["chart_tick"]),
            tickformat=",.2f",
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=p["chart_hover_bg"],
            bordercolor=p["chart_hover_border"],
            font=dict(color=p["chart_hover_text"], family="JetBrains Mono, monospace"),
        ),
        margin=dict(l=60, r=20, t=80, b=100),
    )

    config = {
        "toImageButtonOptions": {
            "format": "png",
            "filename": "precio_bolsa_xm",
            "height": 600,
            "width": 1200,
            "scale": 2,
        },
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
    }

    st.plotly_chart(fig, use_container_width=True, config=config)


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: Letrero de marca (sidebar)
# ──────────────────────────────────────────────────────────────────

def render_sidebar_brand() -> None:
    """Crédito + nombre de la app en el sidebar, adaptado al tema activo."""
    p = _p()
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:600;color:{p['brand_credit']};"
        "font-family:JetBrains Mono,Consolas,monospace;"
        "padding:0 0 2px;'>Sebastián M - ATCE</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='font-size:1.1rem;font-weight:700;color:{p['brand_title']};"
        f"text-shadow:{p['glow_brand']};"
        "font-family:JetBrains Mono,Consolas,monospace;"
        f"padding:8px 0 18px;border-bottom:1px solid {p['border']};'>⚡ XM Precios</div>",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: Banner de cabecera
# ──────────────────────────────────────────────────────────────────

def render_header(year: int, month: int) -> None:
    p = _p()
    month_name = calendar.month_name[month]
    st.markdown(
        f"""
        <div style="
            display:flex; align-items:center; gap:16px;
            padding: 10px 0 18px 0;
            border-bottom: 1px solid {p['border']};
            margin-bottom: 20px;
        ">
          <div style="font-size:2.2rem;">⚡</div>
          <div>
            <div style="
                font-size:1.5rem; font-weight:700;
                color:{p['green']}; letter-spacing:-0.02em;
                text-shadow: {p['glow_title']};
                font-family: JetBrains Mono, Consolas, monospace;
            ">
              Precio de Bolsa de Energía — XM Colombia
            </div>
            <div style="
                font-size:0.85rem; color:{p['text_muted']}; margin-top:4px;
                font-family: JetBrains Mono, Consolas, monospace;
            ">
              Versiones Predespacho · TX1 · TX2 · TXR · TXF &nbsp;|&nbsp;
              Período: <strong style="color:{p['orange']};
                               text-shadow: {p['glow_orange']};">
                {month_name} {year}
              </strong>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: Pantalla de bienvenida
# ──────────────────────────────────────────────────────────────────

def render_welcome() -> None:
    """Pantalla mostrada antes de cargar datos, adaptada al tema claro/oscuro activo."""
    p = _p()
    st.markdown(
        f"""
        <div style="
            max-width: 640px; margin: 60px auto; text-align: center;
            padding: 48px 40px; background: {p['card_bg']};
            border: 1px solid {p['border']}; border-radius: 12px;
            box-shadow: {p['welcome_shadow']};
            font-family: JetBrains Mono, Consolas, monospace;
        ">
          <div style="font-size:3rem;margin-bottom:16px;
                      text-shadow:{p['welcome_icon_glow']};">⚡</div>
          <h2 style="
              color:{p['green']}; font-weight:700; margin-bottom:10px;
              text-shadow: {p['glow_title']};
          ">
            Precio de Bolsa de Energía — XM
          </h2>
          <p style="color:{p['text_muted']};font-size:0.93rem;line-height:1.7;">
            Consulta, procesa y exporta el Precio de Bolsa con todas sus versiones
            (<strong style="color:{p['orange']}">Predespacho · TX1 · TX2· TXR· TXF</strong>)
            directamente desde la plataforma de XM Colombia.
          </p>
          <div style="
              margin-top:28px; padding:16px 20px; background:{p['black']};
              border:1px solid {p['border']}; border-radius:8px;
              text-align:left; font-size:0.83rem; color:{p['text_muted']};
          ">
            <strong style="color:{p['orange']};
                           text-shadow:{p['glow_orange']};">
              &gt; Cómo empezar:
            </strong><br><br>
            1. En el panel izquierdo, selecciona el modo
               <strong style="color:{p['green']}">Demo</strong> o
               ingresa tus credenciales FTPS.<br>
            2. Selecciona el
               <strong style="color:{p['green']}">año y mes</strong> a consultar.<br>
            3. Presiona
               <strong style="color:{p['orange']}">▶ Cargar datos</strong>.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: Análisis de Sensibilidad
# ──────────────────────────────────────────────────────────────────

def render_sensitivity(result: dict, sensitivity_price: float) -> None:
    """
    Muestra el card de sensibilidad cuando el mes está incompleto.
    No renderiza nada si remaining_days == 0.
    """
    remaining = result.get("remaining_days", 0)
    if remaining <= 0:
        return

    p = _p()
    days_with_data = result["days_with_data"]
    days_in_month  = result["days_in_month"]
    current_avg    = result["current_avg"]
    sens_avg       = result["sensitivity_avg"]

    pct_done = days_with_data / days_in_month * 100
    delta    = sens_avg - current_avg if (sens_avg is not None and current_avg is not None) else 0
    delta_sign  = "+" if delta >= 0 else ""
    delta_color = p["bad"] if delta > 0 else p["good"]

    st.markdown(
        f"""
        <div style="
            background:{p['card_bg']};
            border:1px solid {p['border_orange']};
            border-radius:10px;
            padding:22px 28px;
            margin:18px 0 6px;
            box-shadow:{p['sens_glow']};
            font-family:JetBrains Mono,Consolas,monospace;
        ">
          <div style="
              font-size:0.72rem; color:{p['orange']};
              text-transform:uppercase; letter-spacing:0.12em;
              margin-bottom:16px;
              text-shadow:{p['glow_orange']};
          ">
            🎯 Análisis de Sensibilidad — días faltantes del mes
          </div>

          <div style="display:flex; gap:0; flex-wrap:wrap; align-items:stretch;">

            <!-- Avance del mes -->
            <div style="flex:1; min-width:140px; padding-right:28px; border-right:1px solid {p['sens_divider']};">
              <div style="font-size:0.68rem; color:{p['text_muted']}; text-transform:uppercase;
                          letter-spacing:0.07em; margin-bottom:6px;">Avance del mes</div>
              <div style="font-size:1.35rem; font-weight:700; color:{p['orange']};">
                {days_with_data} / {days_in_month} <span style="font-size:0.85rem;">días</span>
              </div>
              <div style="font-size:0.70rem; color:{p['text_muted']}; margin-top:3px;">
                {pct_done:.0f}% completado
              </div>
              <!-- barra de progreso -->
              <div style="
                  margin-top:10px; height:4px; border-radius:2px;
                  background:{p['sens_divider']}; overflow:hidden;
              ">
                <div style="
                    height:100%; border-radius:2px;
                    width:{pct_done:.1f}%;
                    background:linear-gradient(90deg,{p['orange']},{p['amber']});
                    box-shadow:{p['sens_progress_glow']};
                "></div>
              </div>
            </div>

            <!-- Días faltantes -->
            <div style="flex:1; min-width:140px; padding:0 28px; border-right:1px solid {p['sens_divider']};">
              <div style="font-size:0.68rem; color:{p['text_muted']}; text-transform:uppercase;
                          letter-spacing:0.07em; margin-bottom:6px;">Días faltantes</div>
              <div style="font-size:1.35rem; font-weight:700; color:{p['amber']};">
                {remaining} <span style="font-size:0.85rem;">días</span>
              </div>
              <div style="font-size:0.70rem; color:{p['text_muted']}; margin-top:3px;">
                al precio: <strong style="color:{p['amber']};">{sensitivity_price:,.2f} $/kWh</strong>
              </div>
            </div>

            <!-- Promedio actual -->
            <div style="flex:1; min-width:160px; padding:0 28px; border-right:1px solid {p['sens_divider']};">
              <div style="font-size:0.68rem; color:{p['text_muted']}; text-transform:uppercase;
                          letter-spacing:0.07em; margin-bottom:6px;">Promedio actual</div>
              <div style="font-size:1.35rem; font-weight:700; color:{p['text']};">
                {current_avg:,.2f} <span style="font-size:0.85rem;">$/kWh</span>
              </div>
              <div style="font-size:0.70rem; color:{p['text_muted']}; margin-top:3px;">
                con {days_with_data} días reales
              </div>
            </div>

            <!-- Promedio proyectado — protagonista -->
            <div style="flex:1.4; min-width:200px; padding-left:28px;">
              <div style="font-size:0.68rem; color:{p['orange']}; text-transform:uppercase;
                          letter-spacing:0.07em; margin-bottom:6px;
                          text-shadow:{p['glow_orange']};">Promedio proyectado</div>
              <div style="font-size:2.0rem; font-weight:700; color:{p['orange']};
                          text-shadow:{p['sens_headline_glow']}; line-height:1.1;">
                {sens_avg:,.2f}
                <span style="font-size:1.0rem; font-weight:400;">$/kWh</span>
              </div>
              <div style="font-size:0.80rem; color:{delta_color}; margin-top:6px;
                          text-shadow:{p['delta_shadow']}; font-weight:600;">
                {delta_sign}{delta:,.2f} $/kWh vs. promedio actual
              </div>
            </div>

          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN: Tabla de validación de archivos
# ──────────────────────────────────────────────────────────────────

def render_file_status(df: pd.DataFrame) -> None:
    """Muestra un resumen de disponibilidad de archivos por día."""
    with st.expander("📁 Estado de archivos descargados", expanded=False):
        status_df = pd.DataFrame({
            "Día": df["Fecha"].astype(str),
            "IMAR (Predespacho)": df["Predespacho"].apply(lambda x: "✅" if pd.notna(x) else "❌"),
            "TRSD TX1":           df["TX1"].apply(lambda x: "✅" if pd.notna(x) else "❌"),
            "TRSD TX2":           df["TX2"].apply(lambda x: "✅" if pd.notna(x) else "❌"),
        })

        total = len(df)
        imar_ok = df["Predespacho"].notna().sum()
        tx1_ok  = df["TX1"].notna().sum()
        tx2_ok  = df["TX2"].notna().sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("IMAR disponibles", f"{imar_ok}/{total}")
        c2.metric("TX1 disponibles",  f"{tx1_ok}/{total}")
        c3.metric("TX2 disponibles",  f"{tx2_ok}/{total}")

        st.dataframe(status_df, use_container_width=True, height=280)
