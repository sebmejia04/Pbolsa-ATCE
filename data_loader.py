"""
data_loader.py
==============
Descarga y parsea los archivos IMAR y TRSD desde el servidor FTPS de XM.
Gestiona la lógica de rutas, nombres de archivos y extracción de valores horarios.
"""

import io
import calendar
import datetime
import numpy as np
import pandas as pd
from typing import Optional, Callable, Dict, Tuple
from ftp_client import FTPSClient

# ------------------------------------------------------------------
# Rutas base en el servidor FTP
# ------------------------------------------------------------------
IMAR_BASE = "/INFORMACION_XM/Publico/Predespachoideal"
TRSD_BASE = "/INFORMACION_XM/PUBLICOK/SIC/COMERCIA"

# Nombre de fila a buscar en cada tipo de archivo
IMAR_ROW_KEY = "COSTO MARGINAL"
TRSD_ROW_KEY = "PBNA"
PEP_ROW_KEY  = "SISTEMA"   # archivo pepmmdd.txN — precio de techado del día/versión
PEA_ROW_KEY  = "PEA"       # archivo PME140mm.txa — umbral de activación del mes

NUM_HOURS = 24


# ==================================================================
#  PARSER DE ARCHIVOS TXT / CSV con múltiples delimitadores
# ==================================================================

def _parse_content(content: str) -> Optional[pd.DataFrame]:
    """
    Intenta parsear el contenido de texto con varios delimitadores.
    Retorna un DataFrame o None si no fue posible.
    """
    if not content or not content.strip():
        return None

    delimiters = ["\t", ";", ",", "|", "  "]  # tabulador primero (más común en XM)

    for sep in delimiters:
        try:
            df = pd.read_csv(
                io.StringIO(content),
                sep=sep,
                header=None,
                engine="python",
                on_bad_lines="skip",
                dtype=str,
            )
            # Debe tener al menos la columna de nombre + algunas horas
            if df.shape[1] >= 5 and df.shape[0] >= 2:
                return df
        except Exception:
            continue

    # Fallback: separar por espacios múltiples (formato de ancho fijo)
    try:
        lines = [line for line in content.strip().split("\n") if line.strip()]
        rows = [line.split() for line in lines]
        if rows:
            max_cols = max(len(r) for r in rows)
            padded = [r + [""] * (max_cols - len(r)) for r in rows]
            return pd.DataFrame(padded)
    except Exception:
        pass

    return None


def _extract_row_values(df: pd.DataFrame, row_key: str) -> Optional[np.ndarray]:
    """
    Busca una fila cuya primera columna coincida (parcialmente) con row_key
    y extrae los primeros 24 valores numéricos de las columnas restantes.
    """
    if df is None or df.empty:
        return None

    col0 = df.iloc[:, 0].astype(str).str.strip().str.upper()

    # Coincidencia exacta primero
    mask = col0 == row_key.upper()
    if not mask.any():
        # Coincidencia parcial
        mask = col0.str.contains(row_key.upper(), na=False)

    if not mask.any():
        return None

    row = df[mask].iloc[0]
    values = []
    found_numeric = False
    
    for col in df.columns[1:]:
        raw = str(row[col]).strip().replace(",", ".").replace(" ", "")
        try:
            val = float(raw)
            values.append(val)
            found_numeric = True
        except ValueError:
            if found_numeric:
                # Hueco real en medio de las horas → NaN
                values.append(np.nan)
            # Si aún no hemos encontrado números, es columna de texto → saltar

    # Asegurar exactamente 24 valores
    arr = np.array(values[:NUM_HOURS], dtype=float)
    if len(arr) < NUM_HOURS:
        arr = np.concatenate([arr, np.full(NUM_HOURS - len(arr), np.nan)])

    return arr


