"""Comprobantes de atención. El total se delega en una EstrategiaTarifa (patrón Strategy)."""
from dataclasses import dataclass, field
from datetime import datetime

from app.dominio import tarifas
from app.dominio.enums import TipoItem
from app.dominio.excepciones import ValidacionError
from app.dominio.tarifas import EstrategiaTarifa
from app.utils import validaciones as v


@dataclass(kw_only=True)
class ServicioClinico:
    codigo: str
    nombre: str
    precio_base: float
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda s: v.texto_requerido(s.codigo), "El código es obligatorio."),
            (lambda s: v.texto_requerido(s.nombre), "El nombre es obligatorio."),
            (lambda s: s.precio_base >= 0, "El precio no puede ser negativo."),
        ])

    def __str__(self) -> str:
        return self.nombre


# Referencia obligatoria según el tipo de ítem (mismo criterio que el CHECK de item_comprobante)
_REFERENCIA_POR_TIPO = {
    TipoItem.SERVICIO_CLINICO: "id_servicio",
    TipoItem.ANALISIS_LABORATORIO: "id_tipo_analisis",
    TipoItem.VACUNA: "id_vacuna",
    TipoItem.INSUMO: None,
}


@dataclass(kw_only=True)
class ItemComprobante:
    tipo: TipoItem
    descripcion: str
    precio_unitario: float
    cantidad: int = 1
    id_servicio: int | None = None
    id_tipo_analisis: int | None = None
    id_vacuna: int | None = None
    id_comprobante: int | None = None
    id: int | None = None

    def importe(self) -> float:
        return round(self.cantidad * self.precio_unitario, 2)

    def validar(self) -> None:
        requerida = _REFERENCIA_POR_TIPO[self.tipo]
        referencias = {nombre: getattr(self, nombre) for nombre in ("id_servicio", "id_tipo_analisis", "id_vacuna")}
        v.validar(self, [
            (lambda i: v.texto_requerido(i.descripcion), "Cada ítem debe tener una descripción."),
            (lambda i: i.cantidad > 0, f"La cantidad de «{self.descripcion}» debe ser mayor a cero."),
            (lambda i: i.precio_unitario >= 0, f"El precio de «{self.descripcion}» no puede ser negativo."),
            (lambda i: all((valor is not None) == (nombre == requerida) for nombre, valor in referencias.items()),
             f"El ítem «{self.descripcion}» no referencia correctamente su concepto."),
        ])


@dataclass(kw_only=True)
class ComprobanteAtencion:
    id_atencion: int
    id_cliente: int
    id_clinica: int
    numero: str
    fecha_emision: datetime
    items: list[ItemComprobante] = field(default_factory=list)
    estrategia_tarifa: str | None = None
    subtotal_emitido: float | None = None
    total_emitido: float | None = None
    id: int | None = None
    _estrategia: EstrategiaTarifa | None = field(default=None, init=False, repr=False, compare=False)

    def set_estrategia(self, estrategia: EstrategiaTarifa) -> None:
        self._estrategia = estrategia
        self.estrategia_tarifa = estrategia.nombre()

    def estrategia(self) -> EstrategiaTarifa | None:
        return self._estrategia

    def agregar_item(self, item: ItemComprobante) -> None:
        item.validar()
        self.items.append(item)

    def subtotal(self) -> float:
        return tarifas.subtotal(self.items) if self.subtotal_emitido is None else self.subtotal_emitido

    def subtotal_por_tipo(self, tipo: TipoItem) -> float:
        return tarifas.subtotal_por_tipo(self.items, tipo)

    def total(self) -> float:
        """Total calculado por la estrategia; un comprobante ya emitido conserva el total congelado."""
        if self.total_emitido is not None:
            return self.total_emitido
        if self._estrategia is None:
            raise ValidacionError("El comprobante no tiene una estrategia de tarifa asignada.")
        return self._estrategia.calcular_total(self.items)

    def ajuste(self) -> float:
        """Recargo (positivo) o descuento (negativo) aplicado por la estrategia."""
        return round(self.total() - self.subtotal(), 2)

    def emitir(self) -> None:
        """Congela subtotal y total: los reportes no deben depender de recalcular con precios futuros."""
        if not self.items:
            raise ValidacionError("El comprobante debe tener al menos un ítem.")
        if self._estrategia is None:
            raise ValidacionError("El comprobante no tiene una estrategia de tarifa asignada.")
        for item in self.items:
            item.validar()
        self.subtotal_emitido = tarifas.subtotal(self.items)
        self.total_emitido = self._estrategia.calcular_total(self.items)
