"""DAO de turnos. La Agenda del dominio se arma con los turnos de un veterinario en una fecha."""
from datetime import date

from app.dominio.enums import EstadoTurno
from app.dominio.turnos import Turno
from app.persistencia.daos.base_dao import BaseDAO
from app.utils import fechas

_SELECT_RESUMEN = """
    SELECT t.*, m.nombre AS mascota, c.apellido || ', ' || c.nombre AS responsable, c.telefono,
           cl.nombre AS clinica, v.apellido || ', ' || v.nombre AS veterinario,
           datetime(t.fecha_hora_inicio, '+' || t.duracion_min || ' minutes') AS fecha_hora_fin
      FROM turno t
      JOIN mascota m ON m.id_mascota = t.id_mascota
      JOIN cliente c ON c.id_cliente = m.id_cliente
      JOIN clinica cl ON cl.id_clinica = t.id_clinica
      JOIN veterinario v ON v.id_veterinario = t.id_veterinario"""


class TurnoDAO(BaseDAO[Turno]):
    tabla, clave = "turno", "id_turno"
    columnas = ("id_veterinario", "id_mascota", "id_clinica", "fecha_hora_inicio", "duracion_min", "estado")
    orden = "fecha_hora_inicio"

    def _a_entidad(self, fila) -> Turno:
        return Turno(id=fila["id_turno"], id_veterinario=fila["id_veterinario"], id_mascota=fila["id_mascota"],
                     id_clinica=fila["id_clinica"], fecha_hora_inicio=fechas.fecha_hora_desde_sql(fila["fecha_hora_inicio"]),
                     duracion_min=fila["duracion_min"], estado=EstadoTurno(fila["estado"]))

    def _a_registro(self, t: Turno) -> tuple:
        return (t.id_veterinario, t.id_mascota, t.id_clinica, fechas.a_sql(t.fecha_hora_inicio), t.duracion_min,
                EstadoTurno(t.estado).value)

    def turnos_de(self, id_veterinario: int, fecha: date) -> list[Turno]:
        return self._listar_donde("id_veterinario = ? AND date(fecha_hora_inicio) = ?",
                                  (id_veterinario, fechas.a_sql(fecha)))

    def actualizar_estado(self, turno: Turno) -> None:
        self.conexion.ejecutar("UPDATE turno SET estado = ? WHERE id_turno = ?", (turno.estado.value, turno.id))

    def listar_resumen(self, fecha: date | None = None, id_veterinario: int | None = None,
                       estado: EstadoTurno | None = None, id_mascota: int | None = None) -> list[dict]:
        condiciones, parametros = ["1 = 1"], []
        filtros = [
            (fecha, "date(t.fecha_hora_inicio) = ?", fechas.a_sql(fecha)),
            (id_veterinario, "t.id_veterinario = ?", id_veterinario),
            (estado, "t.estado = ?", getattr(estado, "value", estado)),
            (id_mascota, "t.id_mascota = ?", id_mascota),
        ]
        for valor, condicion, parametro in filtros:
            if valor:
                condiciones.append(condicion)
                parametros.append(parametro)
        return self._diccionarios(f"{_SELECT_RESUMEN} WHERE {' AND '.join(condiciones)} ORDER BY t.fecha_hora_inicio",
                                  tuple(parametros))