def _extract_single_value(df: pd.DataFrame, row_key: str, col_index: int) -> Optional[float]:
    """
    Busca una fila cuya primera columna coincida (parcialmente) con row_key
    y extrae el valor numérico de la columna col_index (0-indexada).
    """
    if df is None or df.empty:
        return None

    col0 = df.iloc[:, 0].astype(str).str.strip().str.upper()

    mask = col0 == row_key.upper()
    if not mask.any():
        mask = col0.str.contains(row_key.upper(), na=False)
    if not mask.any():
        return None

    row = df[mask].iloc[0]
    if col_index >= len(row):
        return None

    raw = str(row.iloc[col_index]).strip().replace(",", ".").replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return None


# ==================================================================
#  CARGA DE ARCHIVOS INDIVIDUALES
# ==================================================================

def load_imar(
    client: FTPSClient,
    year: int,
    month: int,
    day: int,
) -> Optional[float]:
    """
    Descarga el archivo IMAR para una fecha dada y calcula el
    Predespacho diario: promedio(Costo Marginal h1..h24) / 1000.

    El archivo está en:
      IMAR_BASE/YYYY-MM/IMARmmdd.txt
    """
    path = f"{IMAR_BASE}/{year:04d}-{month:02d}/IMAR{month:02d}{day:02d}.txt"
    content = client.download_file(path)

    if content is None:
        return None

    df = _parse_content(content)
    values = _extract_row_values(df, IMAR_ROW_KEY)

    if values is None or np.all(np.isnan(values)):
        return None

    return float(np.nanmean(values)) / 1000.0


def load_pea(client: FTPSClient, year: int, month: int) -> Optional[float]:
    """
    Descarga el archivo PME140 del mes y extrae el Precio de Escasez de
    Activación (PEA): umbral horario de PBNA a partir del cual una hora
    se techa con el valor de SISTEMA del archivo PEP correspondiente.

    Aplica a todas las versiones (TX1, TX2, TXR, TXF) de ese mes. El
    archivo está en:
      TRSD_BASE/YYYY-MM/PME140mm.txa
    """
    path = f"{TRSD_BASE}/{year:04d}-{month:02d}/PME140{month:02d}.txa"
    content = client.download_file(path)

    if content is None:
        return None

    df = _parse_content(content)
    return _extract_single_value(df, PEA_ROW_KEY, col_index=2)


def load_pep(
    client: FTPSClient,
    year: int,
    month: int,
    day: int,
    version: str,
) -> Optional[float]:
    """
    Descarga el archivo PEP para una fecha y versión dadas y extrae el
    valor de SISTEMA: precio al cual se techa cualquier hora del día cuyo
    PBNA supere el PEA.

    El archivo está en:
      TRSD_BASE/YYYY-MM/pepmmdd.{version}
    """
    path = f"{TRSD_BASE}/{year:04d}-{month:02d}/pep{month:02d}{day:02d}.{version}"
    content = client.download_file(path)

    if content is None:
        return None

    df = _parse_content(content)
    return _extract_single_value(df, PEP_ROW_KEY, col_index=1)


def load_trsd(
    client: FTPSClient,
    year: int,
    month: int,
    day: int,
    version: str,  # "tx1", "tx2", "txr" o "txf"
    pea: Optional[float] = None,
) -> Tuple[Optional[float], bool, Optional[np.ndarray], Optional[np.ndarray], Optional[float]]:
    """
    Descarga el archivo TRSD para una fecha y versión dadas y calcula
    el PB diario: promedio(PBNA h1..h24).

    Siempre intenta descargar también el archivo PEP de esa fecha/versión
    (pepmmdd.{version}) para obtener SISTEMA. Si se conoce `pea` (Precio
    de Escasez de Activación del mes) y SISTEMA está disponible, cada hora
    cuyo PBNA supere `pea` se techa al valor de SISTEMA. Si falta `pea` o
    SISTEMA, se usan las horas sin techar.

    El archivo está en:
      TRSD_BASE/YYYY-MM/trsdmmdd.{version}

    Retorna (promedio_techado, hubo_techado, horas_crudas, horas_techadas, sistema).
    """
    path = f"{TRSD_BASE}/{year:04d}-{month:02d}/trsd{month:02d}{day:02d}.{version}"
    content = client.download_file(path)

    if content is None:
        return None, False, None, None, None

    df = _parse_content(content)
    raw_hours = _extract_row_values(df, TRSD_ROW_KEY)

    if raw_hours is None or np.all(np.isnan(raw_hours)):
        return None, False, None, None, None

    sistema = load_pep(client, year, month, day, version)

    corrected_hours = raw_hours.copy()
    capped = False
    if pea is not None and sistema is not None:
        exceeds = raw_hours > pea
        if np.any(exceeds):
            corrected_hours = np.where(exceeds, sistema, raw_hours)
            capped = True

    avg = float(np.nanmean(corrected_hours))
    return avg, capped, raw_hours, corrected_hours, sistema


