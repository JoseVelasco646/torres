import nest_asyncio
nest_asyncio.apply()

import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client
import unicodedata

SUPABASE_URL = "https://wkimchzmykvcofvprfat.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraW1jaHpteWt2Y29mdnByZmF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgwMjQ4ODgsImV4cCI6MjA2MzYwMDg4OH0.O84iGohEv1kgLZFoUaQun-SoFGO2XaDWHYJCsudYArQ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

CHAT_ID_ALERTAS = 6881353872  

async def listar_torres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = supabase.table("torres").select("id_torre, nombre").execute()
    if not res.data:
        await update.message.reply_text("No hay torres registradas.")
        return
    
    mensaje = "📋 *Lista de torres disponibles:*\n\n"
    for torre in res.data:
        mensaje += f"- {torre['nombre']} (`{torre['id_torre']}`)\n"

    await update.message.reply_markdown(mensaje)



def normalizar(texto):
    if not texto:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    ).lower().strip()


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Por favor, indica el ID de la torre: /estado <id_torre>")
        return

    id_torre = context.args[0]

    # Buscar nombre de la torre
    res_torre = supabase.table("torres").select("nombre").eq("id_torre", id_torre).execute()
    if not res_torre.data:
        await update.message.reply_text(f"No se encontró ninguna torre con ID {id_torre}")
        return

    nombre_torre = res_torre.data[0]["nombre"]

    
    res_estado = supabase.table("diagnostico_torre")\
        .select("*")\
        .eq("id_torre", id_torre)\
        .order("tiempo_ultima_conexion", desc=True)\
        .limit(1)\
        .execute()

    if not res_estado.data:
        await update.message.reply_text(f"No hay registros de estado para la torre {nombre_torre}.")
        return

    data = res_estado.data[0]


    bateria = data.get("nivel_bateria", "N/A")
    temperatura = data.get("estado_sensor_temperatura", "N/A")
    humedad = data.get("estado_sensor_humedad", "N/A")
    ultima_conexion = data.get("tiempo_ultima_conexion", "N/A")
    estado_general = data.get("estado_general", "N/A")

    mensaje = (
        f"📡 *Estado actual de la torre {nombre_torre}*\n\n"
        f"🔋 *Batería:* {bateria}%\n"
        f"🌡️ *Temperatura:* {temperatura}°C\n"
        f"💧 *Humedad:* {humedad}%\n"
        f"🕐 *Última conexión:* `{ultima_conexion}`\n"
        f"📊 *Estado general:* *{estado_general.upper()}*"
    )

    await update.message.reply_markdown(mensaje)


alertas_enviadas = set()  

async def revisar_alertas(app):
    while True:
        res = supabase.table("diagnostico_torre")\
            .select("*")\
            .order("tiempo_ultima_conexion", desc=True)\
            .limit(100)\
            .execute()

        if res.data:
            estados_por_torre = {}

            for data in res.data:
                torre_id = data.get("id_torre")
                if torre_id not in estados_por_torre:
                    estados_por_torre[torre_id] = data

            for torre_id, data in estados_por_torre.items():
                estado_original = data.get("estado_general", "")
                estado_general = normalizar(estado_original)

                if not torre_id or estado_general not in ("alerta", "critico"):
                    if torre_id and estado_general == "normal":
                        alertas_enviadas.discard((torre_id, "alerta"))
                        alertas_enviadas.discard((torre_id, "critico"))
                    continue

                if (torre_id, estado_general) in alertas_enviadas:
                    continue

                nombre_torre = "desconocida"
                res_torre = supabase.table("torres").select("nombre").eq("id_torre", torre_id).execute()
                if res_torre.data:
                    nombre_torre = res_torre.data[0]["nombre"]

                mensaje = (
                    f"🚨 *Alerta en torre {nombre_torre}*\n\n"
                    f"📊 *Estado general:* *{estado_original.upper()}*"
                )

                try:
                    await app.bot.send_message(
                        chat_id=CHAT_ID_ALERTAS,
                        text=mensaje,
                        parse_mode="Markdown"
                    )
                    print(f"✅ Alerta enviada: Torre {torre_id} - Estado: {estado_original}")
                    alertas_enviadas.add((torre_id, estado_general))
                except Exception as e:
                    print(f"❌ Error al enviar alerta: {e}")

        await asyncio.sleep(60)



async def main():
    app = ApplicationBuilder().token("7240197388:AAG2ylVUhpePMIOIVhAa_WLrntZDJ0hrnLY").build()
    app.add_handler(CommandHandler("listartorres", listar_torres))
    app.add_handler(CommandHandler("estado", estado))
    asyncio.create_task(revisar_alertas(app))
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    import asyncio
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.create_task(main())
            loop.run_forever()
        else:
            asyncio.run(main())
    except RuntimeError:
        asyncio.run(main())
