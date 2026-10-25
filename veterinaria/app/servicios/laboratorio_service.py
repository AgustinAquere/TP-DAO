"""Procesos 6 y 7 (laboratorio): recepción verificando el precinto y registro de resultados."""
from datetime import datetime

from app import config
from app.dominio.enums import EstadoPrecinto
from app.dominio.excepciones import EntidadNoEncontradaError, TransicionInvalidaError, ValidacionError
from app.dominio.laboratorio import DetalleResultado, RecepcionLaboratorio, ResultadoAnalisis
from app.dominio.remito import RemitoBiologico
from app.persistencia.conexion import ConexionBD
from app.persistencia.daos.catalogos_dao import ConservadoraDAO
from app.persistencia.daos.derivacion_dao import MuestraDAO, OrdenDerivacionDAO
from app.persistencia.daos.personas_dao import BioquimicoDAO
from app.persistencia.daos.remito_dao import RecepcionDAO, RemitoDAO
from app.persistencia.daos.resultado_dao import ResultadoDAO
from app.utils import fechas


class LaboratorioService:
    def __init__(self, remitos: RemitoDAO, recepciones: RecepcionDAO, muestras: MuestraDAO,
                 ordenes: OrdenDerivacionDAO, resultados: ResultadoDAO, bioquimicos: BioquimicoDAO,
                 conservadoras: ConservadoraDAO, conexion: ConexionBD):
        self._remitos = remitos
        self._recepciones = recepciones
        self._muestras = muestras
        self._ordenes = ordenes
        self._resultados = resultados
        self._bioquimicos = bioquimicos
        self._conservadoras = conservadoras
        self._conexion = conexion

    def _bioquimico_del_laboratorio(self, id_bioquimico: int, id_laboratorio: int):
        bioquimico = self._bioquimicos.obtener_por_id(id_bioquimico)
        if bioquimico is None:
            raise ValidacionError("Seleccione el bioquímico responsable.")
        if bioquimico.id_laboratorio != id_laboratorio:
            raise ValidacionError(f"{bioquimico.nombre_completo()} no pertenece al laboratorio de destino.")
        return bioquimico

    # --- Proceso 6: recepción ---------------------------------------------------------------
    def remitos_por_recibir(self, id_laboratorio: int | None = None) -> list[dict]:
        return self._remitos.listar_resumen("EN_TRANSITO", id_laboratorio)

    def registrar_recepcion(self, id_remito: int, id_bioquimico: int, precinto_intacto: bool,
                            temperatura_arribo: float | None = None, observacion: str | None = None,
                            fecha_hora: datetime | None = None) -> RemitoBiologico:
        """Verifica el precinto: si llegó roto, el remito y todas sus muestras quedan rechazados
        y no podrán procesarse. Con precinto intacto, cada muestra se evalúa por temperatura y viabilidad."""
        remito = self._remitos.obtener_por_id(id_remito)
        if remito is None:
            raise EntidadNoEncontradaError("el remito", id_remito)
        bioquimico = self._bioquimico_del_laboratorio(id_bioquimico, remito.id_laboratorio_destino)
        recepcion = RecepcionLaboratorio(
            id_remito=id_remito, id_bioquimico=id_bioquimico, fecha_hora=fecha_hora or fechas.ahora(),
            estado_precinto_verificado=EstadoPrecinto.INTACTO if precinto_intacto else EstadoPrecinto.ROTO,
            temperatura_arribo_c=temperatura_arribo,
            motivo_rechazo=None if precinto_intacto else (observacion or None))
        remito.recibir(recepcion, responsable=bioquimico.nombre_completo())
        with self._conexion.transaccion():
            self._recepciones.insertar(recepcion)
            self._remitos.guardar_precinto(remito.precinto)
            self._remitos.guardar_tramo(remito.tramo_actual())
            self._remitos.actualizar_estado(remito)
            for muestra in remito.muestras:
                self._muestras.guardar_transicion(muestra)
            self._conservadoras.marcar_disponible(remito.id_conservadora, True)
        return remito

    # --- Proceso 7: resultados -----------------------------------------------------------------
    def analisis_pendientes(self, id_laboratorio: int | None = None) -> list[dict]:
        return self._resultados.analisis_pendientes(id_laboratorio)

    def plantilla_resultado(self, codigo_analisis: str) -> list[DetalleResultado]:
        return [DetalleResultado(parametro=parametro, valor=0.0, unidad=unidad, valor_ref_min=minimo,
                                 valor_ref_max=maximo)
                for parametro, unidad, minimo, maximo in config.PLANTILLAS_RESULTADO.get(codigo_analisis, [])]

    def registrar_resultado(self, id_analisis_solicitado: int, id_bioquimico: int, detalles: list[DetalleResultado],
                            interpretacion: str | None = None, observaciones: str | None = None,
                            fecha_hora: datetime | None = None) -> ResultadoAnalisis:
        analisis = self._ordenes.obtener_analisis(id_analisis_solicitado)
        if analisis is None:
            raise EntidadNoEncontradaError("el análisis solicitado", id_analisis_solicitado)
        if analisis.tiene_resultado():
            raise ValidacionError("El análisis ya tiene un resultado registrado.")
        muestra = analisis.muestra
        if muestra.nombre_estado() != "RECIBIDA":
            # Validación del enunciado: una muestra rechazada (p. ej. por precinto roto) no se procesa
            raise TransicionInvalidaError(
                f"La muestra {muestra.codigo} está «{muestra.etiqueta_estado()}»: solo se procesan muestras recibidas.")
        orden = self._ordenes.obtener_por_id(analisis.id_orden)
        bioquimico = self._bioquimico_del_laboratorio(id_bioquimico, orden.id_laboratorio)

        resultado = ResultadoAnalisis(id_analisis_solicitado=id_analisis_solicitado, id_bioquimico=id_bioquimico,
                                      fecha_hora=fecha_hora or fechas.ahora(), interpretacion=interpretacion,
                                      observaciones=observaciones, detalles=list(detalles))
        resultado.validar()
        with self._conexion.transaccion():
            self._resultados.insertar(resultado)
            orden = self._ordenes.obtener_por_id(analisis.id_orden)
            sin_resultado = [a for a in orden.analisis if a.id_muestra == muestra.id and not a.tiene_resultado()]
            if not sin_resultado:  # todos los análisis de la muestra informados: Recibida -> Analizada
                muestra.analizar(responsable=bioquimico.nombre_completo(), fecha_hora=resultado.fecha_hora)
                self._muestras.guardar_transicion(muestra)
            orden.actualizar_estado()
            self._ordenes.actualizar_estado(orden)
        return resultado

    def resultados(self, id_laboratorio: int | None = None, texto: str = "") -> list[dict]:
        return self._resultados.listar_resumen(id_laboratorio, texto)

    def obtener_resultado(self, id_resultado: int) -> ResultadoAnalisis:
        resultado = self._resultados.obtener_por_id(id_resultado)
        if resultado is None:
            raise EntidadNoEncontradaError("el resultado", id_resultado)
        return resultado
