"""
app.py
======
Punto de entrada principal de la aplicación Streamlit.
Orquesta la conexión FTPS, descarga de datos, cálculos y dashboard.

Ejecutar con:
    streamlit run app.py
"""

from __future__ import annotations

import calendar
import datetime

import pandas as pd
import streamlit as st

# Módulos propios
from ftp_client import FTPSClient
from data_loader import load_month_data, generate_demo_data
from calculations import (
    calculate_prices, calculate_monthly_summary,
    extend_with_sensitivity,
)
from dashboard import (
    inject_css,
    render_sidebar_brand,
    render_header,
    render_welcome,
    render_kpis,
    render_table,
    render_chart,
    render_file_status,
)
from excel_export import generate_excel
from html_export import generate_html

# ──────────────────────────────────────────────────────────────────
#  CONFIGURACIÓN DE PÁGINA
# ──────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Precio de Bolsa XM",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Aplicación de consulta del Precio de Bolsa de Energía — XM Colombia",
    },
)

inject_css()

# ──────────────────────────────────────────────────────────────────
#  ESTADO DE SESIÓN
# ──────────────────────────────────────────────────────────────────

if "df_raw" not in st.session_state:
    st.session_state.df_raw = None
if "df_calc" not in st.session_state:
    st.session_state.df_calc = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "connected" not in st.session_state:
    st.session_state.connected = False
if "ftp_client" not in st.session_state:
    st.session_state.ftp_client = None
if "periodo" not in st.session_state:
    st.session_state.periodo = (datetime.date.today().year, datetime.date.today().month)


# ──────────────────────────────────────────────────────────────────
#  SIDEBAR
# ──────────────────────────────────────────────────────────────────

