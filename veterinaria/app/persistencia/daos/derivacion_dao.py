"""DAO de muestras (con su historial inmutable) y de órdenes de derivación con sus análisis solicitados."""
from app.dominio.derivacion import AnalisisSolicitado, OrdenDerivacion
from app.dominio.enums import EstadoOrden, Prioridad, TipoMuestra
from app.dominio.estados_muestra import estado_muestra_desde
from app.dominio.historial import CambioEstado, HistorialEstados
from app.dominio.muestra import Muestra
from app.persistencia.daos.base_dao import BaseDAO
from app.persistencia.daos.catalogos_dao import TipoAnalisisDAO
from app.utils import fechas

# Datos de la muestra que se repiten en los listados (orden, laboratorio, mascota, requisitos de conservación)
_SELECT_MUESTRA_RESUMEN = """
    SELECT mu.*, o.numero AS orden, o.prioridad, o.id_laboratorio, lab.nombre AS laboratorio,
           a.id_clinica, cl.nombre AS clinica, m.nombre AS mascota, r.numero AS remito,
           GROUP_CONCAT(ta.nombre, ', ') AS analisis,
           MAX(ta.temp_min_c) AS temp_min_requerida, MIN(ta.temp_max_c) AS temp_max_requerida,
           MIN(ta.horas_max_viabilidad) AS horas_max_viabilidad
      FROM muestra mu
      JOIN orden_derivacion o ON o.id_orden = mu.id_orden
      JOIN laboratorio_central lab ON lab.id_laboratorio = o.id_laboratorio
      JOIN atencion a ON a.id_atencion = o.id_atencion
      JOIN clinica cl ON cl.id_clinica = a.id_clinica
      JOIN historia_clinica h ON h.id_historia = a.id_historia
      JOIN mascota m ON m.id_mascota = h.id_mascota
      LEFT JOIN remito_biologico r ON r.id_remito = mu.id_remito
      LEFT JOIN analisis_solicitado an ON an.id_muestra = mu.id_muestra
      LEFT JOIN tipo_analisis ta ON ta.id_tipo_analisis = an.id_tipo_analisis"""


