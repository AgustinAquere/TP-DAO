"""Agenda médica: reserva de turnos sin superposición para cada veterinario."""
from datetime import date, datetime

from app.dominio.enums import EstadoTurno
from app.dominio.excepciones import EntidadNoEncontradaError, ErrorPersistencia, TurnoSuperpuestoError, ValidacionError
from app.dominio.turnos import Agenda, Turno
from app.persistencia.daos.mascota_dao import MascotaDAO
from app.persistencia.daos.personas_dao import VeterinarioDAO
from app.persistencia.daos.turno_dao import TurnoDAO
from app.utils import fechas


class TurnoService:
    def __init__(self, turnos: TurnoDAO, veterinarios: VeterinarioDAO, mascotas: MascotaDAO):
        self._turnos = turnos
        self._veterinarios = veterinarios
        self._mascotas = mascotas

    def agenda(self, id_veterinario: int, fecha: date) -> Agenda:
        return Agenda(id_veterinario, fecha, self._turnos.turnos_de(id_veterinario, fecha))

    def reservar(self, id_veterinario: int, id_mascota: int, id_clinica: int, inicio: datetime, duracion: int,
                 ahora: datetime | None = None) -> Turno:
        veterinario = self._veterinarios.obtener_por_id(id_veterinario)
        if veterinario is None:
            raise EntidadNoEncontradaError("el veterinario", id_veterinario)
        if not veterinario.trabaja_en(id_clinica):
            raise ValidacionError(f"{veterinario.nombre_completo()} no atiende en la clínica seleccionada.")
        if self._mascotas.obtener_por_id(id_mascota) is None:
            raise EntidadNoEncontradaError("la mascota", id_mascota)
        if inicio < (ahora or fechas.ahora()):
            raise ValidacionError("No se pueden reservar turnos en el pasado.")
        turno = self.agenda(id_veterinario, inicio.date()).reservar(id_mascota, id_clinica, inicio, duracion)
        try:
            self._turnos.insertar(turno)
        except ErrorPersistencia as error:  # el trigger de la base es la última barrera ante reservas simultáneas
            if "superpone" in str(error):
                raise TurnoSuperpuestoError(str(error)) from error
            raise
        return turno

    def _obtener(self, id_turno: int) -> Turno:
        turno = self._turnos.obtener_por_id(id_turno)
        if turno is None:
            raise EntidadNoEncontradaError("el turno", id_turno)
        return turno

    def cancelar(self, id_turno: int) -> None:
        turno = self._obtener(id_turno)
        turno.cancelar()
        self._turnos.actualizar_estado(turno)

    def marcar_ausente(self, id_turno: int) -> None:
        turno = self._obtener(id_turno)
        turno.marcar_ausente()
        self._turnos.actualizar_estado(turno)

    def horarios_disponibles(self, id_veterinario: int, fecha: date, duracion: int) -> list[datetime]:
        desde = fechas.ahora() if fecha == date.today() else None
        return self.agenda(id_veterinario, fecha).turnos_disponibles(duracion, desde)

    def listar(self, fecha: date | None = None, id_veterinario: int | None = None,
               estado: EstadoTurno | None = None, id_mascota: int | None = None) -> list[dict]:
        return self._turnos.listar_resumen(fecha, id_veterinario, estado, id_mascota)

    def pendientes_de_atencion(self, fecha: date | None = None) -> list[dict]:
        return self._turnos.listar_resumen(fecha or date.today(), estado=EstadoTurno.RESERVADO)
