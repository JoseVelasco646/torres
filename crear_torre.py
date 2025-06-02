import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import time
import threading
import random
from datetime import datetime
from supabase import create_client, Client
from streamlit_autorefresh import st_autorefresh
import folium
from streamlit_folium import st_folium
import requests
from fpdf import FPDF
from io import BytesIO
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes




SUPABASE_URL = "https://wkimchzmykvcofvprfat.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraW1jaHpteWt2Y29mdnByZmF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgwMjQ4ODgsImV4cCI6MjA2MzYwMDg4OH0.O84iGohEv1kgLZFoUaQun-SoFGO2XaDWHYJCsudYArQ"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

st.set_page_config(page_title="Simulador Torres Meteorológicas", layout="wide")



def mostrar_mapa_torres():
    # Obtener torres desde la base de datos
    response = supabase.table("torres").select("*").execute()
    torres = response.data if response.data else []

    if not torres:
        st.info("No hay torres para mostrar en el mapa.")
        return

    
    mapa = folium.Map(location=[31.8667, -116.6000], zoom_start=7)

    for torre in torres:
        nombre = torre.get("nombre", "Sin nombre")
        ubicacion = torre.get("ubicacion", {})
        lat = ubicacion.get("lat")
        lon = ubicacion.get("lon")
        estado = torre.get("estado", "Desconocido")

        if lat and lon:
            popup_text = f"<b>{nombre}</b><br>Estado: {estado}<br>Lat: {lat}<br>Lon: {lon}"
            folium.Marker(
                location=[lat, lon],
                popup=popup_text,
                icon=folium.Icon(color="blue" if estado == "Activa" else "red")
            ).add_to(mapa)

    # Mostrar mapa 
    st.subheader("Mapa de Torres Meteorológicas")
    st_folium(mapa, width=700, height=500)

def crear_torre():
    st.header("Crear o Editar Torre")

    modo_edicion = st.session_state.get("modo_edicion", False)
    torre_editando = st.session_state.get("torre_editando", None)

    
    lat_baja_california = 31.8667
    lon_baja_california = -116.6000

    with st.form("form_torre"):
        if modo_edicion and torre_editando:
            nombre = st.text_input("Nombre de la Torre", value=torre_editando["nombre"])
            lat = st.text_input("Latitud", value=str(torre_editando["ubicacion"].get("lat", lat_baja_california)))
            lon = st.text_input("Longitud", value=str(torre_editando["ubicacion"].get("lon", lon_baja_california)))
            estado = st.selectbox("Estado", ["Activa", "Inactiva", "Falla", "Mantenimiento"],
                                  index=["Activa", "Inactiva", "Falla", "Mantenimiento"].index(torre_editando["estado"]))
        else:
            nombre = st.text_input("Nombre de la Torre")
            lat = st.text_input("Latitud", value=str(lat_baja_california))
            lon = st.text_input("Longitud", value=str(lon_baja_california))
            estado = st.selectbox("Estado", ["Activa", "Inactiva", "Falla", "Mantenimiento"])

        enviar = st.form_submit_button("Guardar Torre")

    if enviar:
        if not nombre or not lat or not lon:
            st.error("Completa todos los campos.")
            return

        try:
            lat_float = float(lat)
            lon_float = float(lon)
        except:
            st.error("Latitud y longitud deben ser números válidos.")
            return

        ubicacion = {"lat": lat_float, "lon": lon_float}
        data = {
            "nombre": nombre,
            "ubicacion": ubicacion,
            "estado": estado,
        }

        if modo_edicion and torre_editando:
            supabase.table("torres").update(data).eq("id_torre", torre_editando["id_torre"]).execute()
            st.success("Torre actualizada correctamente.")
            st.session_state["modo_edicion"] = False
            st.session_state["torre_editando"] = None
        else:
            data["usuario_asignado"] = None
            response = supabase.table("torres").insert(data).execute()
            if response.data:
                st.success("Torre creada correctamente.")
                nueva_torre = response.data[0]
                id_nueva_torre = nueva_torre["id_torre"]
                iniciar_simulacion(id_nueva_torre)
            else:
                st.error("Error al crear torre.")

    mostrar_torres()
    mostrar_mapa_torres()


