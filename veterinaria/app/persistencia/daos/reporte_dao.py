"""Consultas de solo lectura para los reportes y el tablero de inicio."""
from datetime import date

from app.persistencia.conexion import ConexionBD
from app.utils import fechas

# Columnas por las que se permite agrupar (lista blanca: evita inyección SQL en el GROUP BY)
AGRUPACIONES_ATENCIONES = {"clinica": "clinica", "veterinario": "veterinario", "tipo": "tipo", "especie": "especie"}
AGRUPACIONES_TIEMPOS = {"tipo_muestra": "tipo", "laboratorio": "laboratorio", "clinica": "clinica",
                        "transportista": "transportista"}


class ReporteDAO:
    def __init__(self, conexion: ConexionBD | None = None):
        self.conexion = conexion or ConexionBD.obtener_instancia()

    def consulta(self, sql: str, parametros: tuple = ()) -> list[dict]:
        return [dict(fila) for fila in self.conexion.consultar(sql, parametros)]

    @staticmethod
    def _periodo(desde: date, hasta: date) -> tuple[str, str]:
        return fechas.a_sql(desde), fechas.a_sql(hasta)

    # --- 1. Atenciones clínicas y derivaciones -------------------------------------
    def atenciones_y_derivaciones(self, desde: date, hasta: date, agrupar_por: str) -> list[dict]:
        grupo = AGRUPACIONES_ATENCIONES[agrupar_por]
        return self.consulta(f"""
            WITH base AS (
                SELECT a.id_atencion, a.tipo, cl.nombre AS clinica, v.apellido || ', ' || v.nombre AS veterinario,
                       e.nombre AS especie,
                       (SELECT COUNT(*) FROM orden_derivacion o WHERE o.id_atencion = a.id_atencion) AS ordenes,
                       (SELECT COUNT(*) FROM analisis_solicitado an JOIN orden_derivacion o ON o.id_orden = an.id_orden
                         WHERE o.id_atencion = a.id_atencion) AS analisis
                  FROM atencion a
                  JOIN clinica cl ON cl.id_clinica = a.id_clinica
                  JOIN veterinario v ON v.id_veterinario = a.id_veterinario
                  JOIN historia_clinica h ON h.id_historia = a.id_historia
                  JOIN mascota m ON m.id_mascota = h.id_mascota
                  JOIN especie e ON e.id_especie = m.id_especie
                 WHERE date(a.fecha_hora) BETWEEN ? AND ?)
            SELECT {grupo} AS grupo, COUNT(*) AS atenciones,
                   SUM(tipo = 'CONSULTA') AS consultas, SUM(tipo = 'CONTROL') AS controles,
                   SUM(tipo = 'URGENCIA') AS urgencias, SUM(ordenes > 0) AS con_derivacion,
                   SUM(ordenes) AS ordenes, SUM(analisis) AS analisis
              FROM base GROUP BY {grupo} ORDER BY atenciones DESC, grupo""", self._periodo(desde, hasta))

    def analisis_mas_solicitados(self, desde: date, hasta: date) -> list[dict]:
        return self.consulta("""
            SELECT ta.nombre AS analisis, COUNT(*) AS cantidad
              FROM analisis_solicitado an
              JOIN tipo_analisis ta ON ta.id_tipo_analisis = an.id_tipo_analisis
              JOIN orden_derivacion o ON o.id_orden = an.id_orden
             WHERE date(o.fecha_emision) BETWEEN ? AND ?
             GROUP BY ta.id_tipo_analisis ORDER BY cantidad DESC""", self._periodo(desde, hasta))

    # --- 2. Muestras rechazadas por fallas en el transporte -------------------------
    def muestras_rechazadas_en_recepcion(self, desde: date, hasta: date) -> list[dict]:
        return self.consulta("""
            SELECT mu.codigo, mu.tipo, r.numero AS remito, cl.nombre AS clinica, lab.nombre AS laboratorio,
                   ce.fecha_hora AS fecha_rechazo, ce.observacion AS motivo, ce.responsable,
                   rec.estado_precinto_verificado AS precinto, rec.temperatura_arribo_c,
                   (julianday(ce.fecha_hora) - julianday(mu.fecha_hora_extraccion)) * 24 AS horas_desde_extraccion,
                   (SELECT GROUP_CONCAT(t.razon_social, ' > ' ORDER BY te.nro_orden)
                      FROM tramo_envio te JOIN transportista t ON t.id_transportista = te.id_transportista
                     WHERE te.id_remito = r.id_remito) AS transportistas
              FROM cambio_estado_muestra ce
              JOIN muestra mu ON mu.id_muestra = ce.id_muestra
              JOIN remito_biologico r ON r.id_remito = mu.id_remito
              JOIN clinica cl ON cl.id_clinica = r.id_clinica_origen
              JOIN laboratorio_central lab ON lab.id_laboratorio = r.id_laboratorio_destino
              LEFT JOIN recepcion_laboratorio rec ON rec.id_remito = r.id_remito
             WHERE ce.estado_nuevo = 'RECHAZADA' AND ce.estado_anterior = 'EN_TRANSITO'
               AND date(ce.fecha_hora) BETWEEN ? AND ?
             ORDER BY ce.fecha_hora DESC""", self._periodo(desde, hasta))

    def muestras_evaluadas_en_recepcion(self, desde: date, hasta: date) -> int:
        """Muestras que llegaron al laboratorio en el período (recibidas o rechazadas en la recepción)."""
        return self.conexion.valor("""
            SELECT COUNT(DISTINCT id_muestra) FROM cambio_estado_muestra
             WHERE estado_anterior = 'EN_TRANSITO' AND estado_nuevo IN ('RECIBIDA', 'RECHAZADA')
               AND date(fecha_hora) BETWEEN ? AND ?""", self._periodo(desde, hasta)) or 0

    # --- 3. Tratamientos aplicados y vacunas pendientes ------------------------------
    def tratamientos_en_periodo(self, desde: date, hasta: date) -> list[dict]:
        """Tratamientos vigentes en algún momento del período."""
        return self.consulta("""
            SELECT t.*, a.fecha_hora, m.nombre AS mascota, e.nombre AS especie,
                   c.apellido || ', ' || c.nombre AS cliente, v.apellido || ', ' || v.nombre AS veterinario,
                   cl.nombre AS clinica
              FROM tratamiento t
              JOIN atencion a ON a.id_atencion = t.id_atencion
              JOIN historia_clinica h ON h.id_historia = a.id_historia
              JOIN mascota m ON m.id_mascota = h.id_mascota
              JOIN especie e ON e.id_especie = m.id_especie
              JOIN cliente c ON c.id_cliente = m.id_cliente
              JOIN veterinario v ON v.id_veterinario = a.id_veterinario
              JOIN clinica cl ON cl.id_clinica = a.id_clinica
             WHERE t.fecha_inicio <= ? AND (t.fecha_fin IS NULL OR t.fecha_fin >= ?)
             ORDER BY t.fecha_inicio DESC""", (fechas.a_sql(hasta), fechas.a_sql(desde)))

    def mascotas_de_clientes_activos(self) -> list[dict]:
        return self.consulta("""
            SELECT m.id_mascota, c.apellido || ', ' || c.nombre AS cliente, c.telefono, e.nombre AS especie
              FROM mascota m
              JOIN cliente c ON c.id_cliente = m.id_cliente
              JOIN especie e ON e.id_especie = m.id_especie
             WHERE c.activo = 1""")

    def aplicaciones_de_vacunas(self) -> list[dict]:
        return self.consulta("""
            SELECT h.id_mascota, ap.id_vacuna, ap.fecha, ap.lote
              FROM aplicacion_vacuna ap
              JOIN atencion a ON a.id_atencion = ap.id_atencion
              JOIN historia_clinica h ON h.id_historia = a.id_historia""")

    # --- 4. Facturación por clínica y servicios de laboratorio -----------------------
    def facturacion_por_clinica(self, desde: date, hasta: date) -> list[dict]:
        periodo = self._periodo(desde, hasta)
        return self.consulta("""
            SELECT cl.nombre AS clinica, x.comprobantes, x.subtotal, x.total,
                   IFNULL(y.servicios, 0) AS servicios, IFNULL(y.analisis, 0) AS analisis,
                   IFNULL(y.vacunas, 0) AS vacunas, IFNULL(y.insumos, 0) AS insumos
              FROM clinica cl
              JOIN (SELECT id_clinica, COUNT(*) AS comprobantes, SUM(subtotal) AS subtotal, SUM(total) AS total
                      FROM comprobante_atencion WHERE date(fecha_emision) BETWEEN ? AND ?
                     GROUP BY id_clinica) x ON x.id_clinica = cl.id_clinica
              LEFT JOIN (
                    SELECT cp.id_clinica,
                           SUM(CASE WHEN i.tipo = 'SERVICIO_CLINICO' THEN i.cantidad * i.precio_unitario END) AS servicios,
                           SUM(CASE WHEN i.tipo = 'ANALISIS_LABORATORIO' THEN i.cantidad * i.precio_unitario END) AS analisis,
                           SUM(CASE WHEN i.tipo = 'VACUNA' THEN i.cantidad * i.precio_unitario END) AS vacunas,
                           SUM(CASE WHEN i.tipo = 'INSUMO' THEN i.cantidad * i.precio_unitario END) AS insumos
                      FROM item_comprobante i JOIN comprobante_atencion cp ON cp.id_comprobante = i.id_comprobante
                     WHERE date(cp.fecha_emision) BETWEEN ? AND ?
                     GROUP BY cp.id_clinica) y ON y.id_clinica = cl.id_clinica
             ORDER BY x.total DESC""", periodo + periodo)

    def servicios_laboratorio_facturados(self, desde: date, hasta: date) -> list[dict]:
        return self.consulta("""
            SELECT cl.nombre AS clinica, ta.nombre AS analisis, SUM(i.cantidad) AS cantidad,
                   SUM(i.cantidad * i.precio_unitario) AS importe
              FROM item_comprobante i
              JOIN comprobante_atencion cp ON cp.id_comprobante = i.id_comprobante
              JOIN clinica cl ON cl.id_clinica = cp.id_clinica
              JOIN tipo_analisis ta ON ta.id_tipo_analisis = i.id_tipo_analisis
             WHERE i.tipo = 'ANALISIS_LABORATORIO' AND date(cp.fecha_emision) BETWEEN ? AND ?
             GROUP BY cl.id_clinica, ta.id_tipo_analisis
             ORDER BY cl.nombre, importe DESC""", self._periodo(desde, hasta))

    # --- 5. Tiempos de tránsito y procesamiento ---------------------------------------
    def tiempos_de_muestras(self, desde: date, hasta: date, agrupar_por: str) -> list[dict]:
        grupo = AGRUPACIONES_TIEMPOS[agrupar_por]
        return self.consulta(f"""
            WITH tiempos AS (
                SELECT mu.id_muestra, mu.tipo, lab.nombre AS laboratorio, cl.nombre AS clinica,
                       (SELECT t.razon_social FROM tramo_envio te
                          JOIN transportista t ON t.id_transportista = te.id_transportista
                         WHERE te.id_remito = mu.id_remito AND te.nro_orden = 1) AS transportista,
                       MAX(CASE WHEN ce.estado_nuevo = 'EXTRAIDA' THEN ce.fecha_hora END) AS t_extraida,
                       MAX(CASE WHEN ce.estado_nuevo = 'EN_TRANSITO' THEN ce.fecha_hora END) AS t_transito,
                       MAX(CASE WHEN ce.estado_nuevo = 'RECIBIDA' THEN ce.fecha_hora END) AS t_recibida,
                       MAX(CASE WHEN ce.estado_nuevo = 'ANALIZADA' THEN ce.fecha_hora END) AS t_analizada
                  FROM muestra mu
                  JOIN cambio_estado_muestra ce ON ce.id_muestra = mu.id_muestra
                  JOIN remito_biologico r ON r.id_remito = mu.id_remito
                  JOIN laboratorio_central lab ON lab.id_laboratorio = r.id_laboratorio_destino
                  JOIN clinica cl ON cl.id_clinica = r.id_clinica_origen
                 GROUP BY mu.id_muestra)
            SELECT {grupo} AS grupo, COUNT(*) AS recibidas, COUNT(t_analizada) AS analizadas,
                   AVG((julianday(t_transito) - julianday(t_extraida)) * 24) AS espera_despacho,
                   AVG((julianday(t_recibida) - julianday(t_transito)) * 24) AS transito,
                   MAX((julianday(t_recibida) - julianday(t_transito)) * 24) AS transito_max,
                   AVG((julianday(t_analizada) - julianday(t_recibida)) * 24) AS procesamiento,
                   AVG((julianday(t_analizada) - julianday(t_extraida)) * 24) AS total
              FROM tiempos
             WHERE t_recibida IS NOT NULL AND date(t_recibida) BETWEEN ? AND ?
             GROUP BY {grupo} ORDER BY transito DESC""", self._periodo(desde, hasta))

    # --- Tablero de inicio ------------------------------------------------------------
    def indicadores_tablero(self, hoy: date) -> dict:
        dia, mes = fechas.a_sql(hoy), f"{hoy:%Y-%m}"
        consultas = {
            "clientes": ("SELECT COUNT(*) FROM cliente WHERE activo = 1", ()),
            "mascotas": ("SELECT COUNT(*) FROM mascota", ()),
            "turnos_hoy": ("SELECT COUNT(*) FROM turno WHERE date(fecha_hora_inicio) = ? AND estado = 'RESERVADO'",
                           (dia,)),
            "atenciones_mes": ("SELECT COUNT(*) FROM atencion WHERE strftime('%Y-%m', fecha_hora) = ?", (mes,)),
            "muestras_por_empaquetar": (
                "SELECT COUNT(*) FROM muestra WHERE estado = 'EXTRAIDA' AND id_remito IS NULL", ()),
            "remitos_en_transito": ("SELECT COUNT(*) FROM remito_biologico WHERE estado = 'EN_TRANSITO'", ()),
            "analisis_pendientes": ("""
                SELECT COUNT(*) FROM analisis_solicitado an JOIN muestra mu ON mu.id_muestra = an.id_muestra
                 WHERE mu.estado = 'RECIBIDA' AND NOT EXISTS (
                       SELECT 1 FROM resultado_analisis r WHERE r.id_analisis_solicitado = an.id_analisis_solicitado)""",
                                    ()),
            "atenciones_sin_facturar": ("""
                SELECT COUNT(*) FROM atencion a WHERE NOT EXISTS (
                       SELECT 1 FROM comprobante_atencion cp WHERE cp.id_atencion = a.id_atencion)""", ()),
            "facturado_mes": ("SELECT IFNULL(SUM(total), 0) FROM comprobante_atencion "
                              "WHERE strftime('%Y-%m', fecha_emision) = ?", (mes,)),
        }
        return {clave: self.conexion.valor(sql, parametros) for clave, (sql, parametros) in consultas.items()}
