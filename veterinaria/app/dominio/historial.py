"""Trazabilidad inmutable de estados de la muestra (patrón Iterator).

CambioEstado es inmutable (dataclass frozen) y HistorialEstados solo permite agregar cambios:
no ofrece operaciones para modificarlos ni eliminarlos.
"""
from dataclasses import dataclass
from datetime import datetime

from app.dominio.excepciones import ValidacionError


@dataclass(frozen=True)
class CambioEstado:
    fecha_hora: datetime
    estado_anterior: str | None
    estado_nuevo: str
    responsable: str
    observacion: str | None = None


class IteradorHistorial:
    """Iterador explícito sobre una copia inmutable (tupla) de los cambios."""

    def __init__(self, cambios: tuple[CambioEstado, ...]):
        self._cambios = cambios
        self._indice = 0

    def __iter__(self) -> "IteradorHistorial":
        return self

    def __next__(self) -> CambioEstado:
        if self._indice >= len(self._cambios):
            raise StopIteration
        cambio = self._cambios[self._indice]
        self._indice += 1
        return cambio


class HistorialEstados:
    """Colección append-only de cambios de estado, ordenada cronológicamente."""

    def __init__(self, cambios: list[CambioEstado] | None = None):
        self._cambios: list[CambioEstado] = []
        for cambio in cambios or []:
            self.registrar(cambio)

    def registrar(self, cambio: CambioEstado) -> None:
        ultimo = self.ultimo()
        if ultimo is not None:
            if cambio.fecha_hora < ultimo.fecha_hora:
                raise ValidacionError("Un cambio de estado no puede ser anterior al último registrado.")
            if cambio.estado_anterior != ultimo.estado_nuevo:
                raise ValidacionError("El cambio de estado no parte del estado actual de la muestra.")
        self._cambios.append(cambio)

    def ultimo(self) -> CambioEstado | None:
        return self._cambios[-1] if self._cambios else None

    def primer_cambio_a(self, estado: str) -> CambioEstado | None:
        return next((c for c in self if c.estado_nuevo == estado), None)

    def __len__(self) -> int:
        return len(self._cambios)

    def __iter__(self) -> IteradorHistorial:
        return IteradorHistorial(tuple(self._cambios))
