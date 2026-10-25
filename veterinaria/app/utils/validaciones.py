"""Validación declarativa: cada regla es un par (función lambda, mensaje de error)."""
import re
from collections.abc import Callable, Iterable

from app.dominio.excepciones import ValidacionError

Regla = tuple[Callable[[object], bool], str]

_PATRON_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
_PATRON_CUIT = re.compile(r"^\d{2}-?\d{8}-?\d$")


def validar(objeto, reglas: Iterable[Regla]) -> None:
    """Evalúa todas las reglas y lanza ValidacionError con los mensajes de las que fallan."""
    errores = [mensaje for regla, mensaje in reglas if not regla(objeto)]
    if errores:
        raise ValidacionError(errores)


def texto_requerido(valor: str | None) -> bool:
    return bool((valor or "").strip())


def es_email(valor: str | None) -> bool:
    """Vacío es válido (campo opcional); si hay texto debe tener formato de email."""
    return not valor or bool(_PATRON_EMAIL.match(valor.strip()))


def es_dni(valor: str | None) -> bool:
    valor = (valor or "").strip()
    return valor.isdigit() and 7 <= len(valor) <= 8


def es_cuit(valor: str | None) -> bool:
    return bool(_PATRON_CUIT.match((valor or "").strip()))


def es_telefono(valor: str | None) -> bool:
    return not valor or bool(re.fullmatch(r"[\d\s()+-]{6,20}", valor.strip()))


def positivo_u_omitido(valor: float | None) -> bool:
    return valor is None or valor > 0
