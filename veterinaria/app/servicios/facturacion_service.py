"""Proceso 7 (clínica): emitir comprobantes de atención aplicando la estrategia de tarifa correspondiente."""
from datetime import date, datetime

from app import config
from app.dominio.atencion import Atencion
from app.dominio.enums import TipoAtencion, TipoItem
from app.dominio.excepciones import EntidadNoEncontradaError, ValidacionError
from app.dominio.facturacion import ComprobanteAtencion, ItemComprobante, ServicioClinico
from app.dominio.tarifas import EstrategiaTarifa, TarifaConsulta, TarifaControl, TarifaUrgencia
from app.persistencia.daos.atencion_dao import AtencionDAO
from app.persistencia.daos.catalogos_dao import ServicioClinicoDAO
from app.persistencia.daos.comprobante_dao import ComprobanteDAO
from app.persistencia.daos.derivacion_dao import OrdenDerivacionDAO
from app.utils import fechas


class FacturacionService:
    def __init__(self, comprobantes: ComprobanteDAO, atenciones: AtencionDAO, servicios: ServicioClinicoDAO,
                 ordenes: OrdenDerivacionDAO):
        self._comprobantes = comprobantes
        self._atenciones = atenciones
        self._servicios = servicios
        self._ordenes = ordenes
        # La estrategia se elige por tipo de atención con un diccionario, sin if/elif
        self._estrategias = {
            TipoAtencion.CONSULTA: lambda atencion: TarifaConsulta(),
            TipoAtencion.CONTROL: lambda atencion: TarifaControl(),
            TipoAtencion.URGENCIA: lambda atencion: TarifaUrgencia(atencion.fecha_hora),
        }

    def estrategia_para(self, atencion: Atencion) -> EstrategiaTarifa:
        return self._estrategias[atencion.tipo](atencion)

    def descripcion_tarifa(self, id_atencion: int) -> str:
        return self.estrategia_para(self._atencion(id_atencion)).descripcion()

    def _atencion(self, id_atencion: int) -> Atencion:
        atencion = self._atenciones.obtener_por_id(id_atencion)
        if atencion is None:
            raise EntidadNoEncontradaError("la atención", id_atencion)
        return atencion

    def atenciones_sin_comprobante(self, id_clinica: int | None = None) -> list[dict]:
        return self._atenciones.listar_resumen(id_clinica=id_clinica, sin_comprobante=True)

    def servicios_clinicos(self) -> list[ServicioClinico]:
        return self._servicios.listar()

    def items_sugeridos(self, id_atencion: int) -> list[ItemComprobante]:
        """Servicio según el tipo de atención, análisis derivados y vacunas aplicadas."""
        atencion = self._atencion(id_atencion)
        items = []
        servicio = self._servicios.obtener_por_codigo(config.SERVICIO_POR_TIPO_ATENCION[atencion.tipo.value])
        if servicio:
            items.append(ItemComprobante(tipo=TipoItem.SERVICIO_CLINICO, descripcion=servicio.nombre,
                                         precio_unitario=servicio.precio_base, id_servicio=servicio.id))
        for orden in self._ordenes.listar_por_atencion(id_atencion):
            items += [ItemComprobante(tipo=TipoItem.ANALISIS_LABORATORIO,
                                      descripcion=f"{a.tipo_analisis.nombre} (orden {orden.numero})",
                                      precio_unitario=a.tipo_analisis.precio, id_tipo_analisis=a.id_tipo_analisis)
                      for a in orden.analisis]
        items += [ItemComprobante(tipo=TipoItem.VACUNA, descripcion=f"Vacuna {ap.nombre_vacuna} (lote {ap.lote})",
                                  precio_unitario=config.PRECIO_SUGERIDO_VACUNA, id_vacuna=ap.id_vacuna)
                  for ap in atencion.aplicaciones]
        return items

    def preparar(self, id_atencion: int, items: list[ItemComprobante] | None = None,
                 fecha_emision: datetime | None = None) -> ComprobanteAtencion:
        """Arma el comprobante (sin guardarlo) para previsualizar subtotal, ajuste y total."""
        atencion = self._atencion(id_atencion)
        comprobante = ComprobanteAtencion(id_atencion=id_atencion, id_cliente=self._atenciones.id_cliente_de(id_atencion),
                                          id_clinica=atencion.id_clinica,
                                          numero=self._comprobantes.siguiente_numero(atencion.id_clinica),
                                          fecha_emision=fecha_emision or fechas.ahora())
        comprobante.set_estrategia(self.estrategia_para(atencion))
        for item in (self.items_sugeridos(id_atencion) if items is None else items):
            comprobante.agregar_item(item)
        return comprobante

    def emitir(self, id_atencion: int, items: list[ItemComprobante] | None = None,
               fecha_emision: datetime | None = None) -> ComprobanteAtencion:
        if self._comprobantes.obtener_por_atencion(id_atencion):
            raise ValidacionError("La atención ya tiene un comprobante emitido.")
        comprobante = self.preparar(id_atencion, items, fecha_emision)
        comprobante.emitir()
        self._comprobantes.insertar(comprobante)
        return comprobante

    def obtener(self, id_comprobante: int) -> ComprobanteAtencion:
        comprobante = self._comprobantes.obtener_por_id(id_comprobante)
        if comprobante is None:
            raise EntidadNoEncontradaError("el comprobante", id_comprobante)
        return comprobante

    def listar(self, desde: date | None = None, hasta: date | None = None, id_clinica: int | None = None) -> list[dict]:
        return self._comprobantes.listar_resumen(desde, hasta, id_clinica)
