"""Proceso 1: administrar clientes (responsables de las mascotas)."""
from app.dominio.excepciones import EntidadNoEncontradaError, ValidacionError
from app.dominio.personas import Cliente
from app.persistencia.daos.mascota_dao import MascotaDAO
from app.persistencia.daos.personas_dao import ClienteDAO


class ClienteService:
    def __init__(self, clientes: ClienteDAO, mascotas: MascotaDAO):
        self._clientes = clientes
        self._mascotas = mascotas

    def obtener(self, id_cliente: int) -> Cliente:
        cliente = self._clientes.obtener_por_id(id_cliente)
        if cliente is None:
            raise EntidadNoEncontradaError("el cliente", id_cliente)
        for mascota in self._mascotas.listar_por_cliente(id_cliente):
            cliente.agregar_mascota(mascota)
        return cliente

    def _validar_dni_unico(self, cliente: Cliente) -> None:
        existente = self._clientes.obtener_por_dni(cliente.dni)
        if existente and existente.id != cliente.id:
            raise ValidacionError(f"Ya existe un cliente con DNI {cliente.dni} ({existente.nombre_completo()}).")

    def alta(self, **datos) -> Cliente:
        cliente = Cliente(**datos)
        cliente.validar()
        self._validar_dni_unico(cliente)
        self._clientes.insertar(cliente)
        return cliente

    def modificar(self, cliente: Cliente) -> None:
        cliente.validar()
        self._validar_dni_unico(cliente)
        self._clientes.actualizar(cliente)

    def baja(self, id_cliente: int) -> None:
        """Baja lógica: el cliente sigue siendo el responsable registrado de sus mascotas."""
        cliente = self.obtener(id_cliente)
        cliente.activo = False
        self._clientes.actualizar(cliente)

    def reactivar(self, id_cliente: int) -> None:
        cliente = self.obtener(id_cliente)
        cliente.activo = True
        self._clientes.actualizar(cliente)

    def buscar(self, texto: str = "", incluir_inactivos: bool = False) -> list[dict]:
        return self._clientes.listar_resumen(texto, incluir_inactivos)

    def listar_activos(self) -> list[Cliente]:
        return self._clientes.listar_activos()
