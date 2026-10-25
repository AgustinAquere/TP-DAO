"""Muestra biológica: contexto del patrón State, con historial inmutable de estados."""
from datetime import datetime

from app.dominio.enums import TipoMuestra
from app.dominio.estados_muestra import EstadoMuestra, Extraida
from app.dominio.historial import CambioEstado, HistorialEstados
from app.utils import fechas


class Muestra:
    def __init__(self, *, id_orden: int | None, id_veterinario: int, codigo: str, tipo: TipoMuestra,
                 fecha_hora_extraccion: datetime, volumen_ml: float | None = None, id_remito: int | None = None,
                 estado: EstadoMuestra | None = None, historial: HistorialEstados | None = None,
                 id: int | None = None):
        self.id = id
        self.id_orden = id_orden
        self.id_veterinario = id_veterinario
        self.id_remito = id_remito
        self.codigo = codigo
        self.tipo = TipoMuestra(tipo)
        self.fecha_hora_extraccion = fecha_hora_extraccion
        self.volumen_ml = volumen_ml
        self._estado = estado or Extraida()
        self._historial = historial or HistorialEstados()
        # Análisis que se procesan sobre esta muestra (TipoAnalisis); los carga la capa de servicios
        self.tipos_analisis: list = []

    @classmethod
    def extraer(cls, *, responsable: str, **datos) -> "Muestra":
        """Crea una muestra recién extraída y registra el primer cambio del historial."""
        muestra = cls(**datos)
        muestra._historial.registrar(CambioEstado(muestra.fecha_hora_extraccion, None, muestra.nombre_estado(),
                                                  responsable, "Extracción de la muestra"))
        return muestra

    # --- Operaciones: se delegan en el estado actual -------------------------
    def empaquetar(self, remito, *, responsable: str, fecha_hora: datetime | None = None) -> None:
        self._estado.empaquetar(self, remito, responsable, fecha_hora or fechas.ahora())

    def despachar(self, *, responsable: str, fecha_hora: datetime | None = None) -> None:
        self._estado.despachar(self, responsable, fecha_hora or fechas.ahora())

    def recibir(self, *, responsable: str, fecha_hora: datetime | None = None) -> None:
        self._estado.recibir(self, responsable, fecha_hora or fechas.ahora())

    def analizar(self, *, responsable: str, fecha_hora: datetime | None = None) -> None:
        self._estado.analizar(self, responsable, fecha_hora or fechas.ahora())

    def rechazar(self, motivo: str, *, responsable: str, fecha_hora: datetime | None = None) -> None:
        self._estado.rechazar(self, motivo, responsable, fecha_hora or fechas.ahora())

    def _cambiar_estado(self, nuevo: EstadoMuestra, responsable: str, observacion: str | None,
                        fecha_hora: datetime) -> None:
        """Solo lo invocan los objetos estado: registra el cambio en el historial y reemplaza el estado."""
        self._historial.registrar(CambioEstado(fecha_hora, self.nombre_estado(), nuevo.nombre(),
                                               responsable, observacion))
        self._estado = nuevo

    # --- Consultas -----------------------------------------------------------
    def nombre_estado(self) -> str:
        return self._estado.nombre()

    def etiqueta_estado(self) -> str:
        return self._estado.etiqueta()

    def es_final(self) -> bool:
        return self._estado.es_final()

    def historial(self) -> HistorialEstados:
        return self._historial

    def rango_temperatura_requerido(self) -> tuple[float, float] | None:
        """Intersección de los rangos de conservación de todos sus análisis."""
        if not self.tipos_analisis:
            return None
        return (max(t.temp_min_c for t in self.tipos_analisis), min(t.temp_max_c for t in self.tipos_analisis))

    def horas_max_viabilidad(self) -> int | None:
        return min((t.horas_max_viabilidad for t in self.tipos_analisis), default=None)

    def horas_desde_extraccion(self, ahora: datetime | None = None) -> float:
        return fechas.horas_entre(self.fecha_hora_extraccion, ahora or fechas.ahora())

    def es_viable(self, ahora: datetime | None = None) -> bool:
        limite = self.horas_max_viabilidad()
        return limite is None or self.horas_desde_extraccion(ahora) <= limite

    def admite_temperatura(self, temperatura: float) -> bool:
        rango = self.rango_temperatura_requerido()
        return rango is None or rango[0] <= temperatura <= rango[1]

    def __repr__(self) -> str:
        return f"Muestra({self.codigo}, {self.nombre_estado()})"
