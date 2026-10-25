"""Empaquetado y envío: conservadoras isotérmicas, precinto sanitario y tramos de la cadena de custodia."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.dominio.enums import EstadoPrecinto
from app.dominio.excepciones import ValidacionError
from app.utils import validaciones as v


@dataclass(kw_only=True)
class Conservadora:
    """Contenedor isotérmico. Mantiene las muestras dentro de un rango de temperatura."""
    codigo: str
    capacidad: int
    temp_min_c: float
    temp_max_c: float
    disponible: bool = True
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda c: v.texto_requerido(c.codigo), "El código es obligatorio."),
            (lambda c: c.capacidad > 0, "La capacidad debe ser mayor a cero."),
            (lambda c: c.temp_min_c <= c.temp_max_c, "La temperatura mínima no puede superar a la máxima."),
        ])

    def motivo_no_admite(self, muestra, ocupadas: int) -> str | None:
        """Explica por qué la muestra no puede viajar en esta conservadora (None si la admite)."""
        if ocupadas >= self.capacidad:
            return f"La conservadora {self.codigo} está completa (capacidad: {self.capacidad} muestras)."
        rango = muestra.rango_temperatura_requerido()
        if rango and not (rango[0] <= self.temp_min_c and self.temp_max_c <= rango[1]):
            return (f"La muestra {muestra.codigo} debe conservarse entre {rango[0]:g} y {rango[1]:g} °C, "
                    f"pero la conservadora {self.codigo} mantiene {self.temp_min_c:g} a {self.temp_max_c:g} °C.")
        return None

    def admite(self, muestra, ocupadas: int = 0) -> bool:
        return self.motivo_no_admite(muestra, ocupadas) is None

    def __str__(self) -> str:
        return f"{self.codigo} ({self.temp_min_c:g} a {self.temp_max_c:g} °C, cap. {self.capacidad})"


@dataclass(kw_only=True)
class PrecintoSanitario:
    numero: str
    fecha_hora_colocacion: datetime
    estado: EstadoPrecinto = EstadoPrecinto.INTACTO
    id_remito: int | None = None
    id: int | None = None

    def verificar(self, intacto: bool) -> bool:
        """Registra el resultado de la verificación en destino. Un precinto roto no vuelve a estar intacto."""
        if not intacto:
            self.estado = EstadoPrecinto.ROTO
        return self.esta_intacto()

    def esta_intacto(self) -> bool:
        return self.estado == EstadoPrecinto.INTACTO


@dataclass(kw_only=True)
class TramoEnvio:
    """Eslabón de la cadena de custodia (clínica -> ... -> laboratorio)."""
    id_transportista: int
    origen: str
    destino: str
    fecha_hora_salida: datetime
    entregado_por: str
    nro_orden: int = 1
    fecha_hora_llegada: datetime | None = None
    temperatura_salida_c: float | None = None
    temperatura_llegada_c: float | None = None
    recibido_por: str | None = None
    observaciones: str | None = None
    id_remito: int | None = None
    id: int | None = None
    nombre_transportista: str = ""

    def validar(self) -> None:
        v.validar(self, [
            (lambda t: v.texto_requerido(t.origen), "El origen del tramo es obligatorio."),
            (lambda t: v.texto_requerido(t.destino), "El destino del tramo es obligatorio."),
            (lambda t: v.texto_requerido(t.entregado_por), "Debe indicar quién entrega la conservadora."),
            (lambda t: t.fecha_hora_llegada is None or t.fecha_hora_llegada >= t.fecha_hora_salida,
             "La llegada del tramo no puede ser anterior a su salida."),
        ])

    def esta_abierto(self) -> bool:
        return self.fecha_hora_llegada is None

    def cerrar(self, *, fecha_hora_llegada: datetime, recibido_por: str, temperatura_llegada_c: float | None = None,
               observaciones: str | None = None) -> None:
        if not v.texto_requerido(recibido_por):
            raise ValidacionError("Debe indicar quién recibe la conservadora al cerrar el tramo.")
        if fecha_hora_llegada < self.fecha_hora_salida:
            raise ValidacionError("La llegada del tramo no puede ser anterior a su salida.")
        self.fecha_hora_llegada = fecha_hora_llegada
        self.recibido_por = recibido_por
        self.temperatura_llegada_c = temperatura_llegada_c
        if observaciones:
            self.observaciones = observaciones

    def duracion(self) -> timedelta | None:
        return None if self.fecha_hora_llegada is None else self.fecha_hora_llegada - self.fecha_hora_salida
