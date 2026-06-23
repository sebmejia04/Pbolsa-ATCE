"""
calculations.py
===============
Toda la lógica de cálculo de precios:
  · Mejor Versión Disponible
  · Diferencia de Versión
  · Promedios mensuales acumulados
  · Análisis de sensibilidad
"""

from __future__ import annotations

import calendar
import numpy as np
import pandas as pd
from typing import Tuple, Optional

# ------------------------------------------------------------------
# Constantes
# ------------------------------------------------------------------
VERSION_ORDER = ["Predespacho", "TX1", "TX2", "TXR", "TXF"]  # ascendente en calidad

# Columna de techado por PEP correspondiente a cada versión (Predespacho no aplica)
_TECHADO_COLS = {"TX1": "TX1_Techado", "TX2": "TX2_Techado", "TXR": "TXR_Techado", "TXF": "TXF_Techado"}


# ==================================================================
#  MEJOR VERSIÓN Y NOMBRE
# ==================================================================

def _best_version_for_row(row: pd.Series) -> Tuple[Optional[float], str]:
    """
    Determina la Mejor Versión Disponible para una fila:
      TXF  →  TXR  →  TX2  →  TX1  →  Predespacho
    Retorna (valor, nombre_versión).
    """
    for version in reversed(VERSION_ORDER):   # TXF, TXR, TX2, TX1, Predespacho
        val = row.get(version)
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            return float(val), version
    return np.nan, ""


def _is_valid(val) -> bool:
    """Verifica si un valor es numérico y no NaN."""
    if val is None:
        return False
    try:
        return not np.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _techado_for_row(row: pd.Series) -> bool:
    """Indica si la versión elegida como Mejor Versión tuvo techado por PEP ese día."""
    flag_col = _TECHADO_COLS.get(row.get("Mejor_Version_Nombre", ""))
    if not flag_col:
        return False
    val = row.get(flag_col)
    return bool(val) if pd.notna(val) else False


# ==================================================================
#  CÁLCULO PRINCIPAL
# ==================================================================

