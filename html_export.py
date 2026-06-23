"""
html_export.py
===============
Genera un reporte HTML autocontenido (KPIs + gráfico interactivo + tabla
diaria + resumen mensual) en una sola página, pensado para compartir por
correo o chat sin necesidad de abrir la aplicación Streamlit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

_MESES_ES_FULL = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# "Promedio Mejor Versión" excluido: es igual a PB Diario
_SKIP_SUMMARY_KEYS = {"Promedio Mejor Versión"}

_NOTES = {
    "Promedio Predespacho": "Promedio archivos IMAR (Costo Marginal / 1000)",
    "Promedio TX1":         "Primera liquidación provisional (TRSD .tx1 — PBNA)",
    "Promedio TX2":         "Segunda liquidación provisional (TRSD .tx2 — PBNA)",
    "Promedio TXR":         "Reliquidación (TRSD .txr) — disponible día 5 mes siguiente",
    "Promedio TXF":         "Liquidación final (TRSD .txf) — disponible día 10 mes siguiente",
    "Promedio PB Mes":      "Precio de Bolsa mensual",
}

_KPI_ICONS = {
    "Promedio PB Mes":      "⚡",
    "Promedio Predespacho": "📋",
    "Promedio TX1":         "1️⃣",
    "Promedio TX2":         "2️⃣",
    "Promedio TXR":         "🔄",
    "Promedio TXF":         "✅",
}

# (color, dash) — paleta verde, sin azules
_SERIES_STYLE = {
    "TXF":         ("#B7860B", "solid"),
    "TXR":         ("#2E7D32", "solid"),
    "TX2":         ("#388E3C", "solid"),
    "TX1":         ("#D35400", "dashdot"),
    "Predespacho": ("#6D4C41", "dot"),
    "PB_Diario":   ("#00695C", "solid"),
    "PB_PromMes":  ("#757575", "dash"),
}
_SERIES_LABELS = {
    "TXF": "TXF", "TXR": "TXR", "TX2": "TX2", "TX1": "TX1",
    "Predespacho": "Predespacho",
    "PB_Diario": "PB Diario", "PB_PromMes": "Prom. Mensual",
}

_NUMERIC_SRC = {
    "Predespacho", "TX1", "TX2", "TXR", "TXF",
    "Diferencia_Version", "PB_Diario", "PB_PromMes",
}

# Columnas de precio con gradiente verde→amarillo→rojo
_GRAD_PRICE_SRC = {"Predespacho", "TX1", "TX2", "TXR", "TXF", "PB_Diario", "PB_PromMes"}
_GRAD_LOW  = (0x63, 0xBE, 0x7B)   # #63BE7B → precio bajo
_GRAD_MID  = (0xFF, 0xEB, 0x84)   # #FFEB84 → precio medio
_GRAD_HIGH = (0xF8, 0x69, 0x6B)   # #F8696B → precio alto

# Columna fuente de precio → columna booleana que indica techado por PEP
_CAPPED_FLAG_SRC = {
    "TX1":       "TX1_Techado",
    "TX2":       "TX2_Techado",
    "TXR":       "TXR_Techado",
    "TXF":       "TXF_Techado",
    "PB_Diario": "Mejor_Version_Techado",
}


def _gradient_style(value: float, mn: float, mx: float) -> str:
    """Interpola #63BE7B→#FFEB84→#F8696B según la posición del valor en [mn, mx]."""
    if mn == mx:
        rgb = _GRAD_MID
    else:
        ratio = (value - mn) / (mx - mn)
        if ratio <= 0.5:
            t = ratio * 2
            rgb = tuple(int(_GRAD_LOW[i] + (_GRAD_MID[i] - _GRAD_LOW[i]) * t) for i in range(3))
        else:
            t = (ratio - 0.5) * 2
            rgb = tuple(int(_GRAD_MID[i] + (_GRAD_HIGH[i] - _GRAD_MID[i]) * t) for i in range(3))
    r, g, b = rgb
    return f"color:#000000;background-color:rgb({r},{g},{b});font-weight:600;"


# ──────────────────────────────────────────────────────────────────
#  GRÁFICO INTERACTIVO
# ──────────────────────────────────────────────────────────────────