class MuestraDAO(BaseDAO[Muestra]):
    tabla, clave = "muestra", "id_muestra"
    columnas = ("id_orden", "id_veterinario", "id_remito", "codigo", "tipo", "fecha_hora_extraccion", "volumen_ml",
                "estado")
    orden = "id_muestra"

    def __init__(self, conexion=None):
        super().__init__(conexion)
        self._tipos = TipoAnalisisDAO(self.conexion)

    def _a_entidad(self, fila) -> Muestra:
        muestra = Muestra(id=fila["id_muestra"], id_orden=fila["id_orden"], id_veterinario=fila["id_veterinario"],
                          id_remito=fila["id_remito"], codigo=fila["codigo"], tipo=TipoMuestra(fila["tipo"]),
                          fecha_hora_extraccion=fechas.fecha_hora_desde_sql(fila["fecha_hora_extraccion"]),
                          volumen_ml=fila["volumen_ml"], estado=estado_muestra_desde(fila["estado"]),
                          historial=self._historial(fila["id_muestra"]))
        muestra.tipos_analisis = self._tipos.listar_por_muestra(muestra.id)
        return muestra

    def _a_registro(self, m: Muestra) -> tuple:
        return (m.id_orden, m.id_veterinario, m.id_remito, m.codigo, m.tipo.value, fechas.a_sql(m.fecha_hora_extraccion),
                m.volumen_ml, m.nombre_estado())

    def _historial(self, id_muestra: int) -> HistorialEstados:
        filas = self.conexion.consultar(
            "SELECT * FROM cambio_estado_muestra WHERE id_muestra = ? ORDER BY fecha_hora, id_cambio", (id_muestra,))
        return HistorialEstados([CambioEstado(fechas.fecha_hora_desde_sql(f["fecha_hora"]), f["estado_anterior"],
                                              f["estado_nuevo"], f["responsable"], f["observacion"]) for f in filas])

    def insertar_cambio_estado(self, id_muestra: int, cambio: CambioEstado) -> None:
        self.conexion.ejecutar("""
            INSERT INTO cambio_estado_muestra (id_muestra, fecha_hora, estado_anterior, estado_nuevo, responsable, observacion)
            VALUES (?, ?, ?, ?, ?, ?)""", (id_muestra, fechas.a_sql(cambio.fecha_hora), cambio.estado_anterior,
                                           cambio.estado_nuevo, cambio.responsable, cambio.observacion))

    def _insertar_cambios_nuevos(self, muestra: Muestra) -> None:
        """El historial es append-only: solo se insertan los cambios que todavía no están en la base."""
        persistidos = self.conexion.valor("SELECT COUNT(*) FROM cambio_estado_muestra WHERE id_muestra = ?",
                                          (muestra.id,))
        for cambio in list(muestra.historial())[persistidos:]:
            self.insertar_cambio_estado(muestra.id, cambio)

    def insertar(self, muestra: Muestra) -> int:
        with self.conexion.transaccion():
            super().insertar(muestra)
            self._insertar_cambios_nuevos(muestra)
        return muestra.id

    def guardar_transicion(self, muestra: Muestra) -> None:
        """Persiste el estado actual (y el remito asignado) junto con los nuevos cambios del historial."""
        with self.conexion.transaccion():
            self.conexion.ejecutar("UPDATE muestra SET estado = ?, id_remito = ? WHERE id_muestra = ?",
                                   (muestra.nombre_estado(), muestra.id_remito, muestra.id))
            self._insertar_cambios_nuevos(muestra)

    def obtener_por_codigo(self, codigo: str) -> Muestra | None:
        return self._obtener_donde("codigo = ?", (codigo.strip(),))

    def listar_por_remito(self, id_remito: int) -> list[Muestra]:
        return self._listar_donde("id_remito = ?", (id_remito,))

    def listar_por_orden(self, id_orden: int) -> list[Muestra]:
        return self._listar_donde("id_orden = ?", (id_orden,))

    def origen_y_destino(self, id_muestra: int) -> tuple[int, int] | None:
        """(clínica donde se extrajo, laboratorio al que se deriva) de una muestra."""
        fila = self.conexion.consultar_uno("""
            SELECT a.id_clinica, o.id_laboratorio FROM muestra mu
              JOIN orden_derivacion o ON o.id_orden = mu.id_orden
              JOIN atencion a ON a.id_atencion = o.id_atencion
             WHERE mu.id_muestra = ?""", (id_muestra,))
        return None if fila is None else (fila["id_clinica"], fila["id_laboratorio"])

    # --- Listados ---------------------------------------------------------------
    def resumen_pendientes_de_empaquetar(self, id_clinica: int | None = None) -> list[dict]:
        filtro = "AND a.id_clinica = ?" if id_clinica else ""
        return self._diccionarios(f"""{_SELECT_MUESTRA_RESUMEN}
             WHERE mu.estado = 'EXTRAIDA' AND mu.id_remito IS NULL AND o.estado <> 'CANCELADA' {filtro}
             GROUP BY mu.id_muestra ORDER BY o.prioridad DESC, mu.fecha_hora_extraccion""",
                                  (id_clinica,) if id_clinica else ())

    def resumen_por_remito(self, id_remito: int) -> list[dict]:
        return self._diccionarios(f"{_SELECT_MUESTRA_RESUMEN} WHERE mu.id_remito = ? GROUP BY mu.id_muestra "
                                  f"ORDER BY mu.codigo", (id_remito,))

    def resumen_por_codigo(self, texto: str) -> list[dict]:
        patron = f"%{texto.strip()}%"
        return self._diccionarios(f"{_SELECT_MUESTRA_RESUMEN} WHERE mu.codigo LIKE ? OR m.nombre LIKE ? "
                                  f"GROUP BY mu.id_muestra ORDER BY mu.fecha_hora_extraccion DESC LIMIT 200",
                                  (patron, patron))


