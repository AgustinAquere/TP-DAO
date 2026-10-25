"""DAO del remito biológico (con precinto y tramos de envío) y de la recepción en el laboratorio."""
from app.dominio.enums import EstadoPrecinto
from app.dominio.envio import PrecintoSanitario, TramoEnvio
from app.dominio.estados_remito import estado_remito_desde
from app.dominio.laboratorio import RecepcionLaboratorio
from app.dominio.remito import RemitoBiologico
from app.persistencia.daos.base_dao import BaseDAO
from app.persistencia.daos.catalogos_dao import ConservadoraDAO
from app.persistencia.daos.derivacion_dao import MuestraDAO
from app.utils import fechas


class RecepcionDAO(BaseDAO[RecepcionLaboratorio]):
    tabla, clave = "recepcion_laboratorio", "id_recepcion"
    columnas = ("id_remito", "id_bioquimico", "fecha_hora", "estado_precinto_verificado", "temperatura_arribo_c",
                "aceptada", "motivo_rechazo")
    orden = "fecha_hora DESC"

    def _a_entidad(self, fila) -> RecepcionLaboratorio:
        return RecepcionLaboratorio(id=fila["id_recepcion"], id_remito=fila["id_remito"],
                                    id_bioquimico=fila["id_bioquimico"],
                                    fecha_hora=fechas.fecha_hora_desde_sql(fila["fecha_hora"]),
                                    estado_precinto_verificado=EstadoPrecinto(fila["estado_precinto_verificado"]),
                                    temperatura_arribo_c=fila["temperatura_arribo_c"], aceptada=bool(fila["aceptada"]),
                                    motivo_rechazo=fila["motivo_rechazo"])

    def _a_registro(self, r: RecepcionLaboratorio) -> tuple:
        return (r.id_remito, r.id_bioquimico, fechas.a_sql(r.fecha_hora), r.estado_precinto_verificado.value,
                r.temperatura_arribo_c, int(r.aceptada), r.motivo_rechazo)

    def obtener_por_remito(self, id_remito: int) -> RecepcionLaboratorio | None:
        return self._obtener_donde("id_remito = ?", (id_remito,))


