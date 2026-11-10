"""
Gastón v3: asistente de finanzas personales en Telegram.

- Responde con Gemini mediante la Interactions API sin estado (store=False).
- Guarda el historial de cada usuario en SQLite (db.py) y lo reenvía en cada consulta.
- /olvidar borra la conversación del usuario.
"""

import logging
import os

from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
from prompts import PROMPT_SISTEMA

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# El modelo se lee del .env para poder cambiarlo sin tocar el código.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Cantidad de mensajes anteriores que se envían en cada consulta
# (20 mensajes = 10 preguntas y sus respuestas).
MAX_MENSAJES_HISTORIAL = 20

# Longitud máxima de un mensaje de Telegram, en caracteres.
LIMITE_TELEGRAM = 4096

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("gaston")

# Un único cliente para todo el programa.
cliente_gemini = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Conexión con Gemini
# ---------------------------------------------------------------------------

def armar_entrada(historial: list[tuple[str, str]], mensaje_nuevo: str) -> list[dict]:
    """Convierte el historial en la lista de pasos que espera la Interactions API
    y agrega al final el mensaje nuevo del usuario."""
    tipo_de_paso = {"user": "user_input", "model": "model_output"}

    pasos = [
        {"type": tipo_de_paso[rol], "content": [{"type": "text", "text": texto}]}
        for rol, texto in historial
    ]
    pasos.append({"type": "user_input", "content": [{"type": "text", "text": mensaje_nuevo}]})
    return pasos


async def consultar_gemini(historial: list[tuple[str, str]], mensaje: str) -> str:
    """Envía a Gemini la conversación completa y devuelve el texto de la respuesta."""
    interaccion = await cliente_gemini.aio.interactions.create(
        model=GEMINI_MODEL,
        system_instruction=PROMPT_SISTEMA,
        input=armar_entrada(historial, mensaje),
        store=False,  # la memoria la administra el bot, no Google
    )
    return interaccion.output_text or "No se me ocurrió nada para responder 🤔"


def describir_error(error: Exception) -> str:
    """Traduce un error de la API a un mensaje comprensible para el usuario."""
    codigo = getattr(error, "status_code", None)
    if codigo == 429:
        return "Estoy recibiendo demasiadas consultas. Probá de nuevo en un minuto, por favor. ⏳"
    if codigo in (401, 403):
        return "Tengo un problema de configuración. Avisale a quien me administra. 🔧"
    return "Tuve un problema para pensar la respuesta. ¿Me lo preguntás de nuevo? 🙏"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /start."""
    nombre = update.effective_user.first_name
    logger.info("Nuevo /start de %s (id %s)", nombre, update.effective_user.id)
    await update.message.reply_text(
        f"¡Hola, {nombre}! Soy Gastón 💸, tu asistente de finanzas personales.\n\n"
        "Te ayudo a armar un presupuesto, ordenar tus gastos y pensar cómo ahorrar. "
        "Contame cuánto cobrás, en qué se te va la plata o qué querés lograr, y lo vemos juntos.\n\n"
        "No me mandes datos sensibles como claves, CBU o tu DNI: no los necesito.\n\n"
        "Escribí /help para ver lo que sé hacer."
    )


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /help."""
    await update.message.reply_text(
        "Estos son mis comandos:\n\n"
        "/start - Presentación de Gastón\n"
        "/help - Esta ayuda\n"
        "/olvidar - Borra nuestra conversación y empezamos de cero\n\n"
        "Y, sobre todo, podés escribirme lo que quieras sobre tus finanzas personales. "
        "Me acuerdo de lo que hablamos."
    )


async def olvidar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /olvidar: borra el historial del usuario."""
    borrados = await db.borrar_historial(update.effective_user.id)
    logger.info("Usuario %s borró %d mensajes", update.effective_user.id, borrados)
    await update.message.reply_text("Listo, empezamos de cero. ¿En qué te ayudo? 🙂")


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde con Gemini, teniendo en cuenta la conversación previa."""
    user_id = update.effective_user.id
    texto = update.message.text
    logger.info("Mensaje de %s: %s", user_id, texto)

    await update.message.chat.send_action(ChatAction.TYPING)

    # Paso 1: recuperar lo que ya se habló con este usuario.
    historial = await db.obtener_historial(user_id, MAX_MENSAJES_HISTORIAL)

    # Paso 2: consultar al modelo con el historial más el mensaje nuevo.
    try:
        respuesta = await consultar_gemini(historial, texto)
    except Exception as error:
        logger.exception("Error al consultar a Gemini")
        await update.message.reply_text(describir_error(error))
        # Si la consulta falló no se guarda nada: el historial nunca
        # queda con una pregunta sin respuesta.
        return

    # Paso 3: guardar la pregunta y la respuesta para la próxima consulta.
    await db.guardar_intercambio(user_id, texto, respuesta)

    # Si la respuesta supera el límite de Telegram, se envía en partes.
    for inicio in range(0, len(respuesta), LIMITE_TELEGRAM):
        await update.message.reply_text(respuesta[inicio:inicio + LIMITE_TELEGRAM])


async def manejar_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra los errores no previstos para que el bot no se caiga."""
    logger.error("Error no manejado", exc_info=context.error)


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------

async def al_iniciar(app: Application) -> None:
    """Se ejecuta una sola vez, antes de recibir mensajes."""
    await db.inicializar()
    logger.info("Base de datos lista (%s).", db.RUTA_DB)


def main() -> None:
    faltantes = [nombre for nombre, valor in [("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
                                              ("GEMINI_API_KEY", GEMINI_API_KEY)]
                 if not valor]
    if faltantes:
        raise SystemExit(f"Faltan variables en el .env: {', '.join(faltantes)}")

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(al_iniciar).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", ayuda))
    app.add_handler(CommandHandler("olvidar", olvidar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.add_error_handler(manejar_error)

    logger.info("Gastón v3 en línea con el modelo %s.", GEMINI_MODEL)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
