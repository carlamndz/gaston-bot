# Gastón · Bot de finanzas personales

Proyecto del Grupo 6 para Sistemas Inteligentes Aplicados (ITU UNCuyo).
Integrantes: Fernando Navarro, Lucas Olarte, Agustina Zartmann y Carla Méndez.

Gastón es un bot de Telegram que ayuda a jóvenes y estudiantes a ordenar sus gastos y pensar cómo ahorrar. Responde con Gemini y recuerda la conversación de cada usuario.

## Versión actual: v3

- Respuestas generadas con Gemini mediante la Interactions API sin estado (`store=False`).
- Historial de cada usuario guardado en SQLite (`gaston.db`) y reenviado en cada consulta (últimos 20 mensajes).
- Comando `/olvidar` para borrar la conversación.

## Archivos

| Archivo | Contenido |
| --- | --- |
| `bot.py` | Handlers de Telegram, consulta a Gemini y arranque |
| `prompts.py` | Prompt de sistema: identidad, tarea y alcance, estilo, formato y honestidad |
| `db.py` | Acceso a la base SQLite |
| `.env.example` | Variables necesarias, sin valores |

## Cómo ejecutarlo

1. Crear el entorno e instalar las dependencias:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copiar `.env.example` como `.env` y completar `TELEGRAM_TOKEN` (BotFather) y `GEMINI_API_KEY` (Google AI Studio).
3. Ejecutar `python bot.py` desde la carpeta del proyecto.

El `.env` y los archivos `.db` no se suben al repositorio.

## Comandos

- `/start` - Presentación de Gastón
- `/help` - Lista de comandos
- `/olvidar` - Borrar la conversación
