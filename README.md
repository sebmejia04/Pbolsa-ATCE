# ⚡ Precio de Bolsa de Energía — XM Colombia

Aplicación Streamlit para consultar, procesar, visualizar y exportar el **Precio de Bolsa de Energía** con todas sus versiones publicadas por XM.

---

## Estructura del proyecto

```
xm_precios/
├── app.py              # Punto de entrada — streamlit run app.py
├── ftp_client.py       # Cliente FTPS seguro
├── data_loader.py      # Descarga y parseo de archivos IMAR / TRSD
├── calculations.py     # Cálculos: Mejor Versión, Diferencia, Promedios, Sensibilidad
├── dashboard.py        # Componentes visuales Streamlit + Plotly
├── excel_export.py     # Exportación a Excel (2 hojas + gráfico embebido)
├── requirements.txt    # Dependencias
└── README.md
```

---

## Instalación

```bash
# 1. Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
.venv\Scripts\activate             # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar
streamlit run app.py
```

Requiere **Python 3.11+**.

---

## Despliegue en Streamlit Community Cloud

Para que la app sea accesible por URL (y embebible como pestaña en un canal de Teams):

1. **Sube el repo a GitHub** (puede ser privado):
   ```bash
   git remote add origin https://github.com/<tu-usuario>/<tu-repo>.git
   git branch -M main
   git push -u origin main
   ```
2. Entra a [share.streamlit.io](https://share.streamlit.io) con tu cuenta (puedes vincular GitHub).
3. **New app** → selecciona el repo, la rama `main` y el archivo principal `app.py`.
4. Deploy. Streamlit instala `requirements.txt` y usa `runtime.txt` para fijar la versión de Python.
5. En **Settings → Sharing**, restringe el acceso a personas específicas por correo si no quieres que la app sea pública.
6. Copia la URL generada y agrégala en Teams como pestaña **Sitio web** dentro del canal — quedará embebida sin necesidad de descargas.

**Nota de seguridad:** las credenciales FTPS se ingresan en cada sesión desde el formulario lateral y no se guardan en el código ni en disco; aun así, al desplegar en Streamlit Cloud los datos de la sesión pasan por infraestructura externa a EPM. Si la política interna no lo permite, considera alojarlo en un servidor propio o Azure en su lugar.

---

## Modos de uso

### Modo Demo
Sin credenciales FTPS. Genera datos sintéticos realistas que simulan
los rezagos de publicación de cada versión. Ideal para explorar y validar
el flujo de la aplicación.

### Modo Producción (FTPS)
Conecta al servidor FTP de XM:

| Campo      | Valor                    |
|------------|--------------------------|
| Servidor   | `xmftps.xm.com.co`       |
| Puerto     | `210`                    |
| Usuario    | Credenciales XM          |
| Contraseña | Credenciales XM          |

---

## Lógica de cálculo

### Predespacho Diario
```
Predespacho = mean(Costo_Marginal_h1..h24) / 1000
Fuente: IMAR{mm}{dd}.txt
Ruta: /INFORMACION_XM/Publico/Predespachoideal/YYYY-MM/
```

### TX1 / TX2 / TXR / TXF Diario (PB)
```
PB = mean(PBNA_h1..h24)
Fuente TX1:  trsd{mm}{dd}.tx1
Fuente TX2:  trsd{mm}{dd}.tx2
Fuente TXR:  trsd{mm}{dd}.txr
Fuente TXF:  trsd{mm}{dd}.txf
Ruta: /INFORMACION_XM/PUBLICOK/SIC/COMERCIA/YYYY-MM/
```

### Mejor Versión Disponible
```
TXF > TXR > TX2 > TX1 > Predespacho
```
Se selecciona automáticamente la versión de mayor calidad disponible para cada día.

### Diferencia de Versión
```
Δ = Mejor_Versión_actual - Versión_inmediatamente_inferior (mismo día)
```

### Rezagos de publicación
| Versión     | Disponible a partir de                    |
|-------------|-------------------------------------------|
| Predespacho | 1 día antes de la fecha operativa         |
| TX1         | 2 días después de la fecha operativa      |
| TX2         | 4 días después de la fecha operativa      |
| TXR         | Varios días después (redespacho)          |
| TXF         | Liquidación final (semanas después)       |

---

## Análisis de sensibilidad

Permite proyectar el promedio mensual final asumiendo un precio hipotético
para los días sin información. Se activa desde el panel lateral:

- **Precio supuesto ($/kWh)**: precio que se asigna a los días faltantes.
- Las filas proyectadas se muestran visualmente diferenciadas en la tabla y el gráfico.
- El promedio mensual proyectado (`PB_PromMes`) se recalcula incluyendo esos días.

---

## Exportación Excel

El archivo generado contiene, en este orden:

1. **Datos Diarios**: tabla completa con todas las versiones y columnas calculadas, con escala
   de color suave por precio, un **gráfico de líneas embebido** (evolución de versiones y
   promedio mensual acumulado) y, debajo de la gráfica, el **Resumen Mensual** (promedios
   globales y notas metodológicas).
2. **PEP**: en A1 el PEA (Precio de Escasez de Activación) del mes; en A2 la etiqueta "PEP
   (Precio de Escasez Ponderado)" que identifica la tabla de abajo, con el valor de SISTEMA
   publicado cada día para cada versión (TX1, TX2, TXR, TXF).
3. **{Versión} Horario** / **{Versión} Horario Techado** — un par de hojas por cada versión
   PBNA disponible (TX1, TX2, TXR*, TXF*): matriz Fecha | H1..H24 | Promedio con el PBNA sin
   techar, seguida de la misma matriz corregida con el PEP de esa versión. Si un día no tuvo
   ninguna hora corregida, la fila es idéntica en ambas hojas; las horas sí corregidas se
   resaltan con relleno naranja y un comentario.

El gráfico incluye:
- Series: Predespacho, TX1, TX2, TXR, TXF, Mejor Versión, PB Diario y Promedio Mensual.
- Eje X con fechas en formato `dd-mmm`.
- Eje Y con límite inferior al múltiplo de 50 por debajo del precio más bajo del mes.

### Techado por PEP (Precio de Escasez Ponderado)

Las horas de PBNA (TX1, TX2, TXR, TXF) que superan el **PEA** se techan al valor de **SISTEMA**
publicado para ese día/versión en el archivo `pepmmdd.txN`. El PEA es un único valor mensual
(archivo `PME140mm.txa`). Predespacho/IMAR nunca se techa. En "Datos Diarios" las celdas de
precio afectadas por el techado se marcan con un **borde grueso rojo** y un comentario
explicativo.

---

## Notas técnicas

- Los días sin información muestran `NaN`, **nunca cero**.
- Los promedios mensuales en la tabla son **acumulados** (expanding mean).
- El parser de archivos intenta automáticamente: tabulador, punto y coma, coma, barra vertical y ancho fijo.
- Las credenciales **nunca se almacenan** en el código ni en disco.
