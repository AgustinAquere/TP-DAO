"""Atenciones clínicas (consultas, controles y urgencias) y tratamientos indicados."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.dominio.derivacion import OrdenDerivacion, TipoAnalisis
from app.dominio.enums import Prioridad, TipoAtencion, TipoMuestra
from app.dominio.mascota import Mascota
from app.dominio.vacunas import AplicacionVacuna, Vacuna, VacunaObligatoria
from app.utils import validaciones as v


@dataclass(kw_only=True)
class Tratamiento:
    descripcion: str
    fecha_inicio: date
    medicamento: str | None = None
    dosis: str | None = None
    frecuencia: str | None = None
    fecha_fin: date | None = None
    id_atencion: int | None = None
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda t: v.texto_requerido(t.descripcion), "La descripción del tratamiento es obligatoria."),
            (lambda t: t.fecha_fin is None or t.fecha_fin >= t.fecha_inicio,
             "La fecha de fin del tratamiento no puede ser anterior a la de inicio."),
        ])

    def esta_vigente(self, fecha: date | None = None) -> bool:
        fecha = fecha or date.today()
        return self.fecha_inicio <= fecha and (self.fecha_fin is None or fecha <= self.fecha_fin)


@dataclass(kw_only=True)
class Atencion:
    id_historia: int | None
    id_veterinario: int
    id_clinica: int
    fecha_hora: datetime
    tipo: TipoAtencion
    motivo: str
    id_turno: int | None = None
    anamnesis: str | None = None
    diagnostico: str | None = None
    peso_registrado_kg: float | None = None
    id: int | None = None
    tratamientos: list[Tratamiento] = field(default_factory=list, repr=False, compare=False)
    aplicaciones: list[AplicacionVacuna] = field(default_factory=list, repr=False, compare=False)
    ordenes: list[OrdenDerivacion] = field(default_factory=list, repr=False, compare=False)
    # Resultado del control del esquema al registrar (vacunas obligatorias que quedaron pendientes)
    vacunas_pendientes: list[VacunaObligatoria] = field(default_factory=list, repr=False, compare=False)

    def validar(self) -> None:
        v.validar(self, [
            (lambda a: v.texto_requerido(a.motivo), "El motivo de la atención es obligatorio."),
            (lambda a: v.positivo_u_omitido(a.peso_registrado_kg), "El peso registrado debe ser mayor a cero."),
            (lambda a: a.fecha_hora <= datetime.now() + timedelta(minutes=5),
             "La atención no puede registrarse con fecha futura."),
        ])

    def agregar_tratamiento(self, tratamiento: Tratamiento) -> None:
        tratamiento.validar()
        tratamiento.id_atencion = self.id
        self.tratamientos.append(tratamiento)

    def aplicar_vacuna(self, vacuna: Vacuna, lote: str, esquema: VacunaObligatoria | None = None) -> AplicacionVacuna:
        fecha = self.fecha_hora.date()
        aplicacion = AplicacionVacuna(id_vacuna=vacuna.id, fecha=fecha, lote=(lote or "").strip(),
                                      fecha_proxima_dosis=esquema.calcular_proxima_dosis(fecha) if esquema else None,
                                      id_atencion=self.id, nombre_vacuna=vacuna.nombre)
        aplicacion.validar()
        self.aplicaciones.append(aplicacion)
        return aplicacion

    def emitir_orden_derivacion(self, *, id_laboratorio: int, analisis: list[TipoAnalisis], numero: str,
                                responsable: str, prioridad: Prioridad = Prioridad.NORMAL,
                                indicaciones: str | None = None, volumenes: dict[TipoMuestra, float] | None = None,
                                fecha_hora: datetime | None = None) -> OrdenDerivacion:
        orden = OrdenDerivacion.emitir(id_atencion=self.id, id_laboratorio=id_laboratorio, numero=numero,
                                       fecha_emision=fecha_hora or self.fecha_hora, tipos_analisis=analisis,
                                       id_veterinario=self.id_veterinario, responsable=responsable,
                                       prioridad=prioridad, indicaciones=indicaciones, volumenes=volumenes)
        self.ordenes.append(orden)
        return orden

    def validar_esquema_vacunas(self, mascota: Mascota) -> list[VacunaObligatoria]:
        """Vacunas obligatorias que siguen pendientes contando las aplicadas en esta atención."""
        aplicadas = mascota.aplicaciones + self.aplicaciones
        return mascota.vacunas_pendientes(self.fecha_hora.date(), aplicadas)
