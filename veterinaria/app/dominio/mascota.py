"""Especies, mascotas e historias clínicas."""
from dataclasses import dataclass, field
from datetime import date

from app.dominio.enums import Sexo
from app.dominio.vacunas import AplicacionVacuna, VacunaObligatoria
from app.utils import fechas
from app.utils import validaciones as v


@dataclass(kw_only=True)
class Especie:
    nombre: str
    esquema: list[VacunaObligatoria] = field(default_factory=list, repr=False)
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [(lambda e: v.texto_requerido(e.nombre), "El nombre es obligatorio.")])

    def __str__(self) -> str:
        return self.nombre


@dataclass(kw_only=True)
class Mascota:
    id_cliente: int | None
    id_especie: int | None
    nombre: str
    fecha_nacimiento: date | None
    raza: str | None = None
    sexo: Sexo | None = None
    peso_kg: float | None = None
    microchip: str | None = None
    id: int | None = None
    # Datos asociados que carga la capa de servicios cuando los necesita
    especie: Especie | None = field(default=None, repr=False, compare=False)
    aplicaciones: list[AplicacionVacuna] = field(default_factory=list, repr=False, compare=False)

    def validar(self) -> None:
        v.validar(self, [
            # Validación de negocio del enunciado: toda mascota debe tener un responsable
            (lambda m: m.id_cliente is not None, "Toda mascota debe tener un responsable asociado."),
            (lambda m: m.id_especie is not None, "La especie es obligatoria."),
            (lambda m: v.texto_requerido(m.nombre), "El nombre es obligatorio."),
            (lambda m: m.fecha_nacimiento is not None,
             "La fecha de nacimiento (aunque sea estimada) es necesaria para controlar el esquema de vacunas."),
            (lambda m: m.fecha_nacimiento is None or m.fecha_nacimiento <= date.today(),
             "La fecha de nacimiento no puede ser futura."),
            (lambda m: v.positivo_u_omitido(m.peso_kg), "El peso debe ser mayor a cero."),
        ])

    def edad_en_semanas(self, fecha: date | None = None) -> int | None:
        if self.fecha_nacimiento is None:
            return None
        return ((fecha or date.today()) - self.fecha_nacimiento).days // 7

    def edad_en_meses(self, fecha: date | None = None) -> int | None:
        if self.fecha_nacimiento is None:
            return None
        fecha = fecha or date.today()
        meses = (fecha.year - self.fecha_nacimiento.year) * 12 + fecha.month - self.fecha_nacimiento.month
        return meses - (1 if fecha.day < self.fecha_nacimiento.day else 0)

    def edad_legible(self, fecha: date | None = None) -> str:
        return fechas.edad_legible(self.fecha_nacimiento, fecha)

    def vacunas_pendientes(self, fecha: date | None = None,
                           aplicaciones: list[AplicacionVacuna] | None = None) -> list[VacunaObligatoria]:
        """Vacunas obligatorias de su especie que corresponde aplicar a la fecha indicada."""
        if self.especie is None:
            return []
        fecha = fecha or date.today()
        return list(filter(lambda vo: vo.corresponde_aplicar(self, fecha, aplicaciones), self.especie.esquema))

    def __str__(self) -> str:
        return self.nombre


@dataclass(kw_only=True)
class HistoriaClinica:
    """Historia clínica de una mascota (1:1). Es iterable: recorre sus atenciones de la más reciente a la más antigua."""
    id_mascota: int
    numero: str
    fecha_apertura: date = field(default_factory=date.today)
    observaciones_generales: str | None = None
    alergias: str | None = None
    id: int | None = None
    _atenciones: list = field(default_factory=list, init=False, repr=False, compare=False)

    def agregar_atencion(self, atencion) -> None:
        atencion.id_historia = self.id
        self._atenciones.append(atencion)

    def __iter__(self):
        yield from sorted(self._atenciones, key=lambda a: a.fecha_hora, reverse=True)

    def __len__(self) -> int:
        return len(self._atenciones)

    def ultima_atencion(self):
        return next(iter(self), None)
