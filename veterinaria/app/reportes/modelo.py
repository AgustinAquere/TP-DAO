"""Estructura común de los reportes: la interfaz, el PDF y el CSV la recorren de la misma forma."""
from collections.abc import Callable
from dataclasses import dataclass, field

Formato = Callable[[object], str]


def texto(valor) -> str:
    return "" if valor is None else str(valor)


@dataclass
class Columna:
    titulo: str
    formato: Formato = texto
    numerica: bool = False


@dataclass
class Seccion:
    titulo: str
    columnas: list[Columna]
    filas: list[list] = field(default_factory=list)   # valores crudos (el CSV los exporta así)
    vacio: str = "No hay datos para el período seleccionado."

    def encabezados(self) -> list[str]:
        return [c.titulo for c in self.columnas]

    def filas_formateadas(self) -> list[list[str]]:
        return [[columna.formato(valor) for columna, valor in zip(self.columnas, fila)] for fila in self.filas]


@dataclass
class Grafico:
    tipo: str                                  # "barras" | "barras_apiladas" | "barras_h" | "torta"
    titulo: str
    etiquetas: list[str]
    series: dict[str, list[float]]
    eje_y: str = ""


@dataclass
class Reporte:
    clave: str
    titulo: str
    descripcion: str
    parametros: dict[str, str] = field(default_factory=dict)
    indicadores: list[tuple[str, str]] = field(default_factory=list)
    secciones: list[Seccion] = field(default_factory=list)
    grafico: Grafico | None = None


@dataclass
class DefinicionReporte:
    """Lo que la interfaz necesita para ofrecer un reporte y sus filtros."""
    clave: str
    titulo: str
    descripcion: str
    icono: str
    agrupaciones: dict[str, str] = field(default_factory=dict)   # clave -> etiqueta
