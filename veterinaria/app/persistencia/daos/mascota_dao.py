"""DAO de mascotas e historias clínicas."""
from app.dominio.enums import Sexo
from app.dominio.mascota import HistoriaClinica, Mascota
from app.persistencia.daos.base_dao import BaseDAO
from app.utils import fechas


class MascotaDAO(BaseDAO[Mascota]):
    tabla, clave = "mascota", "id_mascota"
    columnas = ("id_cliente", "id_especie", "nombre", "raza", "sexo", "fecha_nacimiento", "peso_kg", "microchip")
    orden = "nombre"

    def _a_entidad(self, fila) -> Mascota:
        return Mascota(id=fila["id_mascota"], id_cliente=fila["id_cliente"], id_especie=fila["id_especie"],
                       nombre=fila["nombre"], raza=fila["raza"], sexo=Sexo(fila["sexo"]) if fila["sexo"] else None,
                       fecha_nacimiento=fechas.fecha_desde_sql(fila["fecha_nacimiento"]), peso_kg=fila["peso_kg"],
                       microchip=fila["microchip"])

    def _a_registro(self, m: Mascota) -> tuple:
        return (m.id_cliente, m.id_especie, m.nombre.strip(), m.raza, Sexo(m.sexo).value if m.sexo else None,
                fechas.a_sql(m.fecha_nacimiento), m.peso_kg, (m.microchip or "").strip() or None)

    def listar_por_cliente(self, id_cliente: int) -> list[Mascota]:
        return self._listar_donde("id_cliente = ?", (id_cliente,))

    def listar_resumen(self, texto: str = "", id_cliente: int | None = None) -> list[dict]:
        """Mascotas con especie, responsable y número de historia clínica."""
        patron = f"%{texto.strip()}%"
        filtro_cliente = "AND m.id_cliente = ?" if id_cliente else ""
        parametros = (patron, patron, patron, patron) + ((id_cliente,) if id_cliente else ())
        return self._diccionarios(f"""
            SELECT m.*, e.nombre AS especie, c.apellido || ', ' || c.nombre AS responsable, c.dni AS dni_responsable,
                   c.telefono AS telefono_responsable, h.numero AS numero_historia, h.id_historia
              FROM mascota m
              JOIN especie e ON e.id_especie = m.id_especie
              JOIN cliente c ON c.id_cliente = m.id_cliente
              LEFT JOIN historia_clinica h ON h.id_mascota = m.id_mascota
             WHERE (m.nombre LIKE ? OR c.apellido LIKE ? OR c.dni LIKE ? OR IFNULL(m.microchip, '') LIKE ?)
                   {filtro_cliente}
             ORDER BY m.nombre, c.apellido""", parametros)


class HistoriaClinicaDAO(BaseDAO[HistoriaClinica]):
    tabla, clave = "historia_clinica", "id_historia"
    columnas = ("id_mascota", "numero", "fecha_apertura", "observaciones_generales", "alergias")
    orden = "numero"

    def _a_entidad(self, fila) -> HistoriaClinica:
        return HistoriaClinica(id=fila["id_historia"], id_mascota=fila["id_mascota"], numero=fila["numero"],
                               fecha_apertura=fechas.fecha_desde_sql(fila["fecha_apertura"]),
                               observaciones_generales=fila["observaciones_generales"], alergias=fila["alergias"])

    def _a_registro(self, h: HistoriaClinica) -> tuple:
        return (h.id_mascota, h.numero, fechas.a_sql(h.fecha_apertura), h.observaciones_generales, h.alergias)

    def obtener_por_mascota(self, id_mascota: int) -> HistoriaClinica | None:
        return self._obtener_donde("id_mascota = ?", (id_mascota,))

    def siguiente_numero(self) -> str:
        return f"HC-{self.siguiente_secuencia():06d}"