# mostrar torres 
def mostrar_torres():
    st.subheader("Torres registradas")

    response = supabase.table("torres").select("*").execute()
    if not response.data:
        st.info("No hay torres registradas.")
        return
    

    for torre in response.data:
        nombre = torre.get("nombre", "Sin nombre")
        ubicacion = torre.get("ubicacion", {})
        estado = torre.get("estado", "Desconocido")
        lat = ubicacion.get("lat", "N/A")
        lon = ubicacion.get("lon", "N/A")

        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"**{nombre}** - Estado: {estado}")
            st.write(f"Ubicación: lat {lat}, lon {lon}")
        with col2:
            if st.button("✏️ Editar", key=f"edit_{torre['id_torre']}"):
                st.session_state["modo_edicion"] = True
                st.session_state["torre_editando"] = torre
                st.rerun()

        with col3:
            if st.button("🗑️ Eliminar", key=f"delete_{torre['id_torre']}"):
                supabase.table("torres").delete().eq("id_torre", torre["id_torre"]).execute()
                st.success(f"Torre '{nombre}' eliminada.")
                st.rerun()

        st.markdown("---")

# obtener torres
def obtener_torres():
    res = supabase.table("torres").select("id_torre,nombre").execute()
    if res.data:
        return {t["nombre"]: t["id_torre"] for t in res.data}
    return {}

# obtener datos
def obtener_datos(id_torre):
    res = supabase.table("datos_meteorologicos")\
        .select("*")\
        .eq("id_torre", id_torre)\
        .order("fecha", desc=False)\
        .limit(100)\
        .execute()
    if res.data:
        return pd.DataFrame(res.data)
    return pd.DataFrame()


def mostrar_estado_tecnico():
    st.header("Estado Técnico de las Torres")

    torres = obtener_torres()
    if not torres:
        st.warning("No hay torres registradas.")
        return

    torre_nombre = st.selectbox("Selecciona una torre:", list(torres.keys()), key="selectbox_realtime")
    id_torre = torres[torre_nombre]

    # Insertar nuevo registro automáticamente 
    nuevo_registro = {
        "id_torre": id_torre,
        "nivel_bateria": round(random.uniform(3.5, 4.2), 2),
        "tiempo_ultima_conexion": datetime.now().isoformat(),
        "estado_sensor_temperatura": random.choice(["OK", "Error"]),
        "estado_sensor_humedad": random.choice(["OK", "Error"]),
        "estado_general": random.choice(["Normal", "Alerta", "Crítico"])
    }

    insert_res = supabase.table("diagnostico_torre").insert(nuevo_registro).execute()


    
    res = supabase.table("diagnostico_torre")\
        .select("*")\
        .eq("id_torre", id_torre)\
        .order("id", desc=True)\
        .limit(10)\
        .execute()

    if res.data:
        df = pd.DataFrame(res.data)
        st.dataframe(df)
    else:
        st.info("No hay registros técnicos aún.")

   
    time.sleep(10)
    st.rerun()

# simular datos
def simular_datos(id_torre, stop_event):
    contador = 1
    while not stop_event.is_set():
        data = {
            "id_torre": id_torre,
            "temperatura": round(random.uniform(15, 35), 2),
            "humedad_relativa": round(random.uniform(30, 90), 2),
            "presion_atmosferica": round(random.uniform(980, 1050), 2),
            "velocidad_viento": round(random.uniform(0, 50), 2),
            "direccion_viento": random.randint(0, 360),
            "precipitacion": round(random.uniform(0, 10), 2),
            "radiacion_solar": round(random.uniform(0, 1000), 2),
            "indice_uv": random.randint(0, 11),
            "fecha": datetime.utcnow().isoformat()
        }
        supabase.table("datos_meteorologicos").insert(data).execute()
        time.sleep(60)  

        if contador % 5 == 0: 
            simular_estado_tecnico(id_torre)
        contador += 1
       



# hilos
stop_threads = {}

def iniciar_simulacion(id_torre):
    if id_torre in stop_threads:
        st.warning("Simulación ya activa.")
        return
    stop_event = threading.Event()
    hilo = threading.Thread(target=simular_datos, args=(id_torre, stop_event), daemon=True)
    hilo.start()
    stop_threads[id_torre] = (hilo, stop_event)
    st.success("Simulación iniciada.")

def detener_simulacion(id_torre):
    if id_torre in stop_threads:
        hilo, stop_event = stop_threads.pop(id_torre)
        stop_event.set()
        st.success("Simulación detenida.")
    else:
        st.warning("No hay simulación activa.")


def simulacion_page():
    st.header("Simulación de Datos Meteorológicos")
    torres = obtener_torres()
    if not torres:
        st.warning("No hay torres registradas.")
        return

    torre_nombre = st.selectbox("Selecciona torre:", list(torres.keys()))
    id_torre = torres[torre_nombre]

    if st.button("Iniciar Simulación"):
        iniciar_simulacion(id_torre)
    if st.button("Detener Simulación"):
        detener_simulacion(id_torre)


