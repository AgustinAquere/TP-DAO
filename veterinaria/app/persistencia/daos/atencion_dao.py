"""DAO de atenciones; guarda también sus tratamientos y vacunas aplicadas (composición)."""
from datetime import date

from app.dominio.atencion import Atencion, Tratamiento
from app.dominio.enums import TipoAtencion
from app.dominio.vacunas import AplicacionVacuna
from app.persistencia.daos.base_dao import BaseDAO
from app.utils import fechas

_SELECT_RESUMEN = """
    SELECT a.*, m.id_mascota, m.nombre AS mascota, e.nombre AS especie,
           c.id_cliente, c.apellido || ', ' || c.nombre AS responsable,
           v.apellido || ', ' || v.nombre AS veterinario, cl.nombre AS clinica,
           (SELECT COUNT(*) FROM orden_derivacion o WHERE o.id_atencion = a.id_atencion) AS cantidad_ordenes,
           (SELECT GROUP_CONCAT(o.numero, ', ') FROM orden_derivacion o WHERE o.id_atencion = a.id_atencion) AS ordenes,
           (SELECT cp.numero FROM comprobante_atencion cp WHERE cp.id_atencion = a.id_atencion) AS comprobante
      FROM atencion a
      JOIN historia_clinica h ON h.id_historia = a.id_historia
      JOIN mascota m ON m.id_mascota = h.id_mascota
      JOIN especie e ON e.id_especie = m.id_especie
      JOIN cliente c ON c.id_cliente = m.id_cliente
      JOIN veterinario v ON v.id_veterinario = a.id_veterinario
      JOIN clinica cl ON cl.id_clinica = a.id_clinica"""


