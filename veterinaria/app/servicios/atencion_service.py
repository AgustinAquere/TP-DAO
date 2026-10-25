"""Proceso 3: registrar consultas médicas (con control del esquema de vacunas) y emitir órdenes de derivación."""
from dataclasses import dataclass, field
from datetime import date, datetime

from app.dominio.atencion import Atencion, Tratamiento
from app.dominio.derivacion import OrdenDerivacion
from app.dominio.enums import EstadoTurno, Prioridad, TipoAtencion, TipoMuestra
from app.dominio.excepciones import EntidadNoEncontradaError, EsquemaVacunasIncompletoError, ValidacionError
from app.dominio.mascota import Mascota
from app.dominio.vacunas import VacunaObligatoria
from app.persistencia.conexion import ConexionBD
from app.persistencia.daos.atencion_dao import AtencionDAO
from app.persistencia.daos.catalogos_dao import (LaboratorioDAO, TipoAnalisisDAO, VacunaDAO,
                                                 VacunaObligatoriaDAO)
from app.persistencia.daos.derivacion_dao import OrdenDerivacionDAO
from app.persistencia.daos.mascota_dao import HistoriaClinicaDAO
from app.persistencia.daos.personas_dao import VeterinarioDAO
from app.persistencia.daos.turno_dao import TurnoDAO
from app.servicios.mascota_service import MascotaService
from app.utils import fechas


@dataclass
class SolicitudDerivacion:
    """Datos para emitir una orden de derivación al laboratorio."""
    id_laboratorio: int
    ids_tipo_analisis: list[int]
    prioridad: Prioridad = Prioridad.NORMAL
    indicaciones: str | None = None
    volumenes: dict[TipoMuestra, float] = field(default_factory=dict)


