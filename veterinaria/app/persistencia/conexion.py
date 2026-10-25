"""Conexión a la base SQLite implementada con el patrón Singleton.

Toda la aplicación comparte una única conexión. Las operaciones se agrupan con
`transaccion()`, que es reentrante: solo la transacción más externa confirma (commit)
o deshace (rollback), de modo que un servicio puede combinar varias operaciones de
distintos DAO en una sola unidad atómica.
"""
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from app import config
from app.dominio.excepciones import ErrorPersistencia


class ConexionBD:
    _instancia = None
    _inicializada = False

    def __new__(cls, ruta_bd: str | Path | None = None):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
        return cls._instancia

    def __init__(self, ruta_bd: str | Path | None = None):
        if ConexionBD._inicializada:
            return
        self._ruta = str(ruta_bd or config.RUTA_BD)
        if self._ruta != ":memory:":
            Path(self._ruta).parent.mkdir(parents=True, exist_ok=True)
        # La interfaz puede atender eventos en hilos distintos: se comparte la conexión protegida por un lock
        self._conexion = sqlite3.connect(self._ruta, check_same_thread=False)
        self._conexion.row_factory = sqlite3.Row
        self._conexion.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        self._profundidad = 0
        ConexionBD._inicializada = True

    @classmethod
    def obtener_instancia(cls) -> "ConexionBD":
        return cls()

    @classmethod
    def reiniciar(cls) -> None:
        """Cierra la conexión y descarta la instancia (se usa en las pruebas para cambiar de base)."""
        if cls._instancia is not None and cls._inicializada:
            cls._instancia._conexion.close()
        cls._instancia = None
        cls._inicializada = False

    @property
    def ruta(self) -> str:
        return self._ruta

    @contextmanager
    def transaccion(self):
        with self._lock:
            self._profundidad += 1
            try:
                yield self._conexion
                if self._profundidad == 1:
                    self._conexion.commit()
            except sqlite3.Error as error:
                if self._profundidad == 1:
                    self._conexion.rollback()
                raise ErrorPersistencia(traducir_error(error)) from error
            except Exception:
                if self._profundidad == 1:
                    self._conexion.rollback()
                raise
            finally:
                self._profundidad -= 1

    def ejecutar(self, sql: str, parametros: tuple | dict = ()) -> sqlite3.Cursor:
        with self.transaccion() as conexion:
            return conexion.execute(sql, parametros)

    def ejecutar_muchos(self, sql: str, filas: list[tuple]) -> None:
        with self.transaccion() as conexion:
            conexion.executemany(sql, filas)

    def ejecutar_script(self, script: str) -> None:
        with self._lock:
            self._conexion.executescript(script)

    def consultar(self, sql: str, parametros: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conexion.execute(sql, parametros).fetchall()

    def consultar_uno(self, sql: str, parametros: tuple | dict = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conexion.execute(sql, parametros).fetchone()

    def valor(self, sql: str, parametros: tuple | dict = ()):
        fila = self.consultar_uno(sql, parametros)
        return None if fila is None else fila[0]

    def cerrar(self) -> None:
        with self._lock:
            self._conexion.close()


_RESTRICCION_UNICA = re.compile(r"UNIQUE constraint failed: (\w+)\.(\w+)")


def traducir_error(error: sqlite3.Error) -> str:
    """Convierte los mensajes técnicos de SQLite en mensajes comprensibles para el usuario."""
    mensaje = str(error)
    if (coincidencia := _RESTRICCION_UNICA.search(mensaje)):
        tabla, columna = coincidencia.groups()
        return f"Ya existe un registro de {tabla.replace('_', ' ')} con ese valor de {columna.replace('_', ' ')}."
    if "FOREIGN KEY constraint failed" in mensaje:
        return "La operación no es posible: el registro está relacionado con otros datos."
    if "CHECK constraint failed" in mensaje:
        return f"Los datos no cumplen una regla de validación de la base ({mensaje.split(':')[-1].strip()})."
    if "NOT NULL constraint failed" in mensaje:
        return f"Falta un dato obligatorio ({mensaje.split(':')[-1].strip()})."
    return mensaje  # mensajes de los triggers (RAISE ABORT) ya están redactados para el usuario