with st.sidebar:
    render_sidebar_brand()

    # ── Modo de conexión ──────────────────────────────────────────
    st.markdown("#### 🔌 Conexión")
    mode = st.radio(
        "Modo",
        options=["Producción (FTPS)", "Demo (datos sintéticos)"],
        index=1,
        help="Use 'Demo' para explorar la aplicación sin credenciales FTPS.",
    )
    use_demo = mode == "Demo (datos sintéticos)"

    if not use_demo:
        with st.form("ftps_login_form"):
            ftps_host = st.text_input(
                "Servidor FTPS",
                value="xmftps.xm.com.co",
                placeholder="host o IP del servidor",
            )
            ftps_port = st.number_input("Puerto", value=210, min_value=1, max_value=65535)
            ftps_user = st.text_input("Usuario", placeholder="usuario FTP")
            ftps_pass = st.text_input("Contraseña", type="password", placeholder="••••••••")
            btn_connect = st.form_submit_button("Conectar", use_container_width=True)

        btn_disconnect = st.button("Desconectar", use_container_width=True)

        if btn_connect:
            if not ftps_user or not ftps_pass:
                st.error("❌ Ingresa usuario y contraseña.")
            else:
                with st.spinner("Conectando…"):
                    client = FTPSClient(ftps_host, ftps_user, ftps_pass, int(ftps_port))
                    ok, msg = client.connect()
                if ok:
                    st.session_state.ftp_client = client
                    st.session_state.connected = True
                    st.success(msg)
                else:
                    st.error(msg)
                    st.session_state.connected = False

        if btn_disconnect and st.session_state.ftp_client:
            st.session_state.ftp_client.disconnect()
            st.session_state.connected = False
            st.session_state.ftp_client = None
            st.info("Desconectado.")

        # Estado de conexión
        if st.session_state.connected:
            st.markdown(
                "<div style='color:#00FF41;font-size:0.8rem;padding:4px 0;"
                "text-shadow:0 0 6px rgba(0,255,65,0.6);'>"
                "● Conectado</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='color:#FF3333;font-size:0.8rem;padding:4px 0;'>"
                "○ Sin conexión</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Período ───────────────────────────────────────────────────
    st.markdown("#### 📅 Período")
    hoy = datetime.date.today()

    year = st.selectbox(
        "Año",
        options=list(range(2018, hoy.year + 1))[::-1],
        index=0,
    )
    month = st.selectbox(
        "Mes",
        options=list(range(1, 13)),
        format_func=lambda m: calendar.month_name[m],
        index=hoy.month - 1,
    )

    st.markdown("---")

    # ── Opciones del dashboard ────────────────────────────────────
    st.markdown("#### 🎛️ Series del gráfico")
    show_pred = st.checkbox("Predespacho",  value=True)
    show_tx1  = st.checkbox("TX1",          value=True)
    show_tx2  = st.checkbox("TX2",          value=True)
    show_txr  = st.checkbox("TXR",          value=True)
    show_txf  = st.checkbox("TXF",          value=True)
    show_pb   = st.checkbox("PB Diario",    value=False)
    show_prom = st.checkbox("Prom. Mensual",value=True)

    st.markdown("---")
    st.markdown("#### 🎯 Sensibilidad")
    use_sensitivity = st.checkbox(
        "Activar sensibilidad",
        value=True,
        help="Muestra el promedio mensual proyectado si los días faltantes tienen el precio indicado.",
    )
    sensitivity_price = st.number_input(
        "Precio supuesto ($/kWh)",
        min_value=0.0,
        max_value=9999.0,
        value=300.0,
        step=10.0,
        format="%.2f",
        disabled=not use_sensitivity,
        help="Precio hipotético para los días sin información del mes actual.",
    )

    st.markdown("---")

    # ── Botón principal de descarga / demo ────────────────────────
    btn_load = st.button(
        "▶ Cargar datos" if not use_demo else "▶ Generar datos demo",
        type="primary",
        use_container_width=True,
    )


# ──────────────────────────────────────────────────────────────────
#  LÓGICA DE CARGA
# ──────────────────────────────────────────────────────────────────

if btn_load:
    if use_demo:
        with st.spinner("Generando datos de demostración…"):
            df_raw = generate_demo_data(year, month)

        st.session_state.df_raw = df_raw
        st.session_state.periodo = (year, month)
        st.success(f"✅ Datos demo generados para {calendar.month_name[month]} {year}")

    else:
        # Verificar conexión
        if not st.session_state.connected or st.session_state.ftp_client is None:
            st.error("❌ Conéctate primero al servidor FTPS.")
            st.stop()

        client: FTPSClient = st.session_state.ftp_client

        # Verificar que la conexión sigue activa
        if not client.is_connected():
            st.warning("⚠️ La sesión FTPS expiró. Reconectando…")
            ok, msg = client.connect()
            if not ok:
                st.error(f"No se pudo reconectar: {msg}")
                st.stop()

        # Barra de progreso
        progress_bar = st.progress(0, text="Iniciando descarga…")
        status_text  = st.empty()

        def update_progress(fraction: float, message: str) -> None:
            progress_bar.progress(min(fraction, 1.0), text=message)
            status_text.markdown(
                f"<div style='font-size:0.8rem;color:#7F93B5;'>{message}</div>",
                unsafe_allow_html=True,
            )

        try:
            df_raw = load_month_data(client, year, month, progress_callback=update_progress)
            progress_bar.progress(1.0, text="✅ Descarga completada")
            status_text.empty()
            st.session_state.df_raw = df_raw
            st.session_state.periodo = (year, month)
            st.success(
                f"✅ Datos descargados correctamente para {calendar.month_name[month]} {year}"
            )
        except Exception as e:
            st.error(f"❌ Error durante la descarga: {e}")
            st.stop()


# ──────────────────────────────────────────────────────────────────
#  PROCESAMIENTO Y DASHBOARD
# ──────────────────────────────────────────────────────────────────

if st.session_state.df_raw is not None:
    year_s, month_s = st.session_state.periodo
    df_raw: pd.DataFrame = st.session_state.df_raw

    # Calcular precios y versiones
    df_calc = calculate_prices(df_raw)

    # Recortar al último día con datos reales (evita filas vacías y promedios proyectados)
    price_cols = [c for c in ["Predespacho", "TX1", "TX2", "TXR", "TXF"] if c in df_calc.columns]
    has_data = df_calc[price_cols].notna().any(axis=1)
    if has_data.any():
        df_calc = df_calc.loc[: has_data[has_data].index[-1]].reset_index(drop=True)

    # Resumen mensual
    summary = calculate_monthly_summary(df_calc)

    # ── CABECERA ─────────────────────────────────────────────────
    render_header(year_s, month_s)

    # ── KPIs ─────────────────────────────────────────────────────
    st.markdown("### 📊 Indicadores del Mes")
    render_kpis(summary)
    st.markdown("<div style='margin:18px 0;'></div>", unsafe_allow_html=True)

    # DataFrame extendido con filas de sensibilidad para gráfico y tabla
    df_display = (
        extend_with_sensitivity(df_calc, sensitivity_price, year_s, month_s)
        if use_sensitivity else df_calc
    )

    # ── GRÁFICO ──────────────────────────────────────────────────
    st.markdown("### 📈 Evolución de Precios")
    render_chart(
        df_display,
        show_predespacho=show_pred,
        show_tx1=show_tx1,
        show_tx2=show_tx2,
        show_txr=show_txr,
        show_txf=show_txf,
        show_pb=show_pb,
        show_prom=show_prom,
        show_sensitivity=use_sensitivity,
    )

    # ── TABLA ────────────────────────────────────────────────────
    st.markdown("### 📋 Datos Diarios")
    render_table(df_display)

    # ── ESTADO DE ARCHIVOS ───────────────────────────────────────
    render_file_status(df_calc)

    # ── EXPORTAR EXCEL ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💾 Exportar")

    col_dl, col_dl2, col_info = st.columns([1, 1, 3])
    with col_dl:
        try:
            excel_bytes = generate_excel(df_calc, summary, year_s, month_s)
            filename = f"precio_bolsa_xm_{year_s}_{month_s:02d}.xlsx"
            st.download_button(
                label="⬇ Descargar Excel",
                data=excel_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error generando Excel: {e}")

    with col_dl2:
        try:
            html_bytes = generate_html(df_calc, summary, year_s, month_s)
            filename_html = f"precio_bolsa_xm_{year_s}_{month_s:02d}.html"
            st.download_button(
                label="⬇ Descargar HTML",
                data=html_bytes,
                file_name=filename_html,
                mime="text/html",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error generando HTML: {e}")

    with col_info:
        st.markdown(
            "<div style='color:#7F93B5;font-size:0.82rem;padding-top:8px;'>"
            "<strong>Excel:</strong> dos hojas (tabla + gráfico embebido y resumen mensual). "
            "<strong>HTML:</strong> reporte interactivo de una sola página, ideal para compartir por correo o chat."
            "</div>",
            unsafe_allow_html=True,
        )

else:
    # ── PANTALLA DE BIENVENIDA ───────────────────────────────────
    render_welcome()