# ==================================================================
#  CARGA DEL MES COMPLETO
# ==================================================================

def _txr_txf_availability(year: int, month: int):
    """
    Retorna (txr_available, txf_available) para el mes solicitado.
    TXR se publica el día 5 del mes siguiente; TXF el día 10.
    """
    today = datetime.date.today()
    next_year  = year + 1 if month == 12 else year
    next_month = 1        if month == 12 else month + 1
    txr_date = datetime.date(next_year, next_month, 5)
    txf_date = datetime.date(next_year, next_month, 10)
    return today >= txr_date, today >= txf_date


def load_month_data(
    client: FTPSClient,
    year: int,
    month: int,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> pd.DataFrame:
    """
    Descarga IMAR (Predespacho) y TRSD (TX1, TX2, TXR*, TXF*) para cada día
    del mes indicado. TXR y TXF sólo se descargan si ya fueron publicados
    (día 5 y día 10 del mes siguiente, respectivamente).

    Retorna DataFrame con columnas: Fecha, Predespacho, TX1, TX2[, TXR][, TXF],
    además de, para cada versión PBNA (TX1, TX2, TXR*, TXF*):
      · PEA                                : umbral de activación del mes
      · {V}_Techado                        : hubo techado ese día en esa versión
      · {V}_Sistema                        : valor SISTEMA del día/versión
      · {V}_Horas_Crudas, {V}_Horas_Techadas : listas de 24 valores horarios de
                                                PBNA, antes y después del techado
    Los días sin información tienen NaN (no cero).
    """
    num_days = calendar.monthrange(year, month)[1]
    load_txr, load_txf = _txr_txf_availability(year, month)

    # PEA: un solo archivo para todo el mes, aplica a TX1/TX2/TXR/TXF
    if progress_callback:
        progress_callback(0.0, "📥 Descargando PEA (PME140)…")
    pea = load_pea(client, year, month)

    trsd_versions = 2 + int(load_txr) + int(load_txf)          # tx1, tx2, [txr], [txf]
    total_ops = num_days * (1 + 2 * trsd_versions) + 1          # +1 imar, x2 = trsd+pep, +1 PEA
    ops_done  = 1                                               # PEA ya se intentó

    records: list[Dict] = []

    for day in range(1, num_days + 1):
        fecha = pd.Timestamp(year=year, month=month, day=day).date()

        # ── IMAR (Predespacho) ──────────────────────────────────────────
        ops_done += 1
        if progress_callback:
            progress_callback(ops_done / total_ops,
                              f"📥 Descargando IMAR {day:02d}/{month:02d}/{year}…")
        predespacho = load_imar(client, year, month, day)

        # ── TRSD TX1 ────────────────────────────────────────────────────
        ops_done += 2
        if progress_callback:
            progress_callback(ops_done / total_ops,
                              f"📥 Descargando TX1  {day:02d}/{month:02d}/{year}…")
        tx1, tx1_capped, tx1_raw_h, tx1_corr_h, tx1_sistema = load_trsd(
            client, year, month, day, "tx1", pea=pea
        )

        # ── TRSD TX2 ────────────────────────────────────────────────────
        ops_done += 2
        if progress_callback:
            progress_callback(ops_done / total_ops,
                              f"📥 Descargando TX2  {day:02d}/{month:02d}/{year}…")
        tx2, tx2_capped, tx2_raw_h, tx2_corr_h, tx2_sistema = load_trsd(
            client, year, month, day, "tx2", pea=pea
        )

        # ── TRSD TXR (sólo si fue publicado) ───────────────────────────
        txr, txr_capped, txr_raw_h, txr_corr_h, txr_sistema = None, False, None, None, None
        if load_txr:
            ops_done += 2
            if progress_callback:
                progress_callback(ops_done / total_ops,
                                  f"📥 Descargando TXR  {day:02d}/{month:02d}/{year}…")
            txr, txr_capped, txr_raw_h, txr_corr_h, txr_sistema = load_trsd(
                client, year, month, day, "txr", pea=pea
            )

        # ── TRSD TXF (sólo si fue publicado) ───────────────────────────
        txf, txf_capped, txf_raw_h, txf_corr_h, txf_sistema = None, False, None, None, None
        if load_txf:
            ops_done += 2
            if progress_callback:
                progress_callback(ops_done / total_ops,
                                  f"📥 Descargando TXF  {day:02d}/{month:02d}/{year}…")
            txf, txf_capped, txf_raw_h, txf_corr_h, txf_sistema = load_trsd(
                client, year, month, day, "txf", pea=pea
            )

        record = {
            "Fecha":              fecha,
            "PEA":                pea,
            "Predespacho":        predespacho,
            "TX1":                tx1,
            "TX2":                tx2,
            "TX1_Techado":        tx1_capped,
            "TX2_Techado":        tx2_capped,
            "TX1_Sistema":        tx1_sistema,
            "TX2_Sistema":        tx2_sistema,
            "TX1_Horas_Crudas":   tx1_raw_h.tolist() if tx1_raw_h is not None else None,
            "TX1_Horas_Techadas": tx1_corr_h.tolist() if tx1_corr_h is not None else None,
            "TX2_Horas_Crudas":   tx2_raw_h.tolist() if tx2_raw_h is not None else None,
            "TX2_Horas_Techadas": tx2_corr_h.tolist() if tx2_corr_h is not None else None,
        }
        if load_txr:
            record["TXR"] = txr
            record["TXR_Techado"] = txr_capped
            record["TXR_Sistema"] = txr_sistema
            record["TXR_Horas_Crudas"] = txr_raw_h.tolist() if txr_raw_h is not None else None
            record["TXR_Horas_Techadas"] = txr_corr_h.tolist() if txr_corr_h is not None else None
        if load_txf:
            record["TXF"] = txf
            record["TXF_Techado"] = txf_capped
            record["TXF_Sistema"] = txf_sistema
            record["TXF_Horas_Crudas"] = txf_raw_h.tolist() if txf_raw_h is not None else None
            record["TXF_Horas_Techadas"] = txf_corr_h.tolist() if txf_corr_h is not None else None

        records.append(record)

    return pd.DataFrame(records)


# ==================================================================
#  MODO DEMO (sin conexión FTP)  ← útil para pruebas
# ==================================================================

def generate_demo_data(year: int, month: int) -> pd.DataFrame:
    """
    Genera datos sintéticos realistas para demostración.
    Simula los rezagos de publicación de cada versión:
      Predespacho : disponible al día siguiente
      TX1         : +2 días desde la fecha operativa
      TX2         : +4 días desde la fecha operativa
      TXR         : todo el mes publicado el día 5 del mes siguiente
      TXF         : todo el mes publicado el día 10 del mes siguiente

    También simula el techado por PEP: genera 24 horas sintéticas por
    versión/día, un PEA mensual y un SISTEMA por día/versión, y techa las
    horas que superan el PEA — para poder previsualizar sin conexión FTPS
    los indicadores 🔻 y las hojas horarias del Excel de las cuatro
    versiones (TX1, TX2, TXR, TXF).
    """
    num_days = calendar.monthrange(year, month)[1]
    today = datetime.date.today()
    rng = np.random.default_rng(seed=year * 100 + month)

    base_price = rng.uniform(280, 340)
    noise = rng.normal(0, 15, num_days)
    trend = np.linspace(0, 20, num_days)

    load_txr, load_txf = _txr_txf_availability(year, month)

    # PEA mensual: umbral por encima del cual una hora se techa con SISTEMA
    # (rango alto para que el techado sea un evento ocasional, no diario)
    pea_demo = float(base_price * rng.uniform(1.15, 1.30))

    def _hourly_with_cap(daily_level: float):
        """Genera 24 horas alrededor de daily_level, techa las que superan
        pea_demo y retorna (horas_crudas, horas_techadas, sistema, capped)."""
        raw = daily_level * rng.uniform(0.85, 1.05, NUM_HOURS)
        sistema = float(pea_demo * rng.uniform(0.85, 0.95))
        exceeds = raw > pea_demo
        capped = bool(np.any(exceeds))
        corrected = np.where(exceeds, sistema, raw)
        return raw, corrected, sistema, capped

    records = []
    for day in range(1, num_days + 1):
        fecha = datetime.date(year, month, day)
        p = base_price + trend[day - 1] + noise[day - 1]

        record: Dict = {"Fecha": fecha, "PEA": pea_demo}

        pred = round(p * rng.uniform(0.97, 1.03), 2) if fecha <= today else None
        record["Predespacho"] = pred

        tx1_date = fecha + datetime.timedelta(days=2)
        if tx1_date <= today:
            raw1, corr1, sist1, cap1 = _hourly_with_cap(p * rng.uniform(0.99, 1.01))
            record["TX1"] = round(float(np.mean(corr1)), 2)
            record["TX1_Techado"] = cap1
            record["TX1_Sistema"] = round(sist1, 2)
            record["TX1_Horas_Crudas"] = [round(float(v), 2) for v in raw1]
            record["TX1_Horas_Techadas"] = [round(float(v), 2) for v in corr1]
        else:
            record["TX1"] = None
            record["TX1_Techado"] = False
            record["TX1_Sistema"] = None
            record["TX1_Horas_Crudas"] = None
            record["TX1_Horas_Techadas"] = None

        tx2_date = fecha + datetime.timedelta(days=4)
        if tx2_date <= today:
            raw2, corr2, sist2, cap2 = _hourly_with_cap(p * rng.uniform(0.995, 1.005))
            record["TX2"] = round(float(np.mean(corr2)), 2)
            record["TX2_Techado"] = cap2
            record["TX2_Sistema"] = round(sist2, 2)
            record["TX2_Horas_Crudas"] = [round(float(v), 2) for v in raw2]
            record["TX2_Horas_Techadas"] = [round(float(v), 2) for v in corr2]
        else:
            record["TX2"] = None
            record["TX2_Techado"] = False
            record["TX2_Sistema"] = None
            record["TX2_Horas_Crudas"] = None
            record["TX2_Horas_Techadas"] = None

        # TXR y TXF: disponibles para TODOS los días del mes a la vez
        if load_txr:
            rawr, corrr, sistr, capr = _hourly_with_cap(p * rng.uniform(0.9995, 1.0005))
            record["TXR"] = round(float(np.mean(corrr)), 2)
            record["TXR_Techado"] = capr
            record["TXR_Sistema"] = round(sistr, 2)
            record["TXR_Horas_Crudas"] = [round(float(v), 2) for v in rawr]
            record["TXR_Horas_Techadas"] = [round(float(v), 2) for v in corrr]
        if load_txf:
            rawf, corrf, sistf, capf = _hourly_with_cap(p * rng.uniform(0.9998, 1.0002))
            record["TXF"] = round(float(np.mean(corrf)), 2)
            record["TXF_Techado"] = capf
            record["TXF_Sistema"] = round(sistf, 2)
            record["TXF_Horas_Crudas"] = [round(float(v), 2) for v in rawf]
            record["TXF_Horas_Techadas"] = [round(float(v), 2) for v in corrf]

        records.append(record)

    return pd.DataFrame(records)
