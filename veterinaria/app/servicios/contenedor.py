"""Raíz de composición: crea una vez los DAO y los servicios y los conecta entre sí.

La interfaz solo conoce este contenedor; nunca accede directamente a los DAO ni a SQLite.
"""
from app.persistencia.conexion import ConexionBD
from app.persistencia.daos.atencion_dao import AtencionDAO
from app.persistencia.daos.catalogos_dao import (ClinicaDAO, ConservadoraDAO, EspecieDAO, LaboratorioDAO,
                                                 ServicioClinicoDAO, TipoAnalisisDAO, TransportistaDAO, VacunaDAO,
                                                 VacunaObligatoriaDAO)
from app.persistencia.daos.comprobante_dao import ComprobanteDAO
from app.persistencia.daos.derivacion_dao import MuestraDAO, OrdenDerivacionDAO
from app.persistencia.daos.mascota_dao import HistoriaClinicaDAO, MascotaDAO
from app.persistencia.daos.personas_dao import BioquimicoDAO, ClienteDAO, VeterinarioDAO
from app.persistencia.daos.remito_dao import RecepcionDAO, RemitoDAO
from app.persistencia.daos.reporte_dao import ReporteDAO
from app.persistencia.daos.resultado_dao import ResultadoDAO
from app.persistencia.daos.turno_dao import TurnoDAO
from app.servicios.atencion_service import AtencionService
from app.servicios.catalogo_service import CatalogoService
from app.servicios.cliente_service import ClienteService
from app.servicios.derivacion_service import DerivacionService
from app.servicios.facturacion_service import FacturacionService
from app.servicios.laboratorio_service import LaboratorioService
from app.servicios.mascota_service import MascotaService
from app.servicios.reporte_service import ReporteService
from app.servicios.turno_service import TurnoService


class Servicios:
    def __init__(self, conexion: ConexionBD | None = None):
        bd = conexion or ConexionBD.obtener_instancia()
        # --- DAO ---
        clientes, veterinarios, bioquimicos = ClienteDAO(bd), VeterinarioDAO(bd), BioquimicoDAO(bd)
        clinicas, laboratorios, transportistas = ClinicaDAO(bd), LaboratorioDAO(bd), TransportistaDAO(bd)
        especies, vacunas, esquemas = EspecieDAO(bd), VacunaDAO(bd), VacunaObligatoriaDAO(bd)
        tipos_analisis, servicios_clinicos, conservadoras = TipoAnalisisDAO(bd), ServicioClinicoDAO(bd), ConservadoraDAO(bd)
        mascotas, historias, turnos, atenciones = MascotaDAO(bd), HistoriaClinicaDAO(bd), TurnoDAO(bd), AtencionDAO(bd)
        ordenes, muestras, remitos, recepciones = OrdenDerivacionDAO(bd), MuestraDAO(bd), RemitoDAO(bd), RecepcionDAO(bd)
        resultados, comprobantes = ResultadoDAO(bd), ComprobanteDAO(bd)

        # --- Servicios ---
        self.clientes = ClienteService(clientes, mascotas)
        self.mascotas = MascotaService(mascotas, historias, clientes, especies, atenciones, ordenes, turnos, bd)
        self.turnos = TurnoService(turnos, veterinarios, mascotas)
        self.atenciones = AtencionService(atenciones, historias, self.mascotas, veterinarios, turnos, vacunas, esquemas,
                                          ordenes, tipos_analisis, laboratorios, bd)
        self.derivaciones = DerivacionService(muestras, remitos, conservadoras, ordenes, transportistas, bd)
        self.laboratorio = LaboratorioService(remitos, recepciones, muestras, ordenes, resultados, bioquimicos,
                                              conservadoras, bd)
        self.facturacion = FacturacionService(comprobantes, atenciones, servicios_clinicos, ordenes)
        self.reportes = ReporteService(ReporteDAO(bd), mascotas, especies)
        self.catalogos = CatalogoService({
            "veterinario": veterinarios, "bioquimico": bioquimicos, "clinica": clinicas, "laboratorio": laboratorios,
            "transportista": transportistas, "especie": especies, "vacuna": vacunas, "esquema": esquemas,
            "tipo_analisis": tipos_analisis, "servicio": servicios_clinicos, "conservadora": conservadoras,
        })
