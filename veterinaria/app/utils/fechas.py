"""Conversión de fechas entre Python, SQLite (texto ISO) y la interfaz (dd/mm/aaaa)."""
from datetime import date, datetime

FORMATO_FECHA = "%d/%m/%Y"
FORMATO_FECHA_HORA = "%d/%m/%Y %H:%M"
FORMATO_SQL_FECHA = "%Y-%m-%d"
FORMATO_SQL_FECHA_HORA = "%Y-%m-%d %H:%M:%S"


# --- SQLite ------------------------------------------------------------------
def a_sql(valor: date | datetime | None) -> str | None:
    """Convierte una fecha u hora a texto ISO, el formato que entiende date()/datetime() de SQLite."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.strftime(FORMATO_SQL_FECHA_HORA)
    return valor.strftime(FORMATO_SQL_FECHA)


def fecha_desde_sql(texto: str | None) -> date | None:
    return date.fromisoformat(texto[:10]) if texto else None


def fecha_hora_desde_sql(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


# --- Interfaz ----------------------------------------------------------------
def formatear_fecha(valor: date | None) -> str:
    return valor.strftime(FORMATO_FECHA) if valor else ""


def formatear_fecha_hora(valor: datetime | None) -> str:
    return valor.strftime(FORMATO_FECHA_HORA) if valor else ""


def parsear_fecha(texto: str | None) -> date | None:
    """Interpreta 'dd/mm/aaaa'. Devuelve None si el texto está vacío; ValueError si es inválido."""
    texto = (texto or "").strip()
    if not texto:
        return None
    return datetime.strptime(texto, FORMATO_FECHA).date()


def parsear_fecha_hora(texto: str | None) -> datetime | None:
    """Interpreta 'dd/mm/aaaa hh:mm'. Devuelve None si el texto está vacío; ValueError si es inválido."""
    texto = (texto or "").strip()
    if not texto:
        return None
    return datetime.strptime(texto, FORMATO_FECHA_HORA)


def ahora() -> datetime:
    """Fecha y hora actual sin microsegundos (así se guarda en la base)."""
    return datetime.now().replace(microsecond=0)


def horas_entre(desde: datetime, hasta: datetime) -> float:
    return (hasta - desde).total_seconds() / 3600


def edad_legible(nacimiento: date | None, fecha: date | None = None) -> str:
    """'6 sem.', '14 meses' o '7 años' según la edad a la fecha indicada (hoy por defecto)."""
    if nacimiento is None:
        return "—"
    fecha = fecha or date.today()
    meses = (fecha.year - nacimiento.year) * 12 + fecha.month - nacimiento.month - (fecha.day < nacimiento.day)
    if meses < 1:
        return f"{(fecha - nacimiento).days // 7} sem."
    return f"{meses} meses" if meses < 24 else f"{meses // 12} años"
