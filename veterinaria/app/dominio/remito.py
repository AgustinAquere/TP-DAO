"""Remito biológico: contexto del patrón State que agrupa las muestras enviadas en una conservadora."""
from datetime import datetime, timedelta

from app.dominio.envio import Conservadora, PrecintoSanitario, TramoEnvio
from app.dominio.estados_remito import EnPreparacion, EstadoRemito
from app.dominio.muestra import Muestra
from app.utils import fechas


class RemitoBiologico:
    def __init__(self, *, id_conservadora: int, id_clinica_origen: int, id_laboratorio_destino: int, numero: str,
                 fecha_hora_emision: datetime, estado: EstadoRemito | None = None, id: int | None = None):
        self.id = id
        self.id_conservadora = id_conservadora
        self.id_clinica_origen = id_clinica_origen
        self.id_laboratorio_destino = id_laboratorio_destino
        self.numero = numero
        self.fecha_hora_emision = fecha_hora_emision
        self._estado = estado or EnPreparacion()
        self.muestras: list[Muestra] = []
        self.tramos: list[TramoEnvio] = []
        self.precinto: PrecintoSanitario | None = None
        self.conservadora: Conservadora | None = None
        self.recepcion = None
        # Nombres para mostrar (los completa la capa de persistencia)
        self.nombre_clinica = ""
        self.nombre_laboratorio = ""

    # --- Operaciones: se delegan en el estado actual -------------------------
    def agregar_muestra(self, muestra: Muestra) -> None:
        self._estado.agregar_muestra(self, muestra)

    def quitar_muestra(self, muestra: Muestra) -> None:
        self._estado.quitar_muestra(self, muestra)

    def precintar(self, nro_precinto: str, *, responsable: str, fecha_hora: datetime | None = None) -> PrecintoSanitario:
        precinto = PrecintoSanitario(numero=nro_precinto, fecha_hora_colocacion=fecha_hora or fechas.ahora())
        self._estado.precintar(self, precinto, responsable)
        return precinto

    def despachar(self, tramo: TramoEnvio, *, responsable: str) -> TramoEnvio:
        self._estado.despachar(self, tramo, responsable)
        return tramo

    def registrar_tramo(self, tramo: TramoEnvio) -> TramoEnvio:
        self._estado.registrar_tramo(self, tramo)
        return tramo

    def cerrar_tramo(self, *, fecha_hora_llegada: datetime, recibido_por: str,
                     temperatura_llegada_c: float | None = None, observaciones: str | None = None) -> TramoEnvio:
        self._estado.cerrar_tramo(self, {"fecha_hora_llegada": fecha_hora_llegada, "recibido_por": recibido_por,
                                         "temperatura_llegada_c": temperatura_llegada_c,
                                         "observaciones": observaciones})
        return self.tramo_actual()

    def recibir(self, recepcion, *, responsable: str) -> None:
        self._estado.recibir(self, recepcion, responsable)

    def _cambiar_estado(self, nuevo: EstadoRemito) -> None:
        self._estado = nuevo

    # --- Consultas -----------------------------------------------------------
    def nombre_estado(self) -> str:
        return self._estado.nombre()

    def etiqueta_estado(self) -> str:
        return self._estado.etiqueta()

    def es_final(self) -> bool:
        return self._estado.es_final()

    def operaciones_permitidas(self) -> set[str]:
        return self._estado.operaciones_permitidas()

    def tramo_actual(self) -> TramoEnvio | None:
        return self.tramos[-1] if self.tramos else None

    def tiempo_transito(self) -> timedelta | None:
        """Desde la salida del primer tramo hasta la llegada del último."""
        if not self.tramos or self.tramo_actual().esta_abierto():
            return None
        return self.tramos[-1].fecha_hora_llegada - self.tramos[0].fecha_hora_salida

    def __repr__(self) -> str:
        return f"RemitoBiologico({self.numero}, {self.nombre_estado()}, {len(self.muestras)} muestras)"