def _build_chart_html(df: pd.DataFrame, year: int, month: int) -> str:
    fecha = df["Fecha"].astype(str)
    fig = go.Figure()

    for col in ["TXF", "TXR", "TX2", "TX1", "Predespacho", "PB_Diario", "PB_PromMes"]:
        if col not in df.columns:
            continue
        color, dash = _SERIES_STYLE[col]
        label = _SERIES_LABELS[col]
        fig.add_trace(go.Scatter(
            x=fecha,
            y=df[col],
            name=label,
            mode="lines+markers",
            line=dict(color=color, dash=dash, width=2),
            marker=dict(size=4, color=color),
            connectgaps=False,
            hovertemplate=f"<b>{label}</b><br>Fecha: %{{x}}<br>Precio: %{{y:,.2f}} $/kWh<extra></extra>",
        ))

    fig.update_layout(
        template="plotly_white",
        title=dict(text=f"Precio de Bolsa — {_MESES_ES_FULL[month]} {year}", x=0.01, font=dict(size=16)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(title="Fecha", tickangle=-60, tickmode="array", tickvals=fecha.tolist()),
        yaxis=dict(title="Precio ($/kWh)", tickformat=",.2f"),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=70, b=90),
        height=520,
    )

    return pio.to_html(
        fig, include_plotlyjs="cdn", full_html=False, config={"displaylogo": False}
    )


# ──────────────────────────────────────────────────────────────────
#  TABLA DIARIA
# ──────────────────────────────────────────────────────────────────

def _build_daily_table_html(df: pd.DataFrame) -> tuple[str, bool]:
    has_txr = "TXR" in df.columns and df["TXR"].notna().any()
    has_txf = "TXF" in df.columns and df["TXF"].notna().any()

    cols = [("Fecha", "Fecha"), ("Predespacho", "Predespacho"), ("TX1", "TX1"), ("TX2", "TX2")]
    if has_txr:
        cols.append(("TXR", "TXR"))
    if has_txf:
        cols.append(("TXF", "TXF"))
    cols += [
        ("PB Diario",    "PB_Diario"),
        ("Versión",      "Mejor_Version_Nombre"),
        ("Δ Versión",    "Diferencia_Version"),
        ("PB PromMes",   "PB_PromMes"),
    ]

    grad_ranges: dict[str, tuple[float, float]] = {}
    for src in _GRAD_PRICE_SRC:
        if src in df.columns:
            valid = df[src].dropna()
            if not valid.empty:
                grad_ranges[src] = (float(valid.min()), float(valid.max()))

    rows_html = []
    has_capped = False
    for i, (_, row) in enumerate(df.iterrows()):
        cells = []
        for _, src in cols:
            value = row.get(src)
            if src == "Fecha":
                try:
                    cells.append(f"<td class='c'>{pd.to_datetime(str(value)).strftime('%d-%b')}</td>")
                except Exception:
                    cells.append(f"<td class='c'>{value}</td>")
            elif src in _NUMERIC_SRC:
                if value is None or (isinstance(value, float) and np.isnan(value)):
                    cells.append("<td class='n nan'>—</td>")
                else:
                    fval = float(value)
                    style = ""
                    if src in grad_ranges:
                        mn, mx = grad_ranges[src]
                        style = f" style='{_gradient_style(fval, mn, mx)}'"
                    marker = ""
                    flag_col = _CAPPED_FLAG_SRC.get(src)
                    if flag_col:
                        flag_val = row.get(flag_col)
                        if pd.notna(flag_val) and bool(flag_val):
                            marker = " 🔻"
                            has_capped = True
                    cells.append(f"<td class='n'{style}>{fval:,.2f}{marker}</td>")
            else:
                cells.append(f"<td>{value if pd.notna(value) else ''}</td>")
        cls = " class='alt'" if i % 2 else ""
        rows_html.append(f"<tr{cls}>" + "".join(cells) + "</tr>")

    headers_html = "".join(f"<th>{h}</th>" for h, _ in cols)
    table = (
        "<table class='daily-table'><thead><tr>" + headers_html + "</tr></thead>"
        "<tbody>" + "".join(rows_html) + "</tbody></table>"
    )
    return table, has_capped


# ──────────────────────────────────────────────────────────────────
#  KPIs Y RESUMEN MENSUAL
# ──────────────────────────────────────────────────────────────────

def _build_kpi_html(summary: dict) -> str:
    cards = []
    for key, val in summary.items():
        if key in _SKIP_SUMMARY_KEYS:
            continue
        display = f"{val:,.2f}" if val is not None else "—"
        icon = _KPI_ICONS.get(key, "📊")
        cards.append(
            f"<div class='kpi'>"
            f"<div class='kpi-label'>{icon} {key}</div>"
            f"<div class='kpi-value'>{display}</div>"
            f"<div class='kpi-unit'>$/kWh</div>"
            f"</div>"
        )
    return "<div class='kpi-grid'>" + "".join(cards) + "</div>"