class AtencionDAO(BaseDAO[Atencion]):
    tabla, clave = "atencion", "id_atencion"
    columnas = ("id_historia", "id_veterinario", "id_clinica", "id_turno", "fecha_hora", "tipo", "motivo",
                "anamnesis", "diagnostico", "peso_registrado_kg")
    orden = "fecha_hora DESC"

    def _a_entidad(self, fila) -> Atencion:
        atencion = Atencion(id=fila["id_atencion"], id_historia=fila["id_historia"],
                            id_veterinario=fila["id_veterinario"], id_clinica=fila["id_clinica"],
                            id_turno=fila["id_turno"], fecha_hora=fechas.fecha_hora_desde_sql(fila["fecha_hora"]),
                            tipo=TipoAtencion(fila["tipo"]), motivo=fila["motivo"], anamnesis=fila["anamnesis"],
                            diagnostico=fila["diagnostico"], peso_registrado_kg=fila["peso_registrado_kg"])
        atencion.tratamientos = self.tratamientos_de(atencion.id)
        atencion.aplicaciones = self.aplicaciones_de(atencion.id)
        return atencion

    def _a_registro(self, a: Atencion) -> tuple:
        return (a.id_historia, a.id_veterinario, a.id_clinica, a.id_turno, fechas.a_sql(a.fecha_hora),
                TipoAtencion(a.tipo).value, a.motivo.strip(), a.anamnesis, a.diagnostico, a.peso_registrado_kg)

    def insertar(self, a: Atencion) -> int:
        with self.conexion.transaccion():
            super().insertar(a)
            for tratamiento in a.tratamientos:
                tratamiento.id_atencion = a.id
                self._insertar_tratamiento(tratamiento)
            for aplicacion in a.aplicaciones:
                aplicacion.id_atencion = a.id
                self._insertar_aplicacion(aplicacion)
        return a.id

    # --- Tratamientos ----------------------------------------------------------
    def _insertar_tratamiento(self, t: Tratamiento) -> None:
        t.id = self.conexion.ejecutar("""
            INSERT INTO tratamiento (id_atencion, descripcion, medicamento, dosis, frecuencia, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (t.id_atencion, t.descripcion.strip(), t.medicamento, t.dosis,
                                              t.frecuencia, fechas.a_sql(t.fecha_inicio),
                                              fechas.a_sql(t.fecha_fin))).lastrowid

    def tratamientos_de(self, id_atencion: int) -> list[Tratamiento]:
        filas = self.conexion.consultar("SELECT * FROM tratamiento WHERE id_atencion = ? ORDER BY id_tratamiento",
                                        (id_atencion,))
        return [Tratamiento(id=f["id_tratamiento"], id_atencion=f["id_atencion"], descripcion=f["descripcion"],
                            medicamento=f["medicamento"], dosis=f["dosis"], frecuencia=f["frecuencia"],
                            fecha_inicio=fechas.fecha_desde_sql(f["fecha_inicio"]),
                            fecha_fin=fechas.fecha_desde_sql(f["fecha_fin"])) for f in filas]

    # --- Vacunas aplicadas -----------------------------------------------------
    def _insertar_aplicacion(self, ap: AplicacionVacuna) -> None:
        ap.id = self.conexion.ejecutar("""
            INSERT INTO aplicacion_vacuna (id_atencion, id_vacuna, fecha, lote, fecha_proxima_dosis)
            VALUES (?, ?, ?, ?, ?)""", (ap.id_atencion, ap.id_vacuna, fechas.a_sql(ap.fecha), ap.lote,
                                        fechas.a_sql(ap.fecha_proxima_dosis))).lastrowid

    @staticmethod
    def _a_aplicacion(f) -> AplicacionVacuna:
        return AplicacionVacuna(id=f["id_aplicacion"], id_atencion=f["id_atencion"], id_vacuna=f["id_vacuna"],
                                fecha=fechas.fecha_desde_sql(f["fecha"]), lote=f["lote"],
                                fecha_proxima_dosis=fechas.fecha_desde_sql(f["fecha_proxima_dosis"]),
                                nombre_vacuna=f["nombre_vacuna"])

    def aplicaciones_de(self, id_atencion: int) -> list[AplicacionVacuna]:
        filas = self.conexion.consultar("""
            SELECT ap.*, v.nombre AS nombre_vacuna FROM aplicacion_vacuna ap JOIN vacuna v ON v.id_vacuna = ap.id_vacuna
             WHERE ap.id_atencion = ? ORDER BY ap.id_aplicacion""", (id_atencion,))
        return list(map(self._a_aplicacion, filas))

    def aplicaciones_de_mascota(self, id_mascota: int) -> list[AplicacionVacuna]:
        filas = self.conexion.consultar("""
            SELECT ap.*, v.nombre AS nombre_vacuna
              FROM aplicacion_vacuna ap
              JOIN vacuna v ON v.id_vacuna = ap.id_vacuna
              JOIN atencion a ON a.id_atencion = ap.id_atencion
              JOIN historia_clinica h ON h.id_historia = a.id_historia
             WHERE h.id_mascota = ? ORDER BY ap.fecha""", (id_mascota,))
        return list(map(self._a_aplicacion, filas))

    # --- Consultas -------------------------------------------------------------
    def listar_por_historia(self, id_historia: int) -> list[Atencion]:
        return self._listar_donde("id_historia = ?", (id_historia,))

    def listar_resumen(self, desde: date | None = None, hasta: date | None = None, id_clinica: int | None = None,
                       texto: str = "", sin_comprobante: bool = False) -> list[dict]:
        condiciones, parametros = ["(m.nombre LIKE ? OR c.apellido LIKE ? OR IFNULL(a.diagnostico, '') LIKE ?)"], []
        patron = f"%{texto.strip()}%"
        parametros += [patron, patron, patron]
        if desde:
            condiciones.append("date(a.fecha_hora) >= ?")
            parametros.append(fechas.a_sql(desde))
        if hasta:
            condiciones.append("date(a.fecha_hora) <= ?")
            parametros.append(fechas.a_sql(hasta))
        if id_clinica:
            condiciones.append("a.id_clinica = ?")
            parametros.append(id_clinica)
        if sin_comprobante:
            condiciones.append("NOT EXISTS (SELECT 1 FROM comprobante_atencion cp WHERE cp.id_atencion = a.id_atencion)")
        return self._diccionarios(f"{_SELECT_RESUMEN} WHERE {' AND '.join(condiciones)} ORDER BY a.fecha_hora DESC",
                                  tuple(parametros))

    def resumen_de(self, id_atencion: int) -> dict | None:
        filas = self._diccionarios(f"{_SELECT_RESUMEN} WHERE a.id_atencion = ?", (id_atencion,))
        return filas[0] if filas else None

    def id_cliente_de(self, id_atencion: int) -> int | None:
        return self.conexion.valor("""
            SELECT m.id_cliente FROM atencion a
              JOIN historia_clinica h ON h.id_historia = a.id_historia
              JOIN mascota m ON m.id_mascota = h.id_mascota
             WHERE a.id_atencion = ?""", (id_atencion,))
