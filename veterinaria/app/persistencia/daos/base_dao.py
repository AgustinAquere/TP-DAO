"""DAO genérico: implementa el CRUD (método plantilla) y delega el mapeo fila <-> objeto en cada subclase."""
import sqlite3
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.persistencia.conexion import ConexionBD

T = TypeVar("T")


class BaseDAO(ABC, Generic[T]):
    tabla: str = ""
    clave: str = ""
    columnas: tuple[str, ...] = ()   # columnas sin la clave primaria, en el orden de _a_registro()
    orden: str = ""                  # ORDER BY por defecto de listar()

    def __init__(self, conexion: ConexionBD | None = None):
        self.conexion = conexion or ConexionBD.obtener_instancia()

    # --- Mapeo: lo define cada DAO concreto ----------------------------------
    @abstractmethod
    def _a_entidad(self, fila: sqlite3.Row) -> T:
        """Construye el objeto de dominio a partir de una fila."""

    @abstractmethod
    def _a_registro(self, obj: T) -> tuple:
        """Valores de `columnas` para insertar o actualizar el objeto."""

    # --- CRUD ----------------------------------------------------------------
    def insertar(self, obj: T) -> int:
        marcadores = ", ".join("?" * len(self.columnas))
        sql = f"INSERT INTO {self.tabla} ({', '.join(self.columnas)}) VALUES ({marcadores})"
        obj.id = self.conexion.ejecutar(sql, self._a_registro(obj)).lastrowid
        return obj.id

    def actualizar(self, obj: T) -> None:
        asignaciones = ", ".join(f"{columna} = ?" for columna in self.columnas)
        sql = f"UPDATE {self.tabla} SET {asignaciones} WHERE {self.clave} = ?"
        self.conexion.ejecutar(sql, (*self._a_registro(obj), obj.id))

    def eliminar(self, id_: int) -> None:
        self.conexion.ejecutar(f"DELETE FROM {self.tabla} WHERE {self.clave} = ?", (id_,))

    def obtener_por_id(self, id_: int) -> T | None:
        fila = self.conexion.consultar_uno(f"SELECT * FROM {self.tabla} WHERE {self.clave} = ?", (id_,))
        return None if fila is None else self._a_entidad(fila)

    def listar(self) -> list[T]:
        orden = f" ORDER BY {self.orden}" if self.orden else ""
        return self._mapear(self.conexion.consultar(f"SELECT * FROM {self.tabla}{orden}"))

    # --- Auxiliares para las subclases ---------------------------------------
    def _mapear(self, filas: list[sqlite3.Row]) -> list[T]:
        return list(map(self._a_entidad, filas))

    def _listar_donde(self, condicion: str, parametros: tuple = (), orden: str | None = None) -> list[T]:
        orden = orden or self.orden
        sql = f"SELECT * FROM {self.tabla} WHERE {condicion}" + (f" ORDER BY {orden}" if orden else "")
        return self._mapear(self.conexion.consultar(sql, parametros))

    def _obtener_donde(self, condicion: str, parametros: tuple = ()) -> T | None:
        fila = self.conexion.consultar_uno(f"SELECT * FROM {self.tabla} WHERE {condicion}", parametros)
        return None if fila is None else self._a_entidad(fila)

    def _diccionarios(self, sql: str, parametros: tuple = ()) -> list[dict]:
        """Consultas para listados: filas con datos de varias tablas, como diccionarios."""
        return [dict(fila) for fila in self.conexion.consultar(sql, parametros)]

    def contar(self, condicion: str = "1 = 1", parametros: tuple = ()) -> int:
        return self.conexion.valor(f"SELECT COUNT(*) FROM {self.tabla} WHERE {condicion}", parametros)

    def siguiente_secuencia(self) -> int:
        return (self.conexion.valor(f"SELECT MAX({self.clave}) FROM {self.tabla}") or 0) + 1
