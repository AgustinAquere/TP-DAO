"""Patrón State: ciclo de vida de la muestra biológica.

Transiciones válidas:
    Extraída -> Empaquetada -> En tránsito -> Recibida -> Analizada
    Extraída | En tránsito | Recibida -> Rechazada   (p. ej. precinto roto en la recepción)
Cada estado redefine solo las operaciones que le son válidas; el resto lanza TransicionInvalidaError.
"""
from abc import ABC, abstractmethod

from app.dominio.excepciones import TransicionInvalidaError
from app.utils import formato


class EstadoMuestra(ABC):
    @abstractmethod
    def nombre(self) -> str:
        """Nombre del estado tal como se persiste en la base."""

    def etiqueta(self) -> str:
        return formato.etiqueta(self.nombre())

    def es_final(self) -> bool:
        return False

    def _no_permitido(self, accion: str):
        raise TransicionInvalidaError(f"No se puede {accion} una muestra en estado «{self.etiqueta()}».")

    def empaquetar(self, muestra, remito, responsable, fecha_hora) -> None:
        self._no_permitido("empaquetar")

    def despachar(self, muestra, responsable, fecha_hora) -> None:
        self._no_permitido("despachar")

    def recibir(self, muestra, responsable, fecha_hora) -> None:
        self._no_permitido("recibir")

    def analizar(self, muestra, responsable, fecha_hora) -> None:
        self._no_permitido("analizar (procesar)")

    def rechazar(self, muestra, motivo, responsable, fecha_hora) -> None:
        self._no_permitido("rechazar")


class Extraida(EstadoMuestra):
    def nombre(self) -> str:
        return "EXTRAIDA"

    def empaquetar(self, muestra, remito, responsable, fecha_hora) -> None:
        muestra.id_remito = remito.id
        muestra._cambiar_estado(Empaquetada(), responsable, f"Empaquetada en remito {remito.numero}", fecha_hora)

    def rechazar(self, muestra, motivo, responsable, fecha_hora) -> None:
        muestra._cambiar_estado(Rechazada(), responsable, motivo, fecha_hora)


class Empaquetada(EstadoMuestra):
    def nombre(self) -> str:
        return "EMPAQUETADA"

    def despachar(self, muestra, responsable, fecha_hora) -> None:
        muestra._cambiar_estado(EnTransito(), responsable, "Despachada hacia el laboratorio", fecha_hora)


class EnTransito(EstadoMuestra):
    def nombre(self) -> str:
        return "EN_TRANSITO"

    def recibir(self, muestra, responsable, fecha_hora) -> None:
        muestra._cambiar_estado(Recibida(), responsable, "Recibida en el laboratorio", fecha_hora)

    def rechazar(self, muestra, motivo, responsable, fecha_hora) -> None:
        muestra._cambiar_estado(Rechazada(), responsable, motivo, fecha_hora)


class Recibida(EstadoMuestra):
    def nombre(self) -> str:
        return "RECIBIDA"

    def analizar(self, muestra, responsable, fecha_hora) -> None:
        muestra._cambiar_estado(Analizada(), responsable, "Análisis finalizados", fecha_hora)

    def rechazar(self, muestra, motivo, responsable, fecha_hora) -> None:
        muestra._cambiar_estado(Rechazada(), responsable, motivo, fecha_hora)


class Analizada(EstadoMuestra):
    def nombre(self) -> str:
        return "ANALIZADA"

    def es_final(self) -> bool:
        return True


class Rechazada(EstadoMuestra):
    def nombre(self) -> str:
        return "RECHAZADA"

    def es_final(self) -> bool:
        return True


# Reconstrucción del objeto estado a partir del nombre guardado en la base
_ESTADOS = {estado().nombre(): estado for estado in (Extraida, Empaquetada, EnTransito, Recibida, Analizada, Rechazada)}


def estado_muestra_desde(nombre: str) -> EstadoMuestra:
    try:
        return _ESTADOS[nombre]()
    except KeyError:
        raise ValueError(f"Estado de muestra desconocido: {nombre}") from None