def mostrar_datos_realtime():
    st.header("Visualización en Tiempo Real")
    st_autorefresh(interval=60 * 1000, key="refresh")

    torres = obtener_torres()
    if not torres:
        st.warning("No hay torres.")
        return

    torre_nombre = st.selectbox("Selecciona una torre:", list(torres.keys()))
    id_torre = torres[torre_nombre]
    df = obtener_datos(id_torre)

    if df.empty:
        st.warning("No hay datos aún.")
        return

    
    opciones = {
        "Temperatura": "temperatura",
        "Humedad": "humedad_relativa",
        "Presión": "presion_atmosferica",
        "Velocidad Viento": "velocidad_viento"
    }

    seleccion = st.multiselect("Selecciona los datos a mostrar:", opciones.keys(), default=list(opciones.keys()))

    if not seleccion:
        st.warning("Selecciona al menos un parámetro para mostrar.")
        return

    fig = go.Figure()
    colores = {
        "Temperatura": "red",
        "Humedad": "blue",
        "Presión": "green",
        "Velocidad Viento": "orange"
    }

    for nombre_param in seleccion:
        col = opciones[nombre_param]
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["fecha"],
                y=df[col],
                mode="lines+markers",
                name=f"{nombre_param}",
                line=dict(color=colores.get(nombre_param, "black"))
            ))

    fig.update_layout(
        title=f"Datos meteorológicos de {torre_nombre}",
        xaxis_title="Fecha",
        yaxis_title="Valor",
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)

def mostrar_graficas_todas_torres():
    st.header("Visualización Comparativa de Todas las Torres")

    torres = obtener_torres()
    if not torres:
        st.warning("No hay torres registradas.")
        return

   
    opciones = {
        "Temperatura": "temperatura",
        "Humedad": "humedad_relativa",
        "Presión": "presion_atmosferica",
        "Velocidad Viento": "velocidad_viento"
    }

    parametro_seleccionado = st.selectbox("Selecciona parámetro a graficar:", list(opciones.keys()))
    campo = opciones[parametro_seleccionado]

    fig = go.Figure()

    for nombre_torre, id_torre in torres.items():
        df = obtener_datos(id_torre)
        if not df.empty and campo in df.columns:
            fig.add_trace(go.Scatter(
                x=df["fecha"],
                y=df[campo],
                mode="lines+markers",
                name=nombre_torre
            ))

    fig.update_layout(
        title=f"{parametro_seleccionado} - Todas las Torres",
        xaxis_title="Fecha",
        yaxis_title=parametro_seleccionado,
        height=600
    )

    st.plotly_chart(fig, use_container_width=True)

def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    output.seek(0)
    return output

# generar pdf
def generar_pdf(df, titulo="Reporte de Torre"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, titulo, ln=True, align='C')

   
    col_width = pdf.w / (len(df.columns) + 1)
    row_height = pdf.font_size * 1.5
    pdf.set_font("Arial", size=8)


    for col in df.columns:
        pdf.cell(col_width, row_height, str(col), border=1)
    pdf.ln(row_height)

  
    for i, row in df.iterrows():
        if i > 30:  
            pdf.cell(0, row_height, "... y más filas ...", ln=True)
            break
        for item in row:
            pdf.cell(col_width, row_height, str(item), border=1)
        pdf.ln(row_height)

    return pdf.output(dest='S').encode('latin1')


def generar_imagen(df):
    fig = go.Figure()
    for col in df.columns:
        if col != "fecha":
            fig.add_trace(go.Scatter(x=df["fecha"], y=df[col], mode='lines+markers', name=col))
    fig.update_layout(title="Datos meteorológicos", xaxis_title="Fecha", yaxis_title="Valor")
    img_bytes = fig.to_image(format="png")
    return img_bytes