def calculate_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe el DataFrame crudo (Fecha, Predespacho, TX1, TX2) y devuelve
    el DataFrame enriquecido con todas las columnas calculadas.

    Columnas añadidas
    -----------------
    Mejor_Version         : valor de la mejor versión disponible
    Mejor_Version_Nombre  : nombre de la mejor versión ('TX2', 'TX1', 'Predespacho')
    Diferencia_Version    : Mejor_Version - Predespacho para ese día
    PB_Diario             : igual a Mejor_Version (alias para el dashboard)
    Predespacho_PromMes   : promedio acumulado mensual del Predespacho
    TX1_PromMes           : promedio acumulado mensual de TX1
    TX2_PromMes           : promedio acumulado mensual de TX2
    PB_PromMes            : promedio acumulado mensual del PB Diario
    MejorVersion_PromMes  : promedio acumulado mensual de Mejor Versión
    """
    df = df.copy()

    # Convertir a float (los None quedan como NaN); TXR/TXF son opcionales
    for col in ["Predespacho", "TX1", "TX2", "TXR", "TXF"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Mejor Versión ───────────────────────────────────────────────────
    results = df.apply(_best_version_for_row, axis=1)
    df["Mejor_Version"] = [r[0] for r in results]
    df["Mejor_Version_Nombre"] = [r[1] for r in results]
    df["Mejor_Version_Techado"] = df.apply(_techado_for_row, axis=1)

    # ── Diferencia de Versión (Mejor Versión vs. Predespacho) ───────────
    df["Diferencia_Version"] = np.where(
        df["Predespacho"].notna() & df["Mejor_Version"].notna(),
        df["Mejor_Version"] - df["Predespacho"],
        np.nan,
    )

    # ── PB Diario (alias de Mejor_Version) ─────────────────────────────
    df["PB_Diario"] = df["Mejor_Version"]

    # ── Promedios Mensuales Acumulados ──────────────────────────────────
    # expanding().mean() ignora NaN automáticamente, acumulando sólo días con dato.
    df["Predespacho_PromMes"]  = df["Predespacho"].expanding().mean()
    df["TX1_PromMes"]          = df["TX1"].expanding().mean()
    df["TX2_PromMes"]          = df["TX2"].expanding().mean()
    df["PB_PromMes"]           = df["PB_Diario"].expanding().mean()
    df["MejorVersion_PromMes"] = df["Mejor_Version"].expanding().mean()

    if "TXR" in df.columns:
        df["TXR_PromMes"] = df["TXR"].expanding().mean()
    if "TXF" in df.columns:
        df["TXF_PromMes"] = df["TXF"].expanding().mean()

    return df


# ==================================================================
#  RESUMEN MENSUAL (KPIs)
# ==================================================================

def calculate_monthly_summary(df: pd.DataFrame) -> dict:
    """
    Calcula los promedios mensuales globales para los KPIs del dashboard.
    Usa nanmean para ignorar NaN.
    """
    def safe_mean(series: pd.Series) -> Optional[float]:
        valid = series.dropna()
        return float(valid.mean()) if not valid.empty else None

    summary = {
        "Promedio Predespacho": safe_mean(df["Predespacho"]),
        "Promedio TX1":         safe_mean(df["TX1"]),
        "Promedio TX2":         safe_mean(df["TX2"]),
    }
    for col, label in [("TXR", "Promedio TXR"), ("TXF", "Promedio TXF")]:
        if col in df.columns and df[col].notna().any():
            summary[label] = safe_mean(df[col])
    summary["Promedio Mejor Versión"] = safe_mean(df["Mejor_Version"])
    summary["Promedio PB Mes"]        = safe_mean(df["PB_Diario"])
    return summary


# ==================================================================
#  ANÁLISIS DE SENSIBILIDAD
# ==================================================================

def calculate_sensitivity(
    df: pd.DataFrame,
    sensitivity_price: float,
    year: int,
    month: int,
) -> dict:
    """
    Calcula el promedio mensual proyectado si los días faltantes del mes
    tienen el precio indicado en sensitivity_price.

    Retorna un dict con:
      remaining_days   : días sin dato de PB_Diario
      days_with_data   : días con dato real
      days_in_month    : total de días del mes
      current_avg      : promedio de PB_Diario con los días reales
      sensitivity_avg  : promedio proyectado al completar el mes
    """
    days_in_month = calendar.monthrange(year, month)[1]
    pb_series = df["PB_Diario"].dropna()
    days_with_data = int(pb_series.count())
    remaining_days = days_in_month - days_with_data

    current_avg = float(pb_series.mean()) if days_with_data > 0 else None

    if remaining_days <= 0:
        return {
            "remaining_days": 0,
            "days_with_data": days_with_data,
            "days_in_month": days_in_month,
            "current_avg": current_avg,
            "sensitivity_avg": None,
        }

    sensitivity_avg = (float(pb_series.sum()) + remaining_days * sensitivity_price) / days_in_month

    return {
        "remaining_days": remaining_days,
        "days_with_data": days_with_data,
        "days_in_month": days_in_month,
        "current_avg": current_avg,
        "sensitivity_avg": sensitivity_avg,
    }


def extend_with_sensitivity(
    df: pd.DataFrame,
    sensitivity_price: float,
    year: int,
    month: int,
) -> pd.DataFrame:
    """
    Extiende df con filas para los días faltantes del mes asumiendo que
    PB_Diario = sensitivity_price para esos días. Recalcula los promedios
    acumulados (PB_PromMes, MejorVersion_PromMes) incluyendo los días proyectados.

    Columna añadida:
      Es_Sensibilidad : False para días reales, True para días proyectados
    """
    import datetime as dt

    df = df.copy()
    df["Es_Sensibilidad"] = False

    days_in_month = calendar.monthrange(year, month)[1]
    end_of_month = dt.date(year, month, days_in_month)

    try:
        last_date = dt.date.fromisoformat(str(df["Fecha"].iloc[-1]).strip())
    except (ValueError, IndexError):
        return df

    if last_date >= end_of_month:
        return df

    pb_sum = float(df["PB_Diario"].dropna().sum())
    days_with_data = int(df["PB_Diario"].notna().sum())
    if days_with_data == 0:
        return df

    new_rows = []
    current = last_date + dt.timedelta(days=1)
    k = 0
    while current <= end_of_month:
        k += 1
        row = {col: np.nan for col in df.columns}
        row["Fecha"] = str(current)
        row["Es_Sensibilidad"] = True
        row["PB_Diario"] = float(sensitivity_price)
        row["Mejor_Version"] = float(sensitivity_price)
        row["Mejor_Version_Nombre"] = "Sens."
        projected_avg = (pb_sum + k * float(sensitivity_price)) / (days_with_data + k)
        row["PB_PromMes"] = projected_avg
        row["MejorVersion_PromMes"] = projected_avg
        new_rows.append(row)
        current += dt.timedelta(days=1)

    if not new_rows:
        return df

    new_df = pd.DataFrame(new_rows, columns=df.columns)
    result = pd.concat([df, new_df], ignore_index=True)
    result["Es_Sensibilidad"] = result["Es_Sensibilidad"].fillna(False).astype(bool)
    return result


# ==================================================================
#  FORMATEO PARA DISPLAY
# ==================================================================

def build_display_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye la tabla de presentación con las columnas en el orden
    requerido por el dashboard, con nombres amigables.
    """
    rename_map = {
        "Fecha": "Fecha",
        "Predespacho": "Predespacho\nDiario",
        "TX1": "TX1\nDiario",
        "TX2": "TX2\nDiario",
        "Diferencia_Version": "Diferencia\nVersión",
        "Predespacho_PromMes": "Predespacho\nPromMes",
        "TX1_PromMes": "TX1\nPromMes",
        "TX2_PromMes": "TX2\nPromMes",
        "PB_Diario": "PB\nDiario",
        "Mejor_Version": "PB Mejor\nVersión",
        "PB_PromMes": "PB\nPromMes",
    }

    cols = list(rename_map.keys())
    display = df[[c for c in cols if c in df.columns]].copy()
    display = display.rename(columns=rename_map)

    return display
