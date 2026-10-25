"""Patrón Strategy: cálculo del total del comprobante según el tipo de atención."""
from abc import ABC, abstractmethod
from datetime import datetime
from functools import reduce

from app import config
from app.dominio.enums import TipoItem


def subtotal(items) -> float:
    return round(reduce(lambda acumulado, item: acumulado + item.importe(), items, 0.0), 2)


def subtotal_por_tipo(items, tipo: TipoItem) -> float:
    return subtotal(filter(lambda item: item.tipo == tipo, items))


class EstrategiaTarifa(ABC):
    @abstractmethod
    def nombre(self) -> str:
        """Nombre con el que se registra la estrategia en el comprobante (CONSULTA / CONTROL / URGENCIA)."""

    @abstractmethod
    def calcular_total(self, items) -> float:
        """Total a cobrar para los ítems del comprobante."""

    @abstractmethod
    def descripcion(self) -> str:
        """Explicación breve de la regla aplicada (se muestra al facturar)."""


class TarifaConsulta(EstrategiaTarifa):
    """Consulta: se cobra el precio de lista de cada ítem."""

    def nombre(self) -> str:
        return "CONSULTA"

    def calcular_total(self, items) -> float:
        return subtotal(items)

    def descripcion(self) -> str:
        return "Consulta: precio de lista."


class TarifaControl(EstrategiaTarifa):
    """Control de seguimiento: descuento sobre los servicios clínicos."""

    def __init__(self, descuento_pct: float = config.TARIFA_CONTROL_DESCUENTO_PCT):
        self.descuento_pct = descuento_pct

    def nombre(self) -> str:
        return "CONTROL"

    def calcular_total(self, items) -> float:
        descuento = subtotal_por_tipo(items, TipoItem.SERVICIO_CLINICO) * self.descuento_pct / 100
        return round(subtotal(items) - descuento, 2)

    def descripcion(self) -> str:
        return f"Control: {self.descuento_pct:g} % de descuento en servicios clínicos."


class TarifaUrgencia(EstrategiaTarifa):
    """Urgencia: recargo sobre los servicios clínicos, mayor en horario nocturno."""

    def __init__(self, fecha_hora: datetime, recargo_pct: float = config.TARIFA_URGENCIA_RECARGO_PCT,
                 recargo_nocturno_pct: float = config.TARIFA_URGENCIA_RECARGO_NOCTURNO_PCT):
        self.fecha_hora = fecha_hora
        self.recargo_pct = recargo_pct
        self.recargo_nocturno_pct = recargo_nocturno_pct

    def nombre(self) -> str:
        return "URGENCIA"

    def es_nocturna(self) -> bool:
        desde, hasta = config.HORARIO_NOCTURNO
        hora = self.fecha_hora.time()
        return hora >= desde or hora < hasta

    def porcentaje_recargo(self) -> float:
        return self.recargo_pct + (self.recargo_nocturno_pct if self.es_nocturna() else 0)

    def calcular_total(self, items) -> float:
        recargo = subtotal_por_tipo(items, TipoItem.SERVICIO_CLINICO) * self.porcentaje_recargo() / 100
        return round(subtotal(items) + recargo, 2)

    def descripcion(self) -> str:
        nocturno = " (incluye recargo nocturno)" if self.es_nocturna() else ""
        return f"Urgencia: {self.porcentaje_recargo():g} % de recargo en servicios clínicos{nocturno}."