def subir_excel_y_guardar():
    st.header("Subir archivo Excel con datos históricos")

    uploaded_file = st.file_uploader("Selecciona un archivo Excel (.xlsx, .xls)", type=["xlsx", "xls"])

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.success("Archivo cargado correctamente")
            st.dataframe(df)

            if st.button("Guardar datos en la base de datos"):
                errores = []
                for i, row in df.iterrows():
                    try:
                        data = {
                            "id_torre": int(row["id_torre"]), 
                            "temperatura": float(row["temperatura"]),
                            "humedad_relativa": float(row["humedad_relativa"]),
                            "presion_atmosferica": float(row.get("presion_atmosferica", 0)),
                            "velocidad_viento": float(row.get("velocidad_viento", 0)),
                            "direccion_viento": int(row.get("direccion_viento", 0)),
                            "precipitacion": float(row.get("precipitacion", 0)),
                            "radiacion_solar": float(row.get("radiacion_solar", 0)),
                            "indice_uv": int(row.get("indice_uv", 0)),
                            "fecha": pd.to_datetime(row["fecha"]).isoformat() if not pd.isnull(row["fecha"]) else None,
                        }
                        supabase.table("datos_meteorologicos").insert(data).execute()
                    except Exception as e:
                        errores.append(f"Fila {i+1}: {e}")

                if errores:
                    st.error("Algunos errores al guardar datos:")
                    for err in errores:
                        st.write(err)
                else:
                    st.success("Todos los datos guardados correctamente!")

        except Exception as e:
            st.error(f"Error leyendo el archivo Excel: {e}")

def simular_estado_tecnico(id_torre):
    nivel_bateria = round(random.uniform(10, 100), 2)
    tiempo_ultima_conexion = datetime.utcnow() - pd.to_timedelta(random.randint(0, 10), unit="m")

    estado_sensor_temperatura = random.choice(["OK", "Error"])
    estado_sensor_humedad = random.choice(["OK", "Error"])

    if nivel_bateria < 20 or "Error" in (estado_sensor_temperatura, estado_sensor_humedad):
        estado_general = random.choice(["Alerta", "Crítico"])
    else:
        estado_general = "Normal"

    estado = {
        "id_torre": id_torre,
        "nivel_bateria": nivel_bateria,
        "tiempo_ultima_conexion": tiempo_ultima_conexion.isoformat(),
        "estado_sensor_temperatura": estado_sensor_temperatura,
        "estado_sensor_humedad": estado_sensor_humedad,
        "estado_general": estado_general,
        "fecha": datetime.utcnow().isoformat()
    }

    supabase.table("estado_tecnico").insert(estado).execute()



def descargar_reportes():
    st.header("Descargar Reportes")

 
    torres = obtener_torres() 
    opciones = st.multiselect("Selecciona una o varias torres", options=list(torres.keys()))

    if not opciones:
        st.info("Selecciona al menos una torre para descargar reporte.")
        return

    
    dfs = []
    for nombre in opciones:
        id_torre = torres[nombre]
        df = obtener_datos(id_torre)
        if not df.empty:
            df["torre"] = nombre  
            dfs.append(df)
    if not dfs:
        st.warning("No hay datos para las torres seleccionadas.")
        return

    df_all = pd.concat(dfs).reset_index(drop=True)

  
    formato = st.radio("Selecciona formato de reporte:", ["Excel", "PDF", "Imagen (PNG)"])

    if st.button("Generar y Descargar Reporte"):
        if formato == "Excel":
            excel_bytes = generar_excel(df_all)
            st.download_button("Descargar Excel", excel_bytes, file_name="reporte_torres.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif formato == "PDF":
            pdf_bytes = generar_pdf(df_all)
            st.download_button("Descargar PDF", pdf_bytes, file_name="reporte_torres.pdf", mime="application/pdf")
        elif formato == "Imagen (PNG)":
            img_bytes = generar_imagen(df_all)
            st.download_button("Descargar Imagen PNG", img_bytes, file_name="grafica_torres.png", mime="image/png")


def dashboard_envio():
    st.title("Enviar comando a torre")
    torre_id = st.text_input("ID de torre")
    comando = st.text_input("Comando (ej. reiniciar)")

    if st.button("Enviar"):
        res = requests.post(f"http://localhost:8000/enviar_comando/{torre_id}", json={"comando": comando})
        st.write(res.json())


def main():
    st.title("🌩️ Simulador de Torres Meteorológicas")
    tabs = st.tabs(["Crear Torre", "Visualizar Datos", "Simulacion", "Torres", "Reportes","Importar Excel", "Datos tecnicos"])

    # tabs
    with tabs[0]:
        crear_torre()
    with tabs[1]:
        mostrar_datos_realtime()
    with tabs[2]:
        simulacion_page()
    with tabs[3]:
        mostrar_graficas_todas_torres()
    with tabs[4]:
        descargar_reportes()
    with tabs[5]:
        subir_excel_y_guardar()
    with tabs[6]:
        mostrar_estado_tecnico()

if __name__ == "__main__":
    main()