class OrdenDerivacionDAO(BaseDAO[OrdenDerivacion]):
    tabla, clave = "orden_derivacion", "id_orden"
    columnas = ("id_atencion", "id_laboratorio", "numero", "fecha_emision", "prioridad", "indicaciones_clinicas",
                "estado")
    orden = "fecha_emision DESC"

    def __init__(self, conexion=None):
        super().__init__(conexion)
        self._muestras = MuestraDAO(self.conexion)
        self._tipos = TipoAnalisisDAO(self.conexion)

    def _a_entidad(self, fila) -> OrdenDerivacion:
        orden = OrdenDerivacion(id=fila["id_orden"], id_atencion=fila["id_atencion"],
                                id_laboratorio=fila["id_laboratorio"], numero=fila["numero"],
                                fecha_emision=fechas.fecha_hora_desde_sql(fila["fecha_emision"]),
                                prioridad=Prioridad(fila["prioridad"]),
                                indicaciones_clinicas=fila["indicaciones_clinicas"], estado=EstadoOrden(fila["estado"]))
        orden.muestras = self._muestras.listar_por_orden(orden.id)
        muestras_por_id = {m.id: m for m in orden.muestras}
        orden.analisis = [self._a_analisis(f, muestras_por_id) for f in self.conexion.consultar(
            "SELECT * FROM analisis_solicitado WHERE id_orden = ? ORDER BY id_analisis_solicitado", (orden.id,))]
        return orden

    def _a_analisis(self, f, muestras_por_id: dict) -> AnalisisSolicitado:
        analisis = AnalisisSolicitado(id=f["id_analisis_solicitado"], id_orden=f["id_orden"],
                                      id_tipo_analisis=f["id_tipo_analisis"], id_muestra=f["id_muestra"],
                                      observaciones=f["observaciones"],
                                      tipo_analisis=self._tipos.obtener_por_id(f["id_tipo_analisis"]),
                                      muestra=muestras_por_id.get(f["id_muestra"]))
        # Solo interesa saber si tiene resultado; el detalle lo obtiene ResultadoDAO
        analisis.resultado = self.conexion.valor(
            "SELECT id_resultado FROM resultado_analisis WHERE id_analisis_solicitado = ?", (analisis.id,))
        return analisis

    def _a_registro(self, o: OrdenDerivacion) -> tuple:
        return (o.id_atencion, o.id_laboratorio, o.numero, fechas.a_sql(o.fecha_emision), o.prioridad.value,
                o.indicaciones_clinicas, o.estado.value)

    def insertar(self, orden: OrdenDerivacion) -> int:
        """Inserta la orden, sus muestras extraídas (con el primer cambio de estado) y los análisis solicitados."""
        with self.conexion.transaccion():
            super().insertar(orden)
            for muestra in orden.muestras:
                muestra.id_orden = orden.id
                self._muestras.insertar(muestra)
            for analisis in orden.analisis:
                self._insertar_analisis(orden, analisis)
        return orden.id

    def _insertar_analisis(self, orden: OrdenDerivacion, analisis: AnalisisSolicitado) -> None:
        analisis.id_orden = orden.id
        analisis.id_muestra = analisis.muestra.id
        analisis.id = self.conexion.ejecutar("""
            INSERT INTO analisis_solicitado (id_orden, id_tipo_analisis, id_muestra, observaciones)
            VALUES (?, ?, ?, ?)""", (orden.id, analisis.id_tipo_analisis, analisis.id_muestra,
                                     analisis.observaciones)).lastrowid

    def obtener_analisis(self, id_analisis_solicitado: int) -> AnalisisSolicitado | None:
        fila = self.conexion.consultar_uno("SELECT * FROM analisis_solicitado WHERE id_analisis_solicitado = ?",
                                           (id_analisis_solicitado,))
        if fila is None:
            return None
        muestra = self._muestras.obtener_por_id(fila["id_muestra"])
        return self._a_analisis(fila, {muestra.id: muestra})

    def reasignar_muestra(self, id_analisis_solicitado: int, id_muestra: int) -> None:
        self.conexion.ejecutar("UPDATE analisis_solicitado SET id_muestra = ? WHERE id_analisis_solicitado = ?",
                               (id_muestra, id_analisis_solicitado))

    def actualizar_estado(self, orden: OrdenDerivacion) -> None:
        self.conexion.ejecutar("UPDATE orden_derivacion SET estado = ? WHERE id_orden = ?",
                               (orden.estado.value, orden.id))

    def listar_por_atencion(self, id_atencion: int) -> list[OrdenDerivacion]:
        return self._listar_donde("id_atencion = ?", (id_atencion,))

    def siguiente_numero(self, anio: int) -> str:
        return f"OD-{anio}-{self.siguiente_secuencia():05d}"

    def resumen_de_atencion(self, id_atencion: int) -> list[dict]:
        return self._diccionarios("""
            SELECT o.*, lab.nombre AS laboratorio,
                   GROUP_CONCAT(ta.nombre, ', ') AS analisis
              FROM orden_derivacion o
              JOIN laboratorio_central lab ON lab.id_laboratorio = o.id_laboratorio
              LEFT JOIN analisis_solicitado an ON an.id_orden = o.id_orden
              LEFT JOIN tipo_analisis ta ON ta.id_tipo_analisis = an.id_tipo_analisis
             WHERE o.id_atencion = ? GROUP BY o.id_orden ORDER BY o.fecha_emision""", (id_atencion,))
