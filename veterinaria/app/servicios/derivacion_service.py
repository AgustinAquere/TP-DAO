"""Procesos 4 y 5: empaquetar muestras en conservadoras (remito + precinto) y registrar la cadena de envío."""
from datetime import datetime

from app.dominio.envio import Conservadora, PrecintoSanitario, TramoEnvio
from app.dominio.estados_remito import estado_remito_desde
from app.dominio.excepciones import EntidadNoEncontradaError, TransicionInvalidaError, ValidacionError
from app.dominio.muestra import Muestra
from app.dominio.personas import Veterinario
from app.dominio.remito import RemitoBiologico, anotar_situacion_tramos, es_arribo_a_laboratorio
from app.persistencia.conexion import ConexionBD
from app.persistencia.daos.catalogos_dao import ConservadoraDAO, TransportistaDAO
from app.persistencia.daos.derivacion_dao import MuestraDAO, OrdenDerivacionDAO
from app.persistencia.daos.personas_dao import BioquimicoDAO, VeterinarioDAO
from app.persistencia.daos.remito_dao import RemitoDAO
from app.utils import fechas


class DerivacionService:
    def __init__(self, muestras: MuestraDAO, remitos: RemitoDAO, conservadoras: ConservadoraDAO,
                 ordenes: OrdenDerivacionDAO, transportistas: TransportistaDAO, veterinarios: VeterinarioDAO,
                 bioquimicos: BioquimicoDAO, conexion: ConexionBD):
        self._muestras = muestras
        self._remitos = remitos
        self._conservadoras = conservadoras
        self._ordenes = ordenes
        self._transportistas = transportistas
        self._veterinarios = veterinarios
        self._bioquimicos = bioquimicos
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

    def veterinarios_de_clinica(self, id_clinica: int) -> list[Veterinario]:
        """Personal de la clínica que puede responsabilizarse de la extracción, el empaquetado y el precinto."""
        return self._veterinarios.listar_por_clinica(id_clinica)

    def obtener_remito(self, id_remito: int) -> RemitoBiologico:
        remito = self._remitos.obtener_por_id(id_remito)
        if remito is None:
            raise EntidadNoEncontradaError("el remito", id_remito)
        return remito

    def listar_remitos(self, estado: str | None = None, id_laboratorio: int | None = None,
                       id_clinica: int | None = None) -> list[dict]:
        filas = self._remitos.listar_resumen(estado, id_laboratorio, id_clinica)
        anotar_situacion_tramos(filas, self._bioquimicos.listar())
        return filas

    def receptores_de_llegada(self, id_remito: int, destino_final: bool) -> list[tuple[int, str]]:
        """Quién puede recibir la conservadora al cerrar el tramo.

        En una posta, otro transportista (no el que trae el tramo). En el laboratorio de destino, un bioquímico.
        """
        remito = self.obtener_remito(id_remito)
        if destino_final:
            return [(b.id, f"{b.nombre_completo()} · {b.matricula}")
                    for b in self._bioquimicos.listar_por_laboratorio(remito.id_laboratorio_destino)]
        actual = remito.tramo_actual()
        excluir = actual.id_transportista if actual else None
        return [(t.id, f"{t.razon_social} · {t.patente_vehiculo or ''}")
                for t in self._transportistas.listar() if t.id != excluir]

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

    def _veterinario_de_la_clinica(self, id_veterinario: int | None, id_clinica: int, rol: str,
                                   clinica: str = "la clínica de origen del remito") -> Veterinario:
        veterinario = self._veterinarios.obtener_por_id(id_veterinario) if id_veterinario else None
        if veterinario is None:
            raise ValidacionError(f"Seleccione {rol}.")
        if not veterinario.trabaja_en(id_clinica):
            raise ValidacionError(f"{veterinario.nombre_completo()} no trabaja en {clinica}.")
        return veterinario

    def precintar(self, id_remito: int, id_veterinario: int, numero_precinto: str | None = None,
                  fecha_hora: datetime | None = None) -> PrecintoSanitario:
        """Precinta el remito. El responsable debe ser un veterinario de la clínica de origen."""
        remito = self.obtener_remito(id_remito)
        responsable = self._veterinario_de_la_clinica(id_veterinario, remito.id_clinica_origen,
                                                      "el responsable del empaquetado")
        numero = (numero_precinto or "").strip() or self._remitos.siguiente_numero_precinto()
        precinto = remito.precintar(numero, responsable=responsable.nombre_completo(), fecha_hora=fecha_hora)
        with self._conexion.transaccion():
            self._remitos.guardar_precinto(precinto)
            self._remitos.actualizar_estado(remito)
            for muestra in remito.muestras:
                self._muestras.guardar_transicion(muestra)
        return precinto

    # --- Proceso 5: cadena de envío -----------------------------------------------------------
    def despachar(self, id_remito: int, id_transportista: int, id_veterinario: int,
                  temperatura_salida: float | None = None, fecha_hora: datetime | None = None,
                  destino: str | None = None, observaciones: str | None = None) -> TramoEnvio:
        """Entrega el remito al transportista. Quien lo entrega debe ser un veterinario de la clínica de origen."""
        remito = self.obtener_remito(id_remito)
        self._validar_transportista(id_transportista)
        entregado_por = self._veterinario_de_la_clinica(id_veterinario, remito.id_clinica_origen,
                                                        "quién entrega el remito").nombre_completo()
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

    def cerrar_tramo(self, id_remito: int, fecha_hora_llegada: datetime, *, destino_final: bool, id_receptor: int,
                     lugar: str | None = None, temperatura_llegada: float | None = None,
                     observaciones: str | None = None) -> TramoEnvio:
        """Registra la llegada. En una posta recibe otro transportista; en el laboratorio, un bioquímico."""
        remito = self.obtener_remito(id_remito)
        actual = remito.tramo_actual()
        if destino_final:
            recibido_por, destino = self._bioquimico_que_recibe(id_receptor, remito)
        else:
            recibido_por, destino = self._transportista_que_recibe(id_receptor, actual, remito.nombre_laboratorio, lugar)
        tramo = remito.cerrar_tramo(fecha_hora_llegada=fecha_hora_llegada, recibido_por=recibido_por,
                                    temperatura_llegada_c=temperatura_llegada, observaciones=observaciones)
        tramo.destino = destino
        self._remitos.guardar_tramo(tramo)
        return tramo

    def registrar_tramo(self, id_remito: int, id_transportista: int, origen: str, destino: str,
                        fecha_hora_salida: datetime, entregado_por: str, temperatura_salida: float | None = None,
                        observaciones: str | None = None) -> TramoEnvio:
        remito = self.obtener_remito(id_remito)
        self._validar_continuacion(remito, origen, entregado_por)
        self._validar_transportista(id_transportista)
        tramo = TramoEnvio(id_transportista=id_transportista, origen=origen, destino=destino,
                           fecha_hora_salida=fecha_hora_salida, entregado_por=entregado_por,
                           temperatura_salida_c=temperatura_salida, observaciones=observaciones)
        remito.registrar_tramo(tramo)
        self._remitos.guardar_tramo(tramo)
        return tramo

    def _bioquimico_que_recibe(self, id_receptor: int | None, remito: RemitoBiologico) -> tuple[str, str]:
        bioquimico = self._bioquimicos.obtener_por_id(id_receptor) if id_receptor else None
        if bioquimico is None or bioquimico.id_laboratorio != remito.id_laboratorio_destino:
            raise ValidacionError("Seleccione un bioquímico del laboratorio de destino.")
        return bioquimico.nombre_completo(), remito.nombre_laboratorio

    def _transportista_que_recibe(self, id_receptor: int | None, actual: TramoEnvio | None,
                                  nombre_laboratorio: str, lugar: str | None) -> tuple[str, str]:
        transportista = self._transportistas.obtener_por_id(id_receptor) if id_receptor else None
        if transportista is None:
            raise ValidacionError("Seleccione el transportista que recibe la conservadora.")
        if actual and transportista.id == actual.id_transportista:
            raise ValidacionError("En una posta debe recibir otro transportista, no el que trae el tramo.")
        lugar = (lugar or "").strip()
        if not lugar:
            raise ValidacionError("Indique el lugar de entrega.")
        if lugar == nombre_laboratorio:
            raise ValidacionError("El lugar de entrega no puede ser el laboratorio de destino.")
        return transportista.razon_social, lugar

    def _validar_continuacion(self, remito: RemitoBiologico, origen: str, entregado_por: str) -> None:
        """El tramo siguiente sale de donde llegó el anterior, entregado por quien lo recibió."""
        actual = remito.tramo_actual()
        if actual is None or actual.esta_abierto():
            return
        if es_arribo_a_laboratorio(actual.destino, actual.recibido_por, remito.nombre_laboratorio,
                                   self._nombres_bioquimicos(remito.id_laboratorio_destino)):
            raise ValidacionError("El remito ya llegó al laboratorio. La verificación del precinto se hace en Recepción.")
        if origen.strip() != actual.destino:
            raise ValidacionError("El origen del nuevo tramo debe ser el lugar donde llegó el tramo anterior.")
        if entregado_por.strip() != actual.recibido_por:
            raise ValidacionError("Quien entrega el nuevo tramo debe ser quien recibió el tramo anterior.")

    def _nombres_bioquimicos(self, id_laboratorio: int) -> set[str]:
        return {b.nombre_completo() for b in self._bioquimicos.listar_por_laboratorio(id_laboratorio)}

    def _validar_transportista(self, id_transportista: int) -> None:
        if self._transportistas.obtener_por_id(id_transportista) is None:
            raise ValidacionError("Seleccione el transportista.")

    def _actualizar_ordenes(self, remito: RemitoBiologico) -> None:
        for id_orden in {m.id_orden for m in remito.muestras}:
            orden = self._ordenes.obtener_por_id(id_orden)
            orden.actualizar_estado()
            self._ordenes.actualizar_estado(orden)

    # --- Nueva extracción para una muestra rechazada ------------------------------------------
    def reextraer_muestra(self, id_muestra: int, id_veterinario: int, volumen: float | None = None,
                          fecha_hora: datetime | None = None) -> Muestra:
        """Registra una nueva extracción y le reasigna los análisis que quedaron sin resultado.

        Quien extrae debe ser un veterinario de la clínica donde se tomó la muestra original.
        La muestra rechazada conserva su historial: la trazabilidad no se modifica.
        """
        anterior = self._muestra(id_muestra)
        if anterior.nombre_estado() != "RECHAZADA":
            raise TransicionInvalidaError("Solo se puede repetir la extracción de una muestra rechazada.")
        orden = self._ordenes.obtener_por_id(anterior.id_orden)
        pendientes = [a for a in orden.analisis if a.id_muestra == anterior.id and not a.tiene_resultado()]
        if not pendientes:
            raise ValidacionError("La muestra ya fue reemplazada por una nueva extracción.")
        id_clinica, _ = self._muestras.origen_y_destino(anterior.id)
        responsable = self._veterinario_de_la_clinica(id_veterinario, id_clinica, "el responsable de la extracción",
                                                      "la clínica donde se extrajo la muestra")
        nueva = orden.registrar_extraccion(anterior.tipo, volumen or anterior.volumen_ml,
                                           id_veterinario=responsable.id, responsable=responsable.nombre_completo(),
                                           fecha_hora=fecha_hora or fechas.ahora())
        with self._conexion.transaccion():
            nueva.id_orden = orden.id
            self._muestras.insertar(nueva)
            for analisis in pendientes:
                self._ordenes.reasignar_muestra(analisis.id, nueva.id)
        return nueva
