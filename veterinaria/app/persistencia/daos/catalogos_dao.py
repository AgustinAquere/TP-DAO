"""DAO de las tablas de referencia: clínicas, laboratorio, transportistas, especies, vacunas,
esquema obligatorio, tipos de análisis, servicios clínicos y conservadoras."""
from app.dominio.derivacion import TipoAnalisis
from app.dominio.enums import TipoMuestra
from app.dominio.envio import Conservadora
from app.dominio.facturacion import ServicioClinico
from app.dominio.mascota import Especie
from app.dominio.organizaciones import Clinica, LaboratorioCentral, Transportista
from app.dominio.vacunas import Vacuna, VacunaObligatoria
from app.persistencia.daos.base_dao import BaseDAO


class ClinicaDAO(BaseDAO[Clinica]):
    tabla, clave = "clinica", "id_clinica"
    columnas = ("nombre", "direccion", "telefono", "cuit")
    orden = "nombre"

    def _a_entidad(self, fila) -> Clinica:
        return Clinica(id=fila["id_clinica"], nombre=fila["nombre"], direccion=fila["direccion"],
                       telefono=fila["telefono"], cuit=fila["cuit"])

    def _a_registro(self, c: Clinica) -> tuple:
        return (c.nombre.strip(), c.direccion.strip(), c.telefono, c.cuit.strip())


class LaboratorioDAO(BaseDAO[LaboratorioCentral]):
    tabla, clave = "laboratorio_central", "id_laboratorio"
    columnas = ("nombre", "direccion", "telefono")
    orden = "nombre"

    def _a_entidad(self, fila) -> LaboratorioCentral:
        return LaboratorioCentral(id=fila["id_laboratorio"], nombre=fila["nombre"], direccion=fila["direccion"],
                                  telefono=fila["telefono"])

    def _a_registro(self, l: LaboratorioCentral) -> tuple:
        return (l.nombre.strip(), l.direccion.strip(), l.telefono)


class TransportistaDAO(BaseDAO[Transportista]):
    tabla, clave = "transportista", "id_transportista"
    columnas = ("razon_social", "cuit", "telefono", "patente_vehiculo")
    orden = "razon_social"

    def _a_entidad(self, fila) -> Transportista:
        return Transportista(id=fila["id_transportista"], razon_social=fila["razon_social"], cuit=fila["cuit"],
                             telefono=fila["telefono"], patente_vehiculo=fila["patente_vehiculo"])

    def _a_registro(self, t: Transportista) -> tuple:
        return (t.razon_social.strip(), t.cuit.strip(), t.telefono, t.patente_vehiculo)


class VacunaObligatoriaDAO(BaseDAO[VacunaObligatoria]):
    tabla, clave = "vacuna_obligatoria", "id_vacuna_obligatoria"
    columnas = ("id_especie", "id_vacuna", "edad_minima_semanas", "frecuencia_refuerzo_dias")

    _SELECT = """SELECT vo.*, v.nombre AS nombre_vacuna FROM vacuna_obligatoria vo
                 JOIN vacuna v ON v.id_vacuna = vo.id_vacuna"""

    def _a_entidad(self, fila) -> VacunaObligatoria:
        return VacunaObligatoria(id=fila["id_vacuna_obligatoria"], id_especie=fila["id_especie"],
                                 id_vacuna=fila["id_vacuna"], edad_minima_semanas=fila["edad_minima_semanas"],
                                 frecuencia_refuerzo_dias=fila["frecuencia_refuerzo_dias"],
                                 nombre_vacuna=fila["nombre_vacuna"] if "nombre_vacuna" in fila.keys() else "")

    def _a_registro(self, vo: VacunaObligatoria) -> tuple:
        return (vo.id_especie, vo.id_vacuna, vo.edad_minima_semanas, vo.frecuencia_refuerzo_dias)

    def obtener_por_id(self, id_: int) -> VacunaObligatoria | None:
        fila = self.conexion.consultar_uno(f"{self._SELECT} WHERE vo.id_vacuna_obligatoria = ?", (id_,))
        return None if fila is None else self._a_entidad(fila)

    def listar(self) -> list[VacunaObligatoria]:
        return self._mapear(self.conexion.consultar(f"{self._SELECT} ORDER BY vo.id_especie, vo.edad_minima_semanas"))

    def listar_por_especie(self, id_especie: int) -> list[VacunaObligatoria]:
        return self._mapear(self.conexion.consultar(
            f"{self._SELECT} WHERE vo.id_especie = ? ORDER BY vo.edad_minima_semanas", (id_especie,)))

    def obtener(self, id_especie: int, id_vacuna: int) -> VacunaObligatoria | None:
        fila = self.conexion.consultar_uno(f"{self._SELECT} WHERE vo.id_especie = ? AND vo.id_vacuna = ?",
                                           (id_especie, id_vacuna))
        return None if fila is None else self._a_entidad(fila)


