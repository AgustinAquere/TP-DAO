"""Recepción en el laboratorio central y resultados de los análisis."""
from dataclasses import dataclass, field
from datetime import datetime

from app.dominio.enums import EstadoPrecinto
from app.dominio.excepciones import ValidacionError
from app.utils import validaciones as v

MOTIVO_PRECINTO_ROTO = "Precinto sanitario roto: se perdió la cadena de custodia."


@dataclass(kw_only=True)
class RecepcionLaboratorio:
    id_remito: int
    id_bioquimico: int
    fecha_hora: datetime
    estado_precinto_verificado: EstadoPrecinto
    temperatura_arribo_c: float | None = None
    aceptada: bool = False
    motivo_rechazo: str | None = None
    id: int | None = None

    def precinto_intacto(self) -> bool:
        return self.estado_precinto_verificado == EstadoPrecinto.INTACTO

    def evaluar(self, remito) -> bool:
        """El remito se acepta solo si el precinto llegó intacto."""
        if remito.precinto is not None and remito.precinto.fecha_hora_colocacion > self.fecha_hora:
            raise ValidacionError("La recepción no puede ser anterior a la colocación del precinto.")
        self.aceptada = self.precinto_intacto()
        if not self.aceptada:
            self.motivo_rechazo = self.motivo_rechazo or MOTIVO_PRECINTO_ROTO
        return self.aceptada

    def motivo_rechazo_muestra(self, muestra) -> str | None:
        """Falla de transporte que impide procesar una muestra concreta (temperatura o viabilidad)."""
        if self.temperatura_arribo_c is not None and not muestra.admite_temperatura(self.temperatura_arribo_c):
            minimo, maximo = muestra.rango_temperatura_requerido()
            return (f"Temperatura de arribo {self.temperatura_arribo_c:g} °C fuera del rango requerido "
                    f"({minimo:g} a {maximo:g} °C).")
        if not muestra.es_viable(self.fecha_hora):
            return (f"Viabilidad vencida: {muestra.horas_desde_extraccion(self.fecha_hora):.1f} h desde la "
                    f"extracción (máximo {muestra.horas_max_viabilidad()} h).")
        return None


@dataclass(kw_only=True)
class DetalleResultado:
    parametro: str
    valor: float
    unidad: str | None = None
    valor_ref_min: float | None = None
    valor_ref_max: float | None = None
    id_resultado: int | None = None
    id: int | None = None

    def fuera_de_rango(self) -> bool:
        debajo = self.valor_ref_min is not None and self.valor < self.valor_ref_min
        arriba = self.valor_ref_max is not None and self.valor > self.valor_ref_max
        return debajo or arriba

    def rango_referencia(self) -> str:
        if self.valor_ref_min is None and self.valor_ref_max is None:
            return ""
        texto = lambda valor: "—" if valor is None else f"{valor:g}"
        return f"{texto(self.valor_ref_min)} – {texto(self.valor_ref_max)}"


@dataclass(kw_only=True)
class ResultadoAnalisis:
    id_analisis_solicitado: int
    id_bioquimico: int
    fecha_hora: datetime
    interpretacion: str | None = None
    observaciones: str | None = None
    id: int | None = None
    detalles: list[DetalleResultado] = field(default_factory=list)

    def validar(self) -> None:
        v.validar(self, [
            (lambda r: len(r.detalles) > 0, "El resultado debe tener al menos un parámetro informado."),
            (lambda r: all(v.texto_requerido(d.parametro) for d in r.detalles),
             "Todos los parámetros deben tener nombre."),
            (lambda r: all(d.valor_ref_min is None or d.valor_ref_max is None or d.valor_ref_min <= d.valor_ref_max
                           for d in r.detalles),
             "En los valores de referencia, el mínimo no puede superar al máximo."),
        ])

    def agregar_detalle(self, detalle: DetalleResultado) -> None:
        self.detalles.append(detalle)

    def valores_fuera_de_rango(self) -> list[DetalleResultado]:
        return list(filter(lambda d: d.fuera_de_rango(), self.detalles))
