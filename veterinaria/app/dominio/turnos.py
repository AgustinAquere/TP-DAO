"""Turnos y agenda diaria de un veterinario (validación de superposición)."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app import config
from app.dominio.enums import EstadoTurno
from app.dominio.excepciones import TransicionInvalidaError, TurnoSuperpuestoError, ValidacionError
from app.utils import validaciones as v


@dataclass(kw_only=True)
class Turno:
    id_veterinario: int
    id_mascota: int
    id_clinica: int
    fecha_hora_inicio: datetime
    duracion_min: int
    estado: EstadoTurno = EstadoTurno.RESERVADO
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [(lambda t: t.duracion_min > 0, "La duración del turno debe ser mayor a cero.")])

    def fecha_hora_fin(self) -> datetime:
        return self.fecha_hora_inicio + timedelta(minutes=self.duracion_min)

    def esta_activo(self) -> bool:
        return self.estado != EstadoTurno.CANCELADO

    def se_superpone_con(self, otro: "Turno") -> bool:
        """Dos turnos activos del mismo veterinario se superponen si sus intervalos se intersecan."""
        if self is otro or (self.id is not None and self.id == otro.id):
            return False
        if not (self.esta_activo() and otro.esta_activo()) or self.id_veterinario != otro.id_veterinario:
            return False
        return self.fecha_hora_inicio < otro.fecha_hora_fin() and otro.fecha_hora_inicio < self.fecha_hora_fin()

    def _cambiar_estado(self, nuevo: EstadoTurno) -> None:
        if self.estado != EstadoTurno.RESERVADO:
            raise TransicionInvalidaError(f"El turno ya está {self.estado.value.lower()}; no puede pasar a {nuevo.value.lower()}.")
        self.estado = nuevo

    def cancelar(self) -> None:
        self._cambiar_estado(EstadoTurno.CANCELADO)

    def marcar_atendido(self) -> None:
        self._cambiar_estado(EstadoTurno.ATENDIDO)

    def marcar_ausente(self) -> None:
        self._cambiar_estado(EstadoTurno.AUSENTE)


class Agenda:
    """Turnos de un veterinario en una fecha. No se persiste: es una vista sobre la tabla turno."""

    def __init__(self, id_veterinario: int, fecha: date, turnos: list[Turno]):
        self.id_veterinario = id_veterinario
        self.fecha = fecha
        self._turnos = sorted(turnos, key=lambda t: t.fecha_hora_inicio)

    def __iter__(self):
        return iter(self._turnos)

    def __len__(self) -> int:
        return len(self._turnos)

    def turnos_activos(self) -> list[Turno]:
        return [t for t in self._turnos if t.esta_activo()]

    def _inicio_jornada(self) -> datetime:
        return datetime.combine(self.fecha, config.JORNADA_INICIO)

    def _fin_jornada(self) -> datetime:
        return datetime.combine(self.fecha, config.JORNADA_FIN)

    def reservar(self, id_mascota: int, id_clinica: int, inicio: datetime, duracion: int) -> Turno:
        nuevo = Turno(id_veterinario=self.id_veterinario, id_mascota=id_mascota, id_clinica=id_clinica,
                      fecha_hora_inicio=inicio, duracion_min=duracion)
        nuevo.validar()
        if inicio.date() != self.fecha:
            raise ValidacionError("El turno no corresponde a la fecha de la agenda.")
        if inicio < self._inicio_jornada() or nuevo.fecha_hora_fin() > self._fin_jornada():
            raise ValidacionError(
                f"El turno debe estar dentro de la jornada ({config.JORNADA_INICIO:%H:%M} a {config.JORNADA_FIN:%H:%M}).")
        conflicto = next((t for t in self._turnos if nuevo.se_superpone_con(t)), None)
        if conflicto:
            raise TurnoSuperpuestoError(
                f"El turno se superpone con otro del veterinario "
                f"({conflicto.fecha_hora_inicio:%H:%M} a {conflicto.fecha_hora_fin():%H:%M}).")
        self._turnos.append(nuevo)
        self._turnos.sort(key=lambda t: t.fecha_hora_inicio)
        return nuevo

    def turnos_disponibles(self, duracion: int = config.INTERVALO_TURNOS_MIN,
                           desde: datetime | None = None) -> list[datetime]:
        """Horarios de inicio libres en la jornada, cada INTERVALO_TURNOS_MIN minutos."""
        paso = timedelta(minutes=config.INTERVALO_TURNOS_MIN)
        candidatos, hora = [], self._inicio_jornada()
        while hora + timedelta(minutes=duracion) <= self._fin_jornada():
            candidatos.append(hora)
            hora += paso

        def libre(inicio: datetime) -> bool:
            prueba = Turno(id_veterinario=self.id_veterinario, id_mascota=0, id_clinica=0,
                           fecha_hora_inicio=inicio, duracion_min=duracion)
            return not any(prueba.se_superpone_con(t) for t in self._turnos)

        return [h for h in filter(libre, candidatos) if desde is None or h >= desde]