class EspecieDAO(BaseDAO[Especie]):
    tabla, clave = "especie", "id_especie"
    columnas = ("nombre",)
    orden = "nombre"

    def __init__(self, conexion=None):
        super().__init__(conexion)
        self._esquemas = VacunaObligatoriaDAO(self.conexion)

    def _a_entidad(self, fila) -> Especie:
        return Especie(id=fila["id_especie"], nombre=fila["nombre"],
                       esquema=self._esquemas.listar_por_especie(fila["id_especie"]))

    def _a_registro(self, e: Especie) -> tuple:
        return (e.nombre.strip(),)


class VacunaDAO(BaseDAO[Vacuna]):
    tabla, clave = "vacuna", "id_vacuna"
    columnas = ("nombre", "laboratorio_fabricante")
    orden = "nombre"

    def _a_entidad(self, fila) -> Vacuna:
        return Vacuna(id=fila["id_vacuna"], nombre=fila["nombre"],
                      laboratorio_fabricante=fila["laboratorio_fabricante"])

    def _a_registro(self, v: Vacuna) -> tuple:
        return (v.nombre.strip(), v.laboratorio_fabricante)


class TipoAnalisisDAO(BaseDAO[TipoAnalisis]):
    tabla, clave = "tipo_analisis", "id_tipo_analisis"
    columnas = ("codigo", "nombre", "tipo_muestra_requerida", "temp_min_c", "temp_max_c",
                "horas_max_viabilidad", "precio")
    orden = "nombre"

    def _a_entidad(self, fila) -> TipoAnalisis:
        return TipoAnalisis(id=fila["id_tipo_analisis"], codigo=fila["codigo"], nombre=fila["nombre"],
                            tipo_muestra_requerida=TipoMuestra(fila["tipo_muestra_requerida"]),
                            temp_min_c=fila["temp_min_c"], temp_max_c=fila["temp_max_c"],
                            horas_max_viabilidad=fila["horas_max_viabilidad"], precio=fila["precio"])

    def _a_registro(self, t: TipoAnalisis) -> tuple:
        return (t.codigo.strip().upper(), t.nombre.strip(), TipoMuestra(t.tipo_muestra_requerida).value,
                t.temp_min_c, t.temp_max_c, t.horas_max_viabilidad, t.precio)

    def obtener_por_codigo(self, codigo: str) -> TipoAnalisis | None:
        return self._obtener_donde("codigo = ?", (codigo,))

    def listar_por_muestra(self, id_muestra: int) -> list[TipoAnalisis]:
        return self._listar_donde(
            "id_tipo_analisis IN (SELECT id_tipo_analisis FROM analisis_solicitado WHERE id_muestra = ?)",
            (id_muestra,))


class ServicioClinicoDAO(BaseDAO[ServicioClinico]):
    tabla, clave = "servicio_clinico", "id_servicio"
    columnas = ("codigo", "nombre", "precio_base")
    orden = "nombre"

    def _a_entidad(self, fila) -> ServicioClinico:
        return ServicioClinico(id=fila["id_servicio"], codigo=fila["codigo"], nombre=fila["nombre"],
                               precio_base=fila["precio_base"])

    def _a_registro(self, s: ServicioClinico) -> tuple:
        return (s.codigo.strip().upper(), s.nombre.strip(), s.precio_base)

    def obtener_por_codigo(self, codigo: str) -> ServicioClinico | None:
        return self._obtener_donde("codigo = ?", (codigo,))


class ConservadoraDAO(BaseDAO[Conservadora]):
    tabla, clave = "conservadora", "id_conservadora"
    columnas = ("codigo", "capacidad", "temp_min_c", "temp_max_c", "disponible")
    orden = "codigo"

    def _a_entidad(self, fila) -> Conservadora:
        return Conservadora(id=fila["id_conservadora"], codigo=fila["codigo"], capacidad=fila["capacidad"],
                            temp_min_c=fila["temp_min_c"], temp_max_c=fila["temp_max_c"],
                            disponible=bool(fila["disponible"]))

    def _a_registro(self, c: Conservadora) -> tuple:
        return (c.codigo.strip().upper(), c.capacidad, c.temp_min_c, c.temp_max_c, int(c.disponible))

    def listar_disponibles(self) -> list[Conservadora]:
        return self._listar_donde("disponible = 1")

    def marcar_disponible(self, id_conservadora: int, disponible: bool) -> None:
        self.conexion.ejecutar("UPDATE conservadora SET disponible = ? WHERE id_conservadora = ?",
                               (int(disponible), id_conservadora))
