"""Órdenes de derivación al laboratorio, análisis solicitados y su catálogo."""
from dataclasses import dataclass, field
from datetime import datetime

from app.dominio.enums import EstadoOrden, Prioridad, TipoMuestra
from app.dominio.excepciones import ValidacionError
from app.dominio.muestra import Muestra
from app.utils import validaciones as v


@dataclass(kw_only=True)
class TipoAnalisis:
    codigo: str
    nombre: str
    tipo_muestra_requerida: TipoMuestra
    temp_min_c: float
    temp_max_c: float
    horas_max_viabilidad: int
    precio: float
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda t: v.texto_requerido(t.codigo), "El código es obligatorio."),
            (lambda t: v.texto_requerido(t.nombre), "El nombre es obligatorio."),
            (lambda t: t.temp_min_c <= t.temp_max_c, "La temperatura mínima no puede superar a la máxima."),
            (lambda t: t.horas_max_viabilidad > 0, "Las horas de viabilidad deben ser mayores a cero."),
            (lambda t: t.precio >= 0, "El precio no puede ser negativo."),
        ])

    def __str__(self) -> str:
        return self.nombre


@dataclass(kw_only=True)
class AnalisisSolicitado:
    id_tipo_analisis: int
    id_muestra: int | None = None
    id_orden: int | None = None
    observaciones: str | None = None
    id: int | None = None
    tipo_analisis: TipoAnalisis | None = field(default=None, repr=False, compare=False)
    muestra: Muestra | None = field(default=None, repr=False, compare=False)
    resultado: object | None = field(default=None, repr=False, compare=False)

    def tiene_resultado(self) -> bool:
        return self.resultado is not None


@dataclass(kw_only=True)
class OrdenDerivacion:
    id_atencion: int | None
    id_laboratorio: int
    numero: str
    fecha_emision: datetime
    prioridad: Prioridad = Prioridad.NORMAL
    indicaciones_clinicas: str | None = None
    estado: EstadoOrden = EstadoOrden.EMITIDA
    id: int | None = None
    analisis: list[AnalisisSolicitado] = field(default_factory=list, repr=False, compare=False)
    muestras: list[Muestra] = field(default_factory=list, repr=False, compare=False)

    def registrar_extraccion(self, tipo: TipoMuestra, volumen: float | None, *, id_veterinario: int,
                             responsable: str, fecha_hora: datetime | None = None) -> Muestra:
        if volumen is not None and volumen <= 0:
            raise ValidacionError("El volumen de la muestra debe ser mayor a cero.")
        codigo = f"{self.numero}-M{len(self.muestras) + 1}"
        muestra = Muestra.extraer(responsable=responsable, id_orden=self.id, id_veterinario=id_veterinario,
                                  codigo=codigo, tipo=tipo, fecha_hora_extraccion=fecha_hora or self.fecha_emision,
                                  volumen_ml=volumen)
        self.muestras.append(muestra)
        return muestra

    def solicitar_analisis(self, tipo: TipoAnalisis, muestra: Muestra, observaciones: str | None = None) -> AnalisisSolicitado:
        if tipo.tipo_muestra_requerida != muestra.tipo:
            raise ValidacionError(f"El análisis {tipo.nombre} requiere una muestra de tipo "
                                  f"{tipo.tipo_muestra_requerida.value.lower()}.")
        if any(a.id_tipo_analisis == tipo.id for a in self.analisis):
            raise ValidacionError(f"El análisis {tipo.nombre} ya fue solicitado en la orden.")
        analisis = AnalisisSolicitado(id_tipo_analisis=tipo.id, id_muestra=muestra.id, id_orden=self.id,
                                      observaciones=observaciones, tipo_analisis=tipo, muestra=muestra)
        muestra.tipos_analisis.append(tipo)
        self.analisis.append(analisis)
        return analisis

    @classmethod
    def emitir(cls, *, id_atencion: int | None, id_laboratorio: int, numero: str, fecha_emision: datetime,
               tipos_analisis: list[TipoAnalisis], id_veterinario: int, responsable: str,
               prioridad: Prioridad = Prioridad.NORMAL, indicaciones: str | None = None,
               volumenes: dict[TipoMuestra, float] | None = None) -> "OrdenDerivacion":
        """Emite la orden, registra una extracción por cada tipo de muestra requerido y asocia los análisis."""
        if not tipos_analisis:
            raise ValidacionError("Debe solicitar al menos un análisis.")
        orden = cls(id_atencion=id_atencion, id_laboratorio=id_laboratorio, numero=numero,
                    fecha_emision=fecha_emision, prioridad=prioridad, indicaciones_clinicas=indicaciones)
        volumenes = volumenes or {}
        # Una sola extracción por tipo de muestra (p. ej. un tubo de suero sirve para bioquímica y T4)
        tipos_muestra = list(dict.fromkeys(t.tipo_muestra_requerida for t in tipos_analisis))
        muestras = {tipo: orden.registrar_extraccion(tipo, volumenes.get(tipo), id_veterinario=id_veterinario,
                                                     responsable=responsable, fecha_hora=fecha_emision)
                    for tipo in tipos_muestra}
        for tipo in tipos_analisis:
            orden.solicitar_analisis(tipo, muestras[tipo.tipo_muestra_requerida])
        return orden

    def esta_completa(self) -> bool:
        return bool(self.analisis) and all(map(lambda a: a.tiene_resultado(), self.analisis))

    def actualizar_estado(self) -> None:
        """Deriva el estado de la orden a partir de sus análisis y muestras."""
        if self.estado == EstadoOrden.CANCELADA:
            return
        if self.esta_completa():
            self.estado = EstadoOrden.COMPLETA
        elif any(m.nombre_estado() != "EXTRAIDA" for m in self.muestras):
            self.estado = EstadoOrden.EN_PROCESO
