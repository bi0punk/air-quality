import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Definir el nombre del archivo CSV
CSV_FILE = "datos_sensor.csv"

# Función para cargar datos desde el CSV
def cargar_datos():
    try:
        df = pd.read_csv(CSV_FILE)
        return df
    except FileNotFoundError:
        st.error("⚠️ El archivo CSV no se encontró.")
        return pd.DataFrame()  # DataFrame vacío si no se encuentra el archivo

# Título de la aplicación
st.title("📊 Datos del Sensor MQ-135")

# Ajustar el intervalo de actualización desde la barra lateral
tiempo_actualizacion = st.sidebar.slider("⏲️ Intervalo de actualización (segundos)", 1, 60, 5)

# Mostrar la hora de la última actualización
st.sidebar.write(f"🕒 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Cargar los datos
df = cargar_datos()

if not df.empty:
    # Mostrar los datos en tabla
    st.subheader("📋 Datos Registrados")
    st.dataframe(df)

    # Estadísticas del valor del sensor
    st.subheader("📈 Estadísticas del Sensor")
    estadisticas = df["valor_sensor"].describe()
    st.table(estadisticas)

    # Gráfica de líneas para el valor del sensor
    st.subheader("📊 Gráfica del Valor del Sensor")
    st.line_chart(df[["fecha_hora", "valor_sensor"]].set_index("fecha_hora"))

    # Filtro por fecha
    st.subheader("🔍 Filtrar por Fecha")
    fechas = pd.to_datetime(df["fecha_hora"]).dt.date.unique()
    fecha_seleccionada = st.selectbox("Selecciona una fecha", fechas)

    # Filtrar los datos por la fecha seleccionada
    df_filtrado = df[pd.to_datetime(df["fecha_hora"]).dt.date == fecha_seleccionada]

    if not df_filtrado.empty:
        st.subheader(f"📅 Datos para {fecha_seleccionada}")
        st.dataframe(df_filtrado)


        st.line_chart(df_filtrado)

        # Gráfica para los datos filtrados
        st.line_chart(df_filtrado[["fecha_hora", "valor_sensor"]].set_index("fecha_hora"))
    else:
        st.warning("⚠️ No hay datos para la fecha seleccionada.")
else:
    st.warning("⚠️ No se encontraron datos para mostrar.")

# Esperar antes de recargar
time.sleep(tiempo_actualizacion)

# Usar parámetros en la URL para forzar la recarga automática
st.set_query_params(updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
