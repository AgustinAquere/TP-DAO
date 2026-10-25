"""Procesos 4 y 5: empaquetar muestras en conservadoras (remito + precinto) y registrar la cadena de envío."""
from datetime import datetime

from app.dominio.envio import Conservadora, PrecintoSanitario, TramoEnvio
from app.dominio.estados_remito import estado_remito_desde
from app.dominio.excepciones import EntidadNoEncontradaError, TransicionInvalidaError, ValidacionError
from app.dominio.muestra import Muestra
from app.dominio.remito import RemitoBiologico
from app.persistencia.conexion import ConexionBD
from app.persistencia.daos.catalogos_dao import ConservadoraDAO, TransportistaDAO
from app.persistencia.daos.derivacion_dao import MuestraDAO, OrdenDerivacionDAO
from app.persistencia.daos.remito_dao import RemitoDAO
from app.utils import fechas


class DerivacionService:
    def __init__(self, muestras: MuestraDAO, remitos: RemitoDAO, conservadoras: ConservadoraDAO,
                 ordenes: OrdenDerivacionDAO, transportistas: TransportistaDAO, conexion: ConexionBD):
        self._muestras = muestras
        self._remitos = remitos
        self._conservadoras = conservadoras
        self._ordenes = ordenes
        self._transportistas = transportistas
        self._conexion = conexion

    # --- Consultas -------------------------------------------------------------------
    def muestras_pendientes(self, id_clinica: int | None = None, ahora: datetime | None = None) -> list[dict]:
        """Muestras extraídas sin remito, con las horas de viabilidad que les quedan."""
        ahora = ahora or fechas.ahora()
        filas = self._muestras.resumen_pendientes_de_empaquetar(id_clinica)
        for fila in filas:
            horas = fechas.horas_entre(fechas.fecha_hora_desde_sql(fila["fecha_hora_extraccion"]), ahora)
            fila["horas_restantes"] = (fila["horas_max_viabilidad"] - horas) if fila["horas_max_viabilidad"] else None
        return filas

    def conservadoras_disponibles(self) -> list[Conservadora]:
        return self._conservadoras.listar_disponibles()

    def obtener_remito(self, id_remito: int) -> RemitoBiologico:
        remito = self._remitos.obtener_por_id(id_remito)
        if remito is None:
            raise EntidadNoEncontradaError("el remito", id_remito)
        return remito

    def listar_remitos(self, estado: str | None = None, id_laboratorio: int | None = None,
                       id_clinica: int | None = None) -> list[dict]:
        return self._remitos.listar_resumen(estado, id_laboratorio, id_clinica)

    @staticmethod
    def operaciones_permitidas(estado: str) -> set[str]:
        """Operaciones que admite un remito en el estado indicado (las define cada clase del patrón State)."""
        return estado_remito_desde(estado).operaciones_permitidas()

    def muestras_de_remito(self, id_remito: int) -> list[dict]:
        return self._muestras.resumen_por_remito(id_remito)

    def buscar_muestras(self, texto: str) -> list[dict]:
        return self._muestras.resumen_por_codigo(texto)

    def trazabilidad(self, id_muestra: int) -> Muestra:
        muestra = self._muestras.obtener_por_id(id_muestra)
        if muestra is None:
            raise EntidadNoEncontradaError("la muestra", id_muestra)
        return muestra

    def _muestra(self, id_muestra: int) -> Muestra:
        return self.trazabilidad(id_muestra)

    # --- Proceso 4: empaquetado ------------------------------------------------------------
    def armar_remito(self, ids_muestras: list[int], id_conservadora: int, id_clinica_origen: int,
                     fecha_hora: datetime | None = None) -> RemitoBiologico:
        if not ids_muestras:
            raise ValidacionError("Seleccione al menos una muestra para el remito.")
        conservadora = self._conservadoras.obtener_por_id(id_conservadora)
        if conservadora is None:
            raise ValidacionError("Seleccione una conservadora.")
        if not conservadora.disponible:
            raise ValidacionError(f"La conservadora {conservadora.codigo} está en uso en otro envío.")
        muestras = [self._muestra(id_muestra) for id_muestra in ids_muestras]
        rutas = {self._muestras.origen_y_destino(m.id) for m in muestras}
        if any(clinica != id_clinica_origen for clinica, _ in rutas):
            raise ValidacionError("Todas las muestras deben haberse extraído en la clínica de origen del remito.")
        destinos = {laboratorio for _, laboratorio in rutas}
        if len(destinos) > 1:
            raise ValidacionError("Las muestras de un remito deben derivarse al mismo laboratorio.")

        fecha_hora = fecha_hora or fechas.ahora()
        remito = RemitoBiologico(id_conservadora=id_conservadora, id_clinica_origen=id_clinica_origen,
                                 id_laboratorio_destino=destinos.pop(), fecha_hora_emision=fecha_hora,
                                 numero=self._remitos.siguiente_numero(fecha_hora.year))
        remito.conservadora = conservadora
        with self._conexion.transaccion():
            self._remitos.insertar(remito)
            for muestra in muestras:
                remito.agregar_muestra(muestra)   # la conservadora valida capacidad y temperatura
                self._muestras.guardar_transicion(muestra)
            self._conservadoras.marcar_disponible(id_conservadora, False)
        return remito

    def agregar_muestra(self, id_remito: int, id_muestra: int) -> None:
        remito, muestra = self.obtener_remito(id_remito), self._muestra(id_muestra)
        if self._muestras.origen_y_destino(id_muestra) != (remito.id_clinica_origen, remito.id_laboratorio_destino):
            raise ValidacionError("La muestra no corresponde al origen y destino del remito.")
        remito.agregar_muestra(muestra)
        self._muestras.guardar_transicion(muestra)

    def quitar_muestra(self, id_remito: int, id_muestra: int) -> None:
        remito = self.obtener_remito(id_remito)
        muestra = next((m for m in remito.muestras if m.id == id_muestra), None)
        if muestra is None:
            raise ValidacionError("La muestra no pertenece al remito.")
        remito.quitar_muestra(muestra)
        self._muestras.guardar_transicion(muestra)

    def anular_remito(self, id_remito: int) -> None:
        """Descarta un remito que todavía está en preparación y libera sus muestras y la conservadora."""
        remito = self.obtener_remito(id_remito)
        if "quitar_muestra" not in remito.operaciones_permitidas():
            raise TransicionInvalidaError("Solo puede anularse un remito en preparación.")
        with self._conexion.transaccion():
            for muestra in list(remito.muestras):
                remito.quitar_muestra(muestra)
                self._muestras.guardar_transicion(muestra)
            self._remitos.eliminar(remito.id)
            self._conservadoras.marcar_disponible(remito.id_conservadora, True)

    def precintar(self, id_remito: int, responsable: str, numero_precinto: str | None = None,
                  fecha_hora: datetime | None = None) -> PrecintoSanitario:
        remito = self.obtener_remito(id_remito)
        numero = (numero_precinto or "").strip() or self._remitos.siguiente_numero_precinto()
        precinto = remito.precintar(numero, responsable=responsable, fecha_hora=fecha_hora)
        with self._conexion.transaccion():
            self._remitos.guardar_precinto(precinto)
            self._remitos.actualizar_estado(remito)
            for muestra in remito.muestras:
                self._muestras.guardar_transicion(muestra)
        return precinto

    # --- Proceso 5: cadena de envío -----------------------------------------------------------
    def despachar(self, id_remito: int, id_transportista: int, entregado_por: str,
                  temperatura_salida: float | None = None, fecha_hora: datetime | None = None,
                  destino: str | None = None, observaciones: str | None = None) -> TramoEnvio:
        remito = self.obtener_remito(id_remito)
        self._validar_transportista(id_transportista)
        tramo = TramoEnvio(id_transportista=id_transportista, origen=remito.nombre_clinica,
                           destino=destino or remito.nombre_laboratorio, fecha_hora_salida=fecha_hora or fechas.ahora(),
                           temperatura_salida_c=temperatura_salida, entregado_por=entregado_por,
                           observaciones=observaciones)
        remito.despachar(tramo, responsable=entregado_por)
        with self._conexion.transaccion():
            self._remitos.guardar_tramo(tramo)
            self._remitos.actualizar_estado(remito)
            for muestra in remito.muestras:
                self._muestras.guardar_transicion(muestra)
            self._actualizar_ordenes(remito)
        return tramo

    def cerrar_tramo(self, id_remito: int, fecha_hora_llegada: datetime, recibido_por: str,
                     temperatura_llegada: float | None = None, observaciones: str | None = None) -> TramoEnvio:
        remito = self.obtener_remito(id_remito)
        tramo = remito.cerrar_tramo(fecha_hora_llegada=fecha_hora_llegada, recibido_por=recibido_por,
                                    temperatura_llegada_c=temperatura_llegada, observaciones=observaciones)
        self._remitos.guardar_tramo(tramo)
        return tramo

    def registrar_tramo(self, id_remito: int, id_transportista: int, origen: str, destino: str,
                        fecha_hora_salida: datetime, entregado_por: str, temperatura_salida: float | None = None,
                        observaciones: str | None = None) -> TramoEnvio:
        remito = self.obtener_remito(id_remito)
        self._validar_transportista(id_transportista)
        tramo = TramoEnvio(id_transportista=id_transportista, origen=origen, destino=destino,
                           fecha_hora_salida=fecha_hora_salida, entregado_por=entregado_por,
                           temperatura_salida_c=temperatura_salida, observaciones=observaciones)
        remito.registrar_tramo(tramo)
        self._remitos.guardar_tramo(tramo)
        return tramo

    def _validar_transportista(self, id_transportista: int) -> None:
        if self._transportistas.obtener_por_id(id_transportista) is None:
            raise ValidacionError("Seleccione el transportista.")

    def _actualizar_ordenes(self, remito: RemitoBiologico) -> None:
        for id_orden in {m.id_orden for m in remito.muestras}:
            orden = self._ordenes.obtener_por_id(id_orden)
            orden.actualizar_estado()
            self._ordenes.actualizar_estado(orden)

    # --- Nueva extracción para una muestra rechazada ------------------------------------------
    def reextraer_muestra(self, id_muestra: int, responsable: str, volumen: float | None = None,
                          fecha_hora: datetime | None = None) -> Muestra:
        """Registra una nueva extracción y le reasigna los análisis que quedaron sin resultado.

        La muestra rechazada conserva su historial: la trazabilidad no se modifica.
        """
        anterior = self._muestra(id_muestra)
        if anterior.nombre_estado() != "RECHAZADA":
            raise TransicionInvalidaError("Solo se puede repetir la extracción de una muestra rechazada.")
        orden = self._ordenes.obtener_por_id(anterior.id_orden)
        pendientes = [a for a in orden.analisis if a.id_muestra == anterior.id and not a.tiene_resultado()]
        if not pendientes:
            raise ValidacionError("La muestra ya fue reemplazada por una nueva extracción.")
        nueva = orden.registrar_extraccion(anterior.tipo, volumen or anterior.volumen_ml,
                                           id_veterinario=anterior.id_veterinario, responsable=responsable,
                                           fecha_hora=fecha_hora or fechas.ahora())
        with self._conexion.transaccion():
            nueva.id_orden = orden.id
            self._muestras.insertar(nueva)
            for analisis in pendientes:
                self._ordenes.reasignar_muestra(analisis.id, nueva.id)
        return nueva
