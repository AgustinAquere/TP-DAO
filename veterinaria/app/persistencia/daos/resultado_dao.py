"""DAO de resultados de análisis con sus valores informados (detalle_resultado)."""
from app.dominio.laboratorio import DetalleResultado, ResultadoAnalisis
from app.persistencia.daos.base_dao import BaseDAO
from app.utils import fechas


class ResultadoDAO(BaseDAO[ResultadoAnalisis]):
    tabla, clave = "resultado_analisis", "id_resultado"
    columnas = ("id_analisis_solicitado", "id_bioquimico", "fecha_hora", "interpretacion", "observaciones")
    orden = "fecha_hora DESC"

    def _a_entidad(self, fila) -> ResultadoAnalisis:
        resultado = ResultadoAnalisis(id=fila["id_resultado"], id_analisis_solicitado=fila["id_analisis_solicitado"],
                                      id_bioquimico=fila["id_bioquimico"],
                                      fecha_hora=fechas.fecha_hora_desde_sql(fila["fecha_hora"]),
                                      interpretacion=fila["interpretacion"], observaciones=fila["observaciones"])
        resultado.detalles = [
            DetalleResultado(id=f["id_detalle"], id_resultado=f["id_resultado"], parametro=f["parametro"],
                             valor=f["valor"], unidad=f["unidad"], valor_ref_min=f["valor_ref_min"],
                             valor_ref_max=f["valor_ref_max"])
            for f in self.conexion.consultar("SELECT * FROM detalle_resultado WHERE id_resultado = ? ORDER BY id_detalle",
                                             (resultado.id,))]
        return resultado

    def _a_registro(self, r: ResultadoAnalisis) -> tuple:
        return (r.id_analisis_solicitado, r.id_bioquimico, fechas.a_sql(r.fecha_hora), r.interpretacion,
                r.observaciones)

    def insertar(self, resultado: ResultadoAnalisis) -> int:
        with self.conexion.transaccion():
            super().insertar(resultado)
            for detalle in resultado.detalles:
                detalle.id_resultado = resultado.id
                detalle.id = self.conexion.ejecutar("""
                    INSERT INTO detalle_resultado (id_resultado, parametro, valor, unidad, valor_ref_min, valor_ref_max)
                    VALUES (?, ?, ?, ?, ?, ?)""", (resultado.id, detalle.parametro.strip(), detalle.valor, detalle.unidad,
                                                   detalle.valor_ref_min, detalle.valor_ref_max)).lastrowid
        return resultado.id

    def obtener_por_analisis(self, id_analisis_solicitado: int) -> ResultadoAnalisis | None:
        return self._obtener_donde("id_analisis_solicitado = ?", (id_analisis_solicitado,))

    def analisis_pendientes(self, id_laboratorio: int | None = None) -> list[dict]:
        """Análisis cuya muestra fue recibida y todavía no tienen resultado."""
        filtro = "AND o.id_laboratorio = ?" if id_laboratorio else ""
        return self._diccionarios(f"""
            SELECT an.id_analisis_solicitado, ta.codigo, ta.nombre AS analisis, o.numero AS orden, o.prioridad,
                   mu.codigo AS muestra, mu.tipo AS tipo_muestra, m.nombre AS mascota, e.nombre AS especie,
                   (SELECT MAX(ce.fecha_hora) FROM cambio_estado_muestra ce
                     WHERE ce.id_muestra = mu.id_muestra AND ce.estado_nuevo = 'RECIBIDA') AS recibida
              FROM analisis_solicitado an
              JOIN tipo_analisis ta ON ta.id_tipo_analisis = an.id_tipo_analisis
              JOIN orden_derivacion o ON o.id_orden = an.id_orden
              JOIN muestra mu ON mu.id_muestra = an.id_muestra
              JOIN atencion a ON a.id_atencion = o.id_atencion
              JOIN historia_clinica h ON h.id_historia = a.id_historia
              JOIN mascota m ON m.id_mascota = h.id_mascota
              JOIN especie e ON e.id_especie = m.id_especie
             WHERE mu.estado = 'RECIBIDA'
               AND NOT EXISTS (SELECT 1 FROM resultado_analisis r WHERE r.id_analisis_solicitado = an.id_analisis_solicitado)
               {filtro}
             ORDER BY o.prioridad DESC, recibida""", (id_laboratorio,) if id_laboratorio else ())

    def listar_resumen(self, id_laboratorio: int | None = None, texto: str = "") -> list[dict]:
        patron = f"%{texto.strip()}%"
        filtro = "AND o.id_laboratorio = ?" if id_laboratorio else ""
        return self._diccionarios(f"""
            SELECT r.*, ta.nombre AS analisis, o.numero AS orden, mu.codigo AS muestra, m.nombre AS mascota,
                   b.apellido || ', ' || b.nombre AS bioquimico,
                   (SELECT COUNT(*) FROM detalle_resultado d WHERE d.id_resultado = r.id_resultado
                       AND ((d.valor_ref_min IS NOT NULL AND d.valor < d.valor_ref_min)
                         OR (d.valor_ref_max IS NOT NULL AND d.valor > d.valor_ref_max))) AS fuera_de_rango
              FROM resultado_analisis r
              JOIN analisis_solicitado an ON an.id_analisis_solicitado = r.id_analisis_solicitado
              JOIN tipo_analisis ta ON ta.id_tipo_analisis = an.id_tipo_analisis
              JOIN orden_derivacion o ON o.id_orden = an.id_orden
              JOIN muestra mu ON mu.id_muestra = an.id_muestra
              JOIN atencion a ON a.id_atencion = o.id_atencion
              JOIN historia_clinica h ON h.id_historia = a.id_historia
              JOIN mascota m ON m.id_mascota = h.id_mascota
              JOIN bioquimico b ON b.id_bioquimico = r.id_bioquimico
             WHERE (o.numero LIKE ? OR m.nombre LIKE ? OR ta.nombre LIKE ?) {filtro}
             ORDER BY r.fecha_hora DESC""", (patron, patron, patron) + ((id_laboratorio,) if id_laboratorio else ()))
