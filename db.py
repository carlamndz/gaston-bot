"""
Memoria de Gastón: historial de conversación en SQLite.

Cada mensaje (del usuario o del modelo) se guarda como una fila de la tabla
`mensajes`. Se usa aiosqlite, la versión asíncrona de sqlite3, para que las
operaciones sobre la base no bloqueen al bot mientras atiende a otros usuarios.
"""

import aiosqlite

# Archivo de la base. Se crea en la carpeta desde la que se ejecuta el bot.
# Está excluido del repositorio por .gitignore (*.db).
RUTA_DB = "gaston.db"

# IF NOT EXISTS permite ejecutar el esquema en cada arranque sin error.
ESQUEMA = """
CREATE TABLE IF NOT EXISTS mensajes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    rol      TEXT    NOT NULL CHECK (rol IN ('user', 'model')),
    texto    TEXT    NOT NULL,
    fecha    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mensajes_usuario ON mensajes (user_id, id);
"""


async def inicializar() -> None:
    """Crea la tabla y el índice si todavía no existen."""
    async with aiosqlite.connect(RUTA_DB) as db:
        await db.executescript(ESQUEMA)
        await db.commit()


async def guardar_intercambio(user_id: int, pregunta: str, respuesta: str) -> None:
    """Guarda en una sola operación el mensaje del usuario y la respuesta del modelo."""
    async with aiosqlite.connect(RUTA_DB) as db:
        # Los signos ? son parámetros: evitan la inyección de SQL.
        await db.executemany(
            "INSERT INTO mensajes (user_id, rol, texto) VALUES (?, ?, ?)",
            [(user_id, "user", pregunta),
             (user_id, "model", respuesta)],
        )
        await db.commit()


async def obtener_historial(user_id: int, limite: int) -> list[tuple[str, str]]:
    """Devuelve los últimos `limite` mensajes del usuario, del más antiguo al más reciente."""
    async with aiosqlite.connect(RUTA_DB) as db:
        # DESC + LIMIT trae los últimos mensajes, del más reciente al más antiguo.
        cursor = await db.execute(
            "SELECT rol, texto FROM mensajes WHERE user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, limite),
        )
        filas = await cursor.fetchall()

    # El modelo tiene que leer la conversación en orden cronológico.
    return list(reversed(filas))


async def borrar_historial(user_id: int) -> int:
    """Borra la conversación de un usuario y devuelve cuántos mensajes eliminó."""
    async with aiosqlite.connect(RUTA_DB) as db:
        cursor = await db.execute("DELETE FROM mensajes WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount
