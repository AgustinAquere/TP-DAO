"""DAO de comprobantes de atención con sus ítems. Subtotal, total y estrategia quedan congelados al emitir."""
from datetime import date

from app.dominio.enums import TipoItem
from app.dominio.facturacion import ComprobanteAtencion, ItemComprobante
from app.persistencia.daos.base_dao import BaseDAO
from app.utils import fechas


class ComprobanteDAO(BaseDAO[ComprobanteAtencion]):
    tabla, clave = "comprobante_atencion", "id_comprobante"
    columnas = ("id_atencion", "id_cliente", "id_clinica", "numero", "fecha_emision", "estrategia_tarifa", "subtotal",
                "total")
    orden = "fecha_emision DESC"

    def _a_entidad(self, fila) -> ComprobanteAtencion:
        comprobante = ComprobanteAtencion(id=fila["id_comprobante"], id_atencion=fila["id_atencion"],
                                          id_cliente=fila["id_cliente"], id_clinica=fila["id_clinica"],
                                          numero=fila["numero"],
                                          fecha_emision=fechas.fecha_hora_desde_sql(fila["fecha_emision"]),
                                          estrategia_tarifa=fila["estrategia_tarifa"],
                                          subtotal_emitido=fila["subtotal"], total_emitido=fila["total"])
        comprobante.items = [
            ItemComprobante(id=f["id_item"], id_comprobante=f["id_comprobante"], tipo=TipoItem(f["tipo"]),
                            id_servicio=f["id_servicio"], id_tipo_analisis=f["id_tipo_analisis"],
                            id_vacuna=f["id_vacuna"], descripcion=f["descripcion"], cantidad=f["cantidad"],
                            precio_unitario=f["precio_unitario"])
            for f in self.conexion.consultar("SELECT * FROM item_comprobante WHERE id_comprobante = ? ORDER BY id_item",
                                             (comprobante.id,))]
        return comprobante

    def _a_registro(self, c: ComprobanteAtencion) -> tuple:
        return (c.id_atencion, c.id_cliente, c.id_clinica, c.numero, fechas.a_sql(c.fecha_emision),
                c.estrategia_tarifa, c.subtotal(), c.total())

    def insertar(self, comprobante: ComprobanteAtencion) -> int:
        with self.conexion.transaccion():
            super().insertar(comprobante)
            for item in comprobante.items:
                item.id_comprobante = comprobante.id
                item.id = self.conexion.ejecutar("""
                    INSERT INTO item_comprobante (id_comprobante, tipo, id_servicio, id_tipo_analisis, id_vacuna,
                           descripcion, cantidad, precio_unitario)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (comprobante.id, item.tipo.value, item.id_servicio,
                                                         item.id_tipo_analisis, item.id_vacuna, item.descripcion.strip(),
                                                         item.cantidad, item.precio_unitario)).lastrowid
        return comprobante.id

    def obtener_por_atencion(self, id_atencion: int) -> ComprobanteAtencion | None:
        return self._obtener_donde("id_atencion = ?", (id_atencion,))

    def siguiente_numero(self, id_clinica: int) -> str:
        """Numeración por punto de venta (uno por clínica): 0001-00000001."""
        cantidad = self.contar("id_clinica = ?", (id_clinica,))
        return f"{id_clinica:04d}-{cantidad + 1:08d}"

    def listar_resumen(self, desde: date | None = None, hasta: date | None = None,
                       id_clinica: int | None = None) -> list[dict]:
        condiciones, parametros = ["1 = 1"], []
        for valor, condicion in ((fechas.a_sql(desde), "date(cp.fecha_emision) >= ?"),
                                 (fechas.a_sql(hasta), "date(cp.fecha_emision) <= ?"),
                                 (id_clinica, "cp.id_clinica = ?")):
            if valor:
                condiciones.append(condicion)
                parametros.append(valor)
        return self._diccionarios(f"""
            SELECT cp.*, c.apellido || ', ' || c.nombre AS cliente, c.dni, cl.nombre AS clinica,
                   m.nombre AS mascota, a.tipo AS tipo_atencion, a.fecha_hora AS fecha_atencion
              FROM comprobante_atencion cp
              JOIN cliente c ON c.id_cliente = cp.id_cliente
              JOIN clinica cl ON cl.id_clinica = cp.id_clinica
              JOIN atencion a ON a.id_atencion = cp.id_atencion
              JOIN historia_clinica h ON h.id_historia = a.id_historia
              JOIN mascota m ON m.id_mascota = h.id_mascota
             WHERE {' AND '.join(condiciones)}
             ORDER BY cp.fecha_emision DESC""", tuple(parametros))