def _build_summary_html(summary: dict) -> str:
    rows = []
    for key, val in summary.items():
        if key in _SKIP_SUMMARY_KEYS:
            continue
        display = f"{val:,.2f}" if val is not None else "—"
        note = _NOTES.get(key, "")
        rows.append(
            f"<tr><td class='label'>{key}</td><td class='n'>{display}</td><td class='note'>{note}</td></tr>"
        )
    return (
        "<table class='summary-table'><thead><tr><th>Métrica</th><th>Valor ($/kWh)</th><th>Notas</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


# ──────────────────────────────────────────────────────────────────
#  FUNCIÓN PÚBLICA PRINCIPAL
# ──────────────────────────────────────────────────────────────────

def generate_html(df: pd.DataFrame, summary: dict, year: int, month: int) -> bytes:
    """
    Genera un reporte HTML de una sola página (KPIs, gráfico interactivo,
    tabla diaria y resumen mensual) y retorna los bytes para descargar
    desde Streamlit (st.download_button).
    """
    month_name = _MESES_ES_FULL[month]
    daily_table_html, has_capped = _build_daily_table_html(df)
    pep_note_html = (
        "<div class='note-pep'>🔻 Precio techado por el PEP (Precio de Escasez "
        "Ponderado) en al menos una hora del día.</div>"
        if has_capped else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Precio de Bolsa XM — {month_name} {year}</title>
<style>
  :root {{
    --bg: #F1F8F2; --card: #FFFFFF; --border: #C8E0CC;
    --text: #1B2733; --muted: #4A6B52; --accent: #1B5E20;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px; background: var(--bg); color: var(--text);
    font-family: 'Segoe UI', Calibri, Arial, sans-serif;
  }}
  .wrap {{ max-width: 1200px; margin: 0 auto; }}
  header {{
    display: flex; align-items: center; gap: 14px;
    border-bottom: 2px solid var(--border); padding-bottom: 16px; margin-bottom: 24px;
  }}
  header .icon {{ font-size: 2rem; }}
  header h1 {{ margin: 0; font-size: 1.4rem; color: var(--accent); }}
  header .sub {{ color: var(--muted); font-size: 0.85rem; margin-top: 4px; }}
  h2 {{ font-size: 1.05rem; color: var(--muted); margin: 30px 0 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; box-shadow: 0 2px 8px rgba(15,42,20,0.06); }}

  .kpi-grid {{ display: flex; flex-wrap: wrap; gap: 14px; }}
  .kpi {{ flex: 1; min-width: 150px; background: var(--card); border: 1px solid var(--border);
          border-radius: 10px; padding: 14px 16px; text-align: center; }}
  .kpi-label {{ font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 1.4rem; font-weight: 700; color: var(--accent); }}
  .kpi-unit  {{ font-size: 0.7rem; color: var(--muted); margin-top: 2px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: var(--accent); color: #fff; padding: 8px 10px; text-align: center; position: sticky; top: 0; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); }}
  td.n {{ font-variant-numeric: tabular-nums; }}
  td.c {{ text-align: center; }}
  .daily-table td {{ text-align: center; }}
  td.nan {{ color: #A8C4AA; }}
  tr.alt {{ background: #E8F5E9; }}
  .summary-table td.label {{ font-weight: 600; }}
  .summary-table td.note  {{ color: var(--muted); font-size: 0.78rem; }}
  .table-scroll {{ max-height: 560px; overflow: auto; border: 1px solid var(--border); border-radius: 8px; }}
  .note-pep {{ margin-top: 8px; color: var(--muted); font-size: 0.78rem; }}

  footer {{ margin-top: 36px; color: var(--muted); font-size: 0.75rem; text-align: center; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="icon">⚡</div>
    <div>
      <h1>Precio de Bolsa de Energía — XM Colombia</h1>
      <div class="sub">Período: {month_name} {year} · Versiones Predespacho · TX1 · TX2 · TXR · TXF</div>
    </div>
  </header>

  <h2>📊 Indicadores del mes</h2>
  {_build_kpi_html(summary)}

  <h2>📈 Evolución de precios</h2>
  <div class="card">{_build_chart_html(df, year, month)}</div>

  <h2>📋 Datos diarios</h2>
  <div class="table-scroll">{daily_table_html}</div>
  {pep_note_html}

  <h2>🧾 Resumen mensual</h2>
  <div class="card">{_build_summary_html(summary)}</div>

  <footer>Generado con XM Precios — Sebastián M · ATCE</footer>
</div>
</body>
</html>"""

    return html.encode("utf-8")
