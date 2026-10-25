"""Proceso 2: administrar mascotas y sus historias clínicas."""
from datetime import date

from app.dominio.excepciones import EntidadNoEncontradaError, ValidacionError
from app.dominio.mascota import Especie, HistoriaClinica, Mascota
from app.persistencia.conexion import ConexionBD
from app.persistencia.daos.atencion_dao import AtencionDAO
from app.persistencia.daos.catalogos_dao import EspecieDAO
from app.persistencia.daos.derivacion_dao import OrdenDerivacionDAO
from app.persistencia.daos.mascota_dao import HistoriaClinicaDAO, MascotaDAO
from app.persistencia.daos.personas_dao import ClienteDAO
from app.persistencia.daos.turno_dao import TurnoDAO


class MascotaService:
    def __init__(self, mascotas: MascotaDAO, historias: HistoriaClinicaDAO, clientes: ClienteDAO, especies: EspecieDAO,
                 atenciones: AtencionDAO, ordenes: OrdenDerivacionDAO, turnos: TurnoDAO, conexion: ConexionBD):
        self._mascotas = mascotas
        self._historias = historias
        self._clientes = clientes
        self._especies = especies
        self._atenciones = atenciones
        self._ordenes = ordenes
        self._turnos = turnos
        self._conexion = conexion

    def _validar_responsable(self, id_cliente: int | None) -> None:
        """Validación del enunciado: toda mascota debe tener un responsable asociado (y existente)."""
        if id_cliente is None:
            raise ValidacionError("Toda mascota debe tener un responsable asociado.")
        responsable = self._clientes.obtener_por_id(id_cliente)
        if responsable is None:
            raise ValidacionError("El responsable indicado no existe.")
        if not responsable.activo:
            raise ValidacionError(f"El cliente {responsable.nombre_completo()} está dado de baja.")

    def alta(self, id_cliente: int | None, fecha_apertura: date | None = None, **datos) -> Mascota:
        """Registra la mascota y abre su historia clínica en una misma transacción."""
        mascota = Mascota(id_cliente=id_cliente, **datos)
        self._validar_responsable(id_cliente)
        mascota.validar()
        with self._conexion.transaccion():
            self._mascotas.insertar(mascota)
            self._historias.insertar(HistoriaClinica(id_mascota=mascota.id, numero=self._historias.siguiente_numero(),
                                                     fecha_apertura=fecha_apertura or date.today()))
        return mascota

    def modificar(self, mascota: Mascota) -> None:
        self._validar_responsable(mascota.id_cliente)
        mascota.validar()
        self._mascotas.actualizar(mascota)

    def eliminar(self, id_mascota: int) -> None:
        """Solo se permite si la mascota no tiene atenciones ni turnos (no se borran datos clínicos)."""
        historia = self._historias.obtener_por_mascota(id_mascota)
        if historia and self._atenciones.contar("id_historia = ?", (historia.id,)):
            raise ValidacionError("La mascota tiene atenciones registradas en su historia clínica: no puede eliminarse.")
        if self._turnos.contar("id_mascota = ?", (id_mascota,)):
            raise ValidacionError("La mascota tiene turnos registrados: no puede eliminarse.")
        with self._conexion.transaccion():
            if historia:
                self._historias.eliminar(historia.id)
            self._mascotas.eliminar(id_mascota)

    def obtener(self, id_mascota: int) -> Mascota:
        """Mascota con su especie (y esquema de vacunas) y las vacunas que recibió."""
        mascota = self._mascotas.obtener_por_id(id_mascota)
        if mascota is None:
            raise EntidadNoEncontradaError("la mascota", id_mascota)
        mascota.especie = self._especies.obtener_por_id(mascota.id_especie)
        mascota.aplicaciones = self._atenciones.aplicaciones_de_mascota(id_mascota)
        return mascota

    def listar(self, texto: str = "", id_cliente: int | None = None) -> list[dict]:
        return self._mascotas.listar_resumen(texto, id_cliente)

    def especies(self) -> list[Especie]:
        return self._especies.listar()

    def historia_clinica(self, id_mascota: int) -> HistoriaClinica:
        """Historia clínica con todas sus atenciones (tratamientos, vacunas y órdenes de derivación)."""
        historia = self._historias.obtener_por_mascota(id_mascota)
        if historia is None:
            raise EntidadNoEncontradaError("la historia clínica de la mascota", id_mascota)
        for atencion in self._atenciones.listar_por_historia(historia.id):
            atencion.ordenes = self._ordenes.listar_por_atencion(atencion.id)
            historia.agregar_atencion(atencion)
        return historia

    def actualizar_historia(self, id_mascota: int, observaciones: str | None, alergias: str | None) -> None:
        historia = self._historias.obtener_por_mascota(id_mascota)
        historia.observaciones_generales = observaciones
        historia.alergias = alergias
        self._historias.actualizar(historia)

    def vacunas_pendientes(self, id_mascota: int, fecha: date | None = None) -> list[dict]:
        mascota = self.obtener(id_mascota)
        fecha = fecha or date.today()
        return [{"vacuna": vo.nombre_vacuna, "exigible_desde": vo.fecha_vencimiento(mascota),
                 "nunca_aplicada": vo.ultima_aplicacion(mascota.aplicaciones) is None}
                for vo in mascota.vacunas_pendientes(fecha)]