class RemitoDAO(BaseDAO[RemitoBiologico]):
    tabla, clave = "remito_biologico", "id_remito"
    columnas = ("id_conservadora", "id_clinica_origen", "id_laboratorio_destino", "numero", "fecha_hora_emision",
                "estado")
    orden = "fecha_hora_emision DESC"

    def __init__(self, conexion=None):
        super().__init__(conexion)
        self._muestras = MuestraDAO(self.conexion)
        self._conservadoras = ConservadoraDAO(self.conexion)
        self._recepciones = RecepcionDAO(self.conexion)

    def _a_entidad(self, fila) -> RemitoBiologico:
        remito = RemitoBiologico(id=fila["id_remito"], id_conservadora=fila["id_conservadora"],
                                 id_clinica_origen=fila["id_clinica_origen"],
                                 id_laboratorio_destino=fila["id_laboratorio_destino"], numero=fila["numero"],
                                 fecha_hora_emision=fechas.fecha_hora_desde_sql(fila["fecha_hora_emision"]),
                                 estado=estado_remito_desde(fila["estado"]))
        remito.muestras = self._muestras.listar_por_remito(remito.id)
        remito.conservadora = self._conservadoras.obtener_por_id(remito.id_conservadora)
        remito.precinto = self._precinto_de(remito.id)
        remito.tramos = self._tramos_de(remito.id)
        remito.recepcion = self._recepciones.obtener_por_remito(remito.id)
        remito.nombre_clinica = self.conexion.valor("SELECT nombre FROM clinica WHERE id_clinica = ?",
                                                    (remito.id_clinica_origen,))
        remito.nombre_laboratorio = self.conexion.valor(
            "SELECT nombre FROM laboratorio_central WHERE id_laboratorio = ?", (remito.id_laboratorio_destino,))
        return remito

    def _a_registro(self, r: RemitoBiologico) -> tuple:
        return (r.id_conservadora, r.id_clinica_origen, r.id_laboratorio_destino, r.numero,
                fechas.a_sql(r.fecha_hora_emision), r.nombre_estado())

    def actualizar_estado(self, remito: RemitoBiologico) -> None:
        self.conexion.ejecutar("UPDATE remito_biologico SET estado = ? WHERE id_remito = ?",
                               (remito.nombre_estado(), remito.id))

    def siguiente_numero(self, anio: int) -> str:
        return f"RB-{anio}-{self.siguiente_secuencia():05d}"

    # --- Precinto sanitario (1:1) -------------------------------------------------
    def _precinto_de(self, id_remito: int) -> PrecintoSanitario | None:
        f = self.conexion.consultar_uno("SELECT * FROM precinto_sanitario WHERE id_remito = ?", (id_remito,))
        if f is None:
            return None
        return PrecintoSanitario(id=f["id_precinto"], id_remito=f["id_remito"], numero=f["numero"],
                                 fecha_hora_colocacion=fechas.fecha_hora_desde_sql(f["fecha_hora_colocacion"]),
                                 estado=EstadoPrecinto(f["estado"]))

    def guardar_precinto(self, precinto: PrecintoSanitario) -> None:
        if precinto.id is None:
            precinto.id = self.conexion.ejecutar("""
                INSERT INTO precinto_sanitario (id_remito, numero, fecha_hora_colocacion, estado) VALUES (?, ?, ?, ?)""",
                (precinto.id_remito, precinto.numero, fechas.a_sql(precinto.fecha_hora_colocacion),
                 precinto.estado.value)).lastrowid
        else:
            self.conexion.ejecutar("UPDATE precinto_sanitario SET estado = ? WHERE id_precinto = ?",
                                   (precinto.estado.value, precinto.id))

    def siguiente_numero_precinto(self) -> str:
        siguiente = (self.conexion.valor("SELECT MAX(id_precinto) FROM precinto_sanitario") or 0) + 1
        return f"PS-{siguiente:06d}"

    # --- Tramos de envío (cadena de custodia) -------------------------------------
    def _tramos_de(self, id_remito: int) -> list[TramoEnvio]:
        filas = self.conexion.consultar("""
            SELECT te.*, t.razon_social FROM tramo_envio te JOIN transportista t ON t.id_transportista = te.id_transportista
             WHERE te.id_remito = ? ORDER BY te.nro_orden""", (id_remito,))
        return [TramoEnvio(id=f["id_tramo"], id_remito=f["id_remito"], id_transportista=f["id_transportista"],
                           nro_orden=f["nro_orden"], origen=f["origen"], destino=f["destino"],
                           fecha_hora_salida=fechas.fecha_hora_desde_sql(f["fecha_hora_salida"]),
                           fecha_hora_llegada=fechas.fecha_hora_desde_sql(f["fecha_hora_llegada"]),
                           temperatura_salida_c=f["temperatura_salida_c"],
                           temperatura_llegada_c=f["temperatura_llegada_c"], entregado_por=f["entregado_por"],
                           recibido_por=f["recibido_por"], observaciones=f["observaciones"],
                           nombre_transportista=f["razon_social"]) for f in filas]

    def guardar_tramo(self, t: TramoEnvio) -> None:
        valores = (t.id_remito, t.id_transportista, t.nro_orden, t.origen, t.destino, fechas.a_sql(t.fecha_hora_salida),
                   fechas.a_sql(t.fecha_hora_llegada), t.temperatura_salida_c, t.temperatura_llegada_c, t.entregado_por,
                   t.recibido_por, t.observaciones)
        if t.id is None:
            t.id = self.conexion.ejecutar("""
                INSERT INTO tramo_envio (id_remito, id_transportista, nro_orden, origen, destino, fecha_hora_salida,
                       fecha_hora_llegada, temperatura_salida_c, temperatura_llegada_c, entregado_por, recibido_por,
                       observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", valores).lastrowid
        else:
            self.conexion.ejecutar("""
                UPDATE tramo_envio SET id_remito = ?, id_transportista = ?, nro_orden = ?, origen = ?, destino = ?,
                       fecha_hora_salida = ?, fecha_hora_llegada = ?, temperatura_salida_c = ?,
                       temperatura_llegada_c = ?, entregado_por = ?, recibido_por = ?, observaciones = ?
                 WHERE id_tramo = ?""", (*valores, t.id))

    # --- Listados -------------------------------------------------------------------
    def listar_resumen(self, estado: str | None = None, id_laboratorio: int | None = None,
                       id_clinica: int | None = None) -> list[dict]:
        condiciones, parametros = ["1 = 1"], []
        for valor, condicion in ((estado, "r.estado = ?"), (id_laboratorio, "r.id_laboratorio_destino = ?"),
                                 (id_clinica, "r.id_clinica_origen = ?")):
            if valor:
                condiciones.append(condicion)
                parametros.append(valor)
        return self._diccionarios(f"""
            SELECT r.*, cl.nombre AS clinica, lab.nombre AS laboratorio, c.codigo AS conservadora,
                   p.numero AS precinto, p.estado AS estado_precinto,
                   (SELECT COUNT(*) FROM muestra mu WHERE mu.id_remito = r.id_remito) AS cantidad_muestras,
                   (SELECT MIN(te.fecha_hora_salida) FROM tramo_envio te WHERE te.id_remito = r.id_remito) AS salida,
                   (SELECT COUNT(*) FROM tramo_envio te WHERE te.id_remito = r.id_remito) AS cantidad_tramos,
                   (SELECT t.razon_social FROM tramo_envio te JOIN transportista t ON t.id_transportista = te.id_transportista
                     WHERE te.id_remito = r.id_remito ORDER BY te.nro_orden DESC LIMIT 1) AS transportista
              FROM remito_biologico r
              JOIN clinica cl ON cl.id_clinica = r.id_clinica_origen
              JOIN laboratorio_central lab ON lab.id_laboratorio = r.id_laboratorio_destino
              JOIN conservadora c ON c.id_conservadora = r.id_conservadora
              LEFT JOIN precinto_sanitario p ON p.id_remito = r.id_remito
             WHERE {' AND '.join(condiciones)}
             ORDER BY r.fecha_hora_emision DESC""", tuple(parametros))
