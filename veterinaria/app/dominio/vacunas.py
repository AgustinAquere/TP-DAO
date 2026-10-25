"""Vacunas, esquema de vacunación obligatorio por especie y aplicaciones registradas."""
from dataclasses import dataclass
from datetime import date, timedelta

from app.utils import validaciones as v


@dataclass(kw_only=True)
class Vacuna:
    nombre: str
    laboratorio_fabricante: str | None = None
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [(lambda x: v.texto_requerido(x.nombre), "El nombre es obligatorio.")])

    def __str__(self) -> str:
        return self.nombre


@dataclass(kw_only=True)
class AplicacionVacuna:
    id_vacuna: int
    fecha: date
    lote: str
    fecha_proxima_dosis: date | None = None
    id_atencion: int | None = None
    nombre_vacuna: str = ""
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda a: v.texto_requerido(a.lote), "El lote de la vacuna es obligatorio."),
            (lambda a: a.fecha_proxima_dosis is None or a.fecha_proxima_dosis > a.fecha,
             "La próxima dosis debe ser posterior a la aplicación."),
        ])


@dataclass(kw_only=True)
class VacunaObligatoria:
    """Elemento del esquema obligatorio de una especie (edad mínima y frecuencia de refuerzo)."""
    id_especie: int
    id_vacuna: int
    edad_minima_semanas: int
    frecuencia_refuerzo_dias: int | None = None  # None = dosis única
    nombre_vacuna: str = ""
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda x: x.edad_minima_semanas >= 0, "La edad mínima no puede ser negativa."),
            (lambda x: v.positivo_u_omitido(x.frecuencia_refuerzo_dias),
             "La frecuencia de refuerzo debe ser mayor a cero (o vacía si es dosis única)."),
        ])

    def ultima_aplicacion(self, aplicaciones: list[AplicacionVacuna]) -> date | None:
        fechas = [a.fecha for a in aplicaciones if a.id_vacuna == self.id_vacuna]
        return max(fechas, default=None)

    def fecha_vencimiento(self, mascota, aplicaciones: list[AplicacionVacuna] | None = None) -> date | None:
        """Fecha desde la que la vacuna es exigible: edad mínima (si nunca se aplicó) o vencimiento del refuerzo."""
        aplicaciones = mascota.aplicaciones if aplicaciones is None else aplicaciones
        ultima = self.ultima_aplicacion(aplicaciones)
        if ultima is None:
            if mascota.fecha_nacimiento is None:
                return None
            return mascota.fecha_nacimiento + timedelta(weeks=self.edad_minima_semanas)
        if self.frecuencia_refuerzo_dias is None:
            return None
        return ultima + timedelta(days=self.frecuencia_refuerzo_dias)

    def corresponde_aplicar(self, mascota, fecha: date, aplicaciones: list[AplicacionVacuna] | None = None) -> bool:
        """True si la vacuna es exigible a la fecha: alcanzó la edad mínima y nunca se aplicó o venció el refuerzo."""
        vencimiento = self.fecha_vencimiento(mascota, aplicaciones)
        return vencimiento is not None and vencimiento <= fecha

    def calcular_proxima_dosis(self, fecha_aplicacion: date) -> date | None:
        if self.frecuencia_refuerzo_dias is None:
            return None
        return fecha_aplicacion + timedelta(days=self.frecuencia_refuerzo_dias)
