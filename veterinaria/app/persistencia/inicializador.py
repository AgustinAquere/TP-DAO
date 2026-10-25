"""Crea el esquema de la base (schema.sql del DER) si todavía no existe."""
from app import config
from app.persistencia.conexion import ConexionBD


def esquema_creado(conexion: ConexionBD) -> bool:
    return conexion.valor("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'cliente'") == 1


def crear_esquema(conexion: ConexionBD | None = None) -> bool:
    """Ejecuta schema.sql en una base vacía. Devuelve True si creó el esquema."""
    conexion = conexion or ConexionBD.obtener_instancia()
    if esquema_creado(conexion):
        return False
    conexion.ejecutar_script(config.RUTA_ESQUEMA.read_text(encoding="utf-8"))
    return True


def base_vacia(conexion: ConexionBD | None = None) -> bool:
    conexion = conexion or ConexionBD.obtener_instancia()
    return conexion.valor("SELECT COUNT(*) FROM clinica") == 0
