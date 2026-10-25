"""ABM genérico de las tablas de referencia (veterinarios, clínicas, conservadoras, análisis, etc.)."""
from app.dominio.excepciones import ErrorPersistencia, ValidacionError
from app.persistencia.daos.base_dao import BaseDAO


class CatalogoService:
    def __init__(self, daos: dict[str, BaseDAO]):
        self._daos = daos

    def _dao(self, entidad: str) -> BaseDAO:
        return self._daos[entidad]

    def listar(self, entidad: str) -> list:
        return self._dao(entidad).listar()

    def obtener(self, entidad: str, id_: int):
        return self._dao(entidad).obtener_por_id(id_)

    def guardar(self, entidad: str, objeto) -> None:
        objeto.validar()
        dao = self._dao(entidad)
        if objeto.id is None:
            dao.insertar(objeto)
        else:
            dao.actualizar(objeto)

    def eliminar(self, entidad: str, id_: int) -> None:
        try:
            self._dao(entidad).eliminar(id_)
        except ErrorPersistencia as error:
            if "relacionado" in str(error):
                raise ValidacionError("No se puede eliminar: el registro está siendo utilizado por otros datos.") from error
            raise
