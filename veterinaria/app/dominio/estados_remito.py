"""Patrón State: ciclo de vida del remito biológico.

En preparación -> Precintado -> En tránsito -> Recibido | Rechazado
El remito delega en su estado; cada estado coordina además las transiciones de sus muestras.
"""
from abc import ABC, abstractmethod

from app.dominio.excepciones import TransicionInvalidaError, ValidacionError
from app.utils import formato

ESTADO_EXTRAIDA = "EXTRAIDA"


class EstadoRemito(ABC):
    OPERACIONES = ("agregar_muestra", "quitar_muestra", "precintar", "despachar",
                   "registrar_tramo", "cerrar_tramo", "recibir")

    @abstractmethod
    def nombre(self) -> str:
        """Nombre del estado tal como se persiste en la base."""

    def etiqueta(self) -> str:
        return formato.etiqueta(self.nombre())

    def es_final(self) -> bool:
        return False

    def operaciones_permitidas(self) -> set[str]:
        """Operaciones que este estado redefine (las únicas que admite)."""
        return {op for op in self.OPERACIONES if getattr(type(self), op) is not getattr(EstadoRemito, op)}

    def _no_permitido(self, accion: str):
        raise TransicionInvalidaError(f"No se puede {accion} un remito en estado «{self.etiqueta()}».")

    def agregar_muestra(self, remito, muestra) -> None:
        self._no_permitido("agregar muestras a")

    def quitar_muestra(self, remito, muestra) -> None:
        self._no_permitido("quitar muestras de")

    def precintar(self, remito, precinto, responsable) -> None:
        self._no_permitido("precintar")

    def despachar(self, remito, tramo, responsable) -> None:
        self._no_permitido("despachar")

    def registrar_tramo(self, remito, tramo) -> None:
        self._no_permitido("registrar un tramo en")

    def cerrar_tramo(self, remito, datos_llegada: dict) -> None:
        self._no_permitido("cerrar el tramo de")

    def recibir(self, remito, recepcion, responsable) -> None:
        self._no_permitido("recibir")


class EnPreparacion(EstadoRemito):
    def nombre(self) -> str:
        return "EN_PREPARACION"

    def agregar_muestra(self, remito, muestra) -> None:
        if muestra.nombre_estado() != ESTADO_EXTRAIDA:
            raise TransicionInvalidaError(f"La muestra {muestra.codigo} no está pendiente de empaquetar.")
        if muestra.id_remito not in (None, remito.id) or muestra in remito.muestras:
            raise ValidacionError(f"La muestra {muestra.codigo} ya está asignada a un remito.")
        motivo = remito.conservadora.motivo_no_admite(muestra, len(remito.muestras))
        if motivo:
            raise ValidacionError(motivo)
        muestra.id_remito = remito.id
        remito.muestras.append(muestra)

    def quitar_muestra(self, remito, muestra) -> None:
        remito.muestras.remove(muestra)
        muestra.id_remito = None

    def precintar(self, remito, precinto, responsable) -> None:
        if not remito.muestras:
            raise ValidacionError("No se puede precintar un remito sin muestras.")
        precinto.id_remito = remito.id
        remito.precinto = precinto
        for muestra in remito.muestras:
            muestra.empaquetar(remito, responsable=responsable, fecha_hora=precinto.fecha_hora_colocacion)
        remito._cambiar_estado(Precintado())


class Precintado(EstadoRemito):
    def nombre(self) -> str:
        return "PRECINTADO"

    def despachar(self, remito, tramo, responsable) -> None:
        if tramo.fecha_hora_salida < remito.precinto.fecha_hora_colocacion:
            raise ValidacionError("El despacho no puede ser anterior a la colocación del precinto.")
        tramo.nro_orden = 1
        tramo.id_remito = remito.id
        tramo.validar()
        remito.tramos.append(tramo)
        for muestra in remito.muestras:
            muestra.despachar(responsable=responsable, fecha_hora=tramo.fecha_hora_salida)
        remito._cambiar_estado(EnTransito())


class EnTransito(EstadoRemito):
    def nombre(self) -> str:
        return "EN_TRANSITO"

    def registrar_tramo(self, remito, tramo) -> None:
        actual = remito.tramo_actual()
        if actual.esta_abierto():
            raise ValidacionError("Antes de iniciar un nuevo tramo debe registrarse la llegada del tramo actual.")
        if tramo.fecha_hora_salida < actual.fecha_hora_llegada:
            raise ValidacionError("El nuevo tramo no puede salir antes de la llegada del tramo anterior.")
        tramo.nro_orden = actual.nro_orden + 1
        tramo.id_remito = remito.id
        tramo.validar()
        remito.tramos.append(tramo)

    def cerrar_tramo(self, remito, datos_llegada: dict) -> None:
        actual = remito.tramo_actual()
        if not actual.esta_abierto():
            raise ValidacionError("El tramo actual ya tiene registrada su llegada.")
        actual.cerrar(**datos_llegada)

    def recibir(self, remito, recepcion, responsable) -> None:
        actual = remito.tramo_actual()
        if actual.esta_abierto():
            actual.cerrar(fecha_hora_llegada=recepcion.fecha_hora, recibido_por=responsable,
                          temperatura_llegada_c=recepcion.temperatura_arribo_c)
        remito.precinto.verificar(recepcion.precinto_intacto())
        if recepcion.evaluar(remito):
            # Precinto intacto: cada muestra se evalúa por temperatura y viabilidad
            for muestra in remito.muestras:
                motivo = recepcion.motivo_rechazo_muestra(muestra)
                if motivo:
                    muestra.rechazar(motivo, responsable=responsable, fecha_hora=recepcion.fecha_hora)
                else:
                    muestra.recibir(responsable=responsable, fecha_hora=recepcion.fecha_hora)
            remito._cambiar_estado(Recibido())
        else:
            # Precinto roto: ninguna muestra puede procesarse
            for muestra in remito.muestras:
                muestra.rechazar(recepcion.motivo_rechazo, responsable=responsable, fecha_hora=recepcion.fecha_hora)
            remito._cambiar_estado(Rechazado())
        remito.recepcion = recepcion


class Recibido(EstadoRemito):
    def nombre(self) -> str:
        return "RECIBIDO"

    def es_final(self) -> bool:
        return True


class Rechazado(EstadoRemito):
    def nombre(self) -> str:
        return "RECHAZADO"

    def es_final(self) -> bool:
        return True


_ESTADOS = {estado().nombre(): estado for estado in (EnPreparacion, Precintado, EnTransito, Recibido, Rechazado)}


def estado_remito_desde(nombre: str) -> EstadoRemito:
    try:
        return _ESTADOS[nombre]()
    except KeyError:
        raise ValueError(f"Estado de remito desconocido: {nombre}") from None
