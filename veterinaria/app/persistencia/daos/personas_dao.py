"""DAO de clientes, veterinarios (con su relación N:M con clínicas) y bioquímicos."""
from app.dominio.personas import Bioquimico, Cliente, Veterinario
from app.persistencia.daos.base_dao import BaseDAO
from app.utils import fechas


class ClienteDAO(BaseDAO[Cliente]):
    tabla, clave = "cliente", "id_cliente"
    columnas = ("dni", "nombre", "apellido", "telefono", "email", "direccion", "fecha_alta", "activo")
    orden = "apellido, nombre"

    def _a_entidad(self, fila) -> Cliente:
        return Cliente(id=fila["id_cliente"], dni=fila["dni"], nombre=fila["nombre"], apellido=fila["apellido"],
                       telefono=fila["telefono"], email=fila["email"], direccion=fila["direccion"],
                       fecha_alta=fechas.fecha_desde_sql(fila["fecha_alta"]), activo=bool(fila["activo"]))

    def _a_registro(self, c: Cliente) -> tuple:
        return (c.dni.strip(), c.nombre.strip(), c.apellido.strip(), c.telefono, c.email, c.direccion,
                fechas.a_sql(c.fecha_alta), int(c.activo))

    def obtener_por_dni(self, dni: str) -> Cliente | None:
        return self._obtener_donde("dni = ?", (dni.strip(),))

    def listar_resumen(self, texto: str = "", incluir_inactivos: bool = False) -> list[dict]:
        """Clientes con la cantidad de mascotas a cargo, filtrados por DNI, nombre o apellido."""
        patron = f"%{texto.strip()}%"
        return self._diccionarios(f"""
            SELECT c.*, COUNT(m.id_mascota) AS cantidad_mascotas
              FROM cliente c LEFT JOIN mascota m ON m.id_cliente = c.id_cliente
             WHERE (c.dni LIKE ? OR c.nombre LIKE ? OR c.apellido LIKE ?
                    OR (c.apellido || ', ' || c.nombre) LIKE ?)
               {'' if incluir_inactivos else 'AND c.activo = 1'}
             GROUP BY c.id_cliente
             ORDER BY c.apellido, c.nombre""", (patron, patron, patron, patron))

    def listar_activos(self) -> list[Cliente]:
        return self._listar_donde("activo = 1")


class VeterinarioDAO(BaseDAO[Veterinario]):
    tabla, clave = "veterinario", "id_veterinario"
    columnas = ("dni", "nombre", "apellido", "telefono", "email", "matricula", "especialidad")
    orden = "apellido, nombre"

    def _a_entidad(self, fila) -> Veterinario:
        ids = [f["id_clinica"] for f in self.conexion.consultar(
            "SELECT id_clinica FROM veterinario_clinica WHERE id_veterinario = ? ORDER BY id_clinica",
            (fila["id_veterinario"],))]
        return Veterinario(id=fila["id_veterinario"], dni=fila["dni"], nombre=fila["nombre"],
                           apellido=fila["apellido"], telefono=fila["telefono"], email=fila["email"],
                           matricula=fila["matricula"], especialidad=fila["especialidad"], ids_clinicas=ids)

    def _a_registro(self, v: Veterinario) -> tuple:
        return (v.dni.strip(), v.nombre.strip(), v.apellido.strip(), v.telefono, v.email, v.matricula.strip(),
                v.especialidad)

    def _guardar_clinicas(self, v: Veterinario) -> None:
        self.conexion.ejecutar("DELETE FROM veterinario_clinica WHERE id_veterinario = ?", (v.id,))
        self.conexion.ejecutar_muchos("INSERT INTO veterinario_clinica (id_veterinario, id_clinica) VALUES (?, ?)",
                                      [(v.id, id_clinica) for id_clinica in v.ids_clinicas])

    def insertar(self, v: Veterinario) -> int:
        with self.conexion.transaccion():
            super().insertar(v)
            self._guardar_clinicas(v)
        return v.id

    def actualizar(self, v: Veterinario) -> None:
        with self.conexion.transaccion():
            super().actualizar(v)
            self._guardar_clinicas(v)

    def eliminar(self, id_: int) -> None:
        with self.conexion.transaccion():
            self.conexion.ejecutar("DELETE FROM veterinario_clinica WHERE id_veterinario = ?", (id_,))
            super().eliminar(id_)

    def listar_por_clinica(self, id_clinica: int) -> list[Veterinario]:
        return self._listar_donde(
            "id_veterinario IN (SELECT id_veterinario FROM veterinario_clinica WHERE id_clinica = ?)", (id_clinica,))


class BioquimicoDAO(BaseDAO[Bioquimico]):
    tabla, clave = "bioquimico", "id_bioquimico"
    columnas = ("id_laboratorio", "dni", "nombre", "apellido", "telefono", "email", "matricula")
    orden = "apellido, nombre"

    def _a_entidad(self, fila) -> Bioquimico:
        return Bioquimico(id=fila["id_bioquimico"], id_laboratorio=fila["id_laboratorio"], dni=fila["dni"],
                          nombre=fila["nombre"], apellido=fila["apellido"], telefono=fila["telefono"],
                          email=fila["email"], matricula=fila["matricula"])

    def _a_registro(self, b: Bioquimico) -> tuple:
        return (b.id_laboratorio, b.dni.strip(), b.nombre.strip(), b.apellido.strip(), b.telefono, b.email,
                b.matricula.strip())

    def listar_por_laboratorio(self, id_laboratorio: int) -> list[Bioquimico]:
        return self._listar_donde("id_laboratorio = ?", (id_laboratorio,))