class AtencionService:
    def __init__(self, atenciones: AtencionDAO, historias: HistoriaClinicaDAO, mascotas: MascotaService,
                 veterinarios: VeterinarioDAO, turnos: TurnoDAO, vacunas: VacunaDAO, esquemas: VacunaObligatoriaDAO,
                 ordenes: OrdenDerivacionDAO, tipos_analisis: TipoAnalisisDAO, laboratorios: LaboratorioDAO,
                 conexion: ConexionBD):
        self._atenciones = atenciones
        self._historias = historias
        self._mascotas = mascotas
        self._veterinarios = veterinarios
        self._turnos = turnos
        self._vacunas = vacunas
        self._esquemas = esquemas
        self._ordenes = ordenes
        self._tipos = tipos_analisis
        self._laboratorios = laboratorios
        self._conexion = conexion

    # --- Control del esquema de vacunas ------------------------------------------------
    def vacunas_pendientes(self, id_mascota: int, fecha: date | None = None) -> list[VacunaObligatoria]:
        return self._mascotas.obtener(id_mascota).vacunas_pendientes(fecha or date.today())

    def esquema_de(self, mascota: Mascota) -> list[VacunaObligatoria]:
        return mascota.especie.esquema if mascota.especie else []

    # --- Registro de la atención ---------------------------------------------------------
    def registrar(self, *, id_mascota: int, id_veterinario: int, id_clinica: int, tipo: TipoAtencion, motivo: str,
                  fecha_hora: datetime | None = None, id_turno: int | None = None, anamnesis: str | None = None,
                  diagnostico: str | None = None, peso_registrado_kg: float | None = None,
                  tratamientos: list[Tratamiento] = (), vacunas: list[tuple[int, str]] = (),
                  derivacion: SolicitudDerivacion | None = None,
                  confirmar_esquema_incompleto: bool = False) -> Atencion:
        """Registra la atención con sus tratamientos, vacunas aplicadas y (opcionalmente) una orden de derivación.

        Controla el esquema de vacunas obligatorias: si quedan vacunas pendientes lanza
        EsquemaVacunasIncompletoError, salvo que el veterinario confirme registrar igualmente.
        """
        mascota = self._mascotas.obtener(id_mascota)
        historia = self._historias.obtener_por_mascota(id_mascota)
        veterinario = self._veterinarios.obtener_por_id(id_veterinario)
        if veterinario is None:
            raise EntidadNoEncontradaError("el veterinario", id_veterinario)
        if not veterinario.trabaja_en(id_clinica):
            raise ValidacionError(f"{veterinario.nombre_completo()} no atiende en la clínica seleccionada.")
        turno = self._turno_a_atender(id_turno, id_mascota, id_veterinario)

        atencion = Atencion(id_historia=historia.id, id_veterinario=id_veterinario, id_clinica=id_clinica,
                            id_turno=id_turno, fecha_hora=fecha_hora or fechas.ahora(), tipo=TipoAtencion(tipo),
                            motivo=motivo, anamnesis=anamnesis, diagnostico=diagnostico,
                            peso_registrado_kg=peso_registrado_kg)
        atencion.validar()
        for tratamiento in tratamientos:
            atencion.agregar_tratamiento(tratamiento)
        for id_vacuna, lote in vacunas:
            vacuna = self._vacunas.obtener_por_id(id_vacuna)
            if vacuna is None:
                raise EntidadNoEncontradaError("la vacuna", id_vacuna)
            atencion.aplicar_vacuna(vacuna, lote, self._esquemas.obtener(mascota.id_especie, id_vacuna))

        atencion.vacunas_pendientes = atencion.validar_esquema_vacunas(mascota)
        if atencion.vacunas_pendientes and not confirmar_esquema_incompleto:
            raise EsquemaVacunasIncompletoError(atencion.vacunas_pendientes)

        with self._conexion.transaccion():
            self._atenciones.insertar(atencion)
            if turno:
                turno.marcar_atendido()
                self._turnos.actualizar_estado(turno)
            if peso_registrado_kg:
                mascota.peso_kg = peso_registrado_kg
                self._mascotas.modificar(mascota)
            if derivacion:
                self._emitir_orden(atencion, derivacion, veterinario.nombre_completo(), atencion.fecha_hora)
        return atencion

    def _turno_a_atender(self, id_turno: int | None, id_mascota: int, id_veterinario: int):
        if id_turno is None:
            return None
        turno = self._turnos.obtener_por_id(id_turno)
        if turno is None:
            raise EntidadNoEncontradaError("el turno", id_turno)
        if turno.estado != EstadoTurno.RESERVADO:
            raise ValidacionError("El turno seleccionado no está pendiente de atención.")
        if turno.id_mascota != id_mascota or turno.id_veterinario != id_veterinario:
            raise ValidacionError("El turno corresponde a otra mascota o a otro veterinario.")
        return turno

    # --- Órdenes de derivación ---------------------------------------------------------------
    def emitir_orden(self, id_atencion: int, solicitud: SolicitudDerivacion,
                     fecha_hora: datetime | None = None) -> OrdenDerivacion:
        atencion = self.obtener(id_atencion)
        veterinario = self._veterinarios.obtener_por_id(atencion.id_veterinario)
        with self._conexion.transaccion():
            return self._emitir_orden(atencion, solicitud, veterinario.nombre_completo(), fecha_hora or fechas.ahora())

    def _emitir_orden(self, atencion: Atencion, solicitud: SolicitudDerivacion, responsable: str,
                      fecha_hora: datetime) -> OrdenDerivacion:
        if self._laboratorios.obtener_por_id(solicitud.id_laboratorio) is None:
            raise ValidacionError("Debe seleccionar el laboratorio de destino.")
        tipos = [self._tipos.obtener_por_id(id_tipo) for id_tipo in solicitud.ids_tipo_analisis]
        if None in tipos:
            raise ValidacionError("Alguno de los análisis seleccionados no existe.")
        orden = atencion.emitir_orden_derivacion(
            id_laboratorio=solicitud.id_laboratorio, analisis=tipos, numero=self._ordenes.siguiente_numero(fecha_hora.year),
            responsable=responsable, prioridad=solicitud.prioridad, indicaciones=solicitud.indicaciones,
            volumenes=solicitud.volumenes, fecha_hora=fecha_hora)
        self._ordenes.insertar(orden)
        return orden

    # --- Consultas -----------------------------------------------------------------------------
    def obtener(self, id_atencion: int) -> Atencion:
        atencion = self._atenciones.obtener_por_id(id_atencion)
        if atencion is None:
            raise EntidadNoEncontradaError("la atención", id_atencion)
        atencion.ordenes = self._ordenes.listar_por_atencion(id_atencion)
        return atencion

    def resumen(self, id_atencion: int) -> dict:
        return self._atenciones.resumen_de(id_atencion)

    def ordenes_de(self, id_atencion: int) -> list[dict]:
        return self._ordenes.resumen_de_atencion(id_atencion)

    def listar(self, desde: date | None = None, hasta: date | None = None, id_clinica: int | None = None,
               texto: str = "") -> list[dict]:
        return self._atenciones.listar_resumen(desde, hasta, id_clinica, texto)
