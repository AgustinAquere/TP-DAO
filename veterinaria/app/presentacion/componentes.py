"""Controles y funciones reutilizables por todas las vistas: tablas, formularios, diálogos y avisos."""
import logging
import os
from collections.abc import Callable
from datetime import date, datetime
from functools import wraps
from pathlib import Path

import flet as ft

from app.dominio.excepciones import ErrorNegocio, ValidacionError
from app.utils import fechas, formato

logger = logging.getLogger(__name__)

COLOR_PRIMARIO = ft.Colors.TEAL_700

COLORES_ESTADO = {
    "EXTRAIDA": ft.Colors.BLUE_GREY_600, "EMPAQUETADA": ft.Colors.INDIGO_600, "EN_TRANSITO": ft.Colors.AMBER_800,
    "RECIBIDA": ft.Colors.TEAL_700, "ANALIZADA": ft.Colors.GREEN_700, "RECHAZADA": ft.Colors.RED_700,
    "EN_PREPARACION": ft.Colors.BLUE_GREY_600, "PRECINTADO": ft.Colors.INDIGO_600, "RECIBIDO": ft.Colors.GREEN_700,
    "RECHAZADO": ft.Colors.RED_700, "RESERVADO": ft.Colors.BLUE_700, "ATENDIDO": ft.Colors.GREEN_700,
    "CANCELADO": ft.Colors.GREY_600, "AUSENTE": ft.Colors.ORANGE_800, "EMITIDA": ft.Colors.BLUE_700,
    "EN_PROCESO": ft.Colors.AMBER_800, "COMPLETA": ft.Colors.GREEN_700, "URGENTE": ft.Colors.RED_700,
    "NORMAL": ft.Colors.BLUE_GREY_600, "CONSULTA": ft.Colors.BLUE_700, "CONTROL": ft.Colors.TEAL_700,
    "URGENCIA": ft.Colors.RED_700, "INTACTO": ft.Colors.GREEN_700, "ROTO": ft.Colors.RED_700,
    "ACTIVO": ft.Colors.GREEN_700, "BAJA": ft.Colors.GREY_600,
}


# --- Avisos y diálogos ----------------------------------------------------------------
class Notificador:
    def __init__(self, page: ft.Page):
        self.page = page

    def _mostrar(self, mensaje: str, color, icono) -> None:
        self.page.show_dialog(ft.SnackBar(
            content=ft.Row([ft.Icon(icono, color=ft.Colors.WHITE), ft.Text(mensaje, color=ft.Colors.WHITE, expand=True)]),
            bgcolor=color, show_close_icon=True, close_icon_color=ft.Colors.WHITE))

    def exito(self, mensaje: str) -> None:
        self._mostrar(mensaje, ft.Colors.GREEN_700, ft.Icons.CHECK_CIRCLE)

    def error(self, mensaje: str) -> None:
        self._mostrar(mensaje, ft.Colors.RED_700, ft.Icons.ERROR_OUTLINE)

    def info(self, mensaje: str) -> None:
        self._mostrar(mensaje, ft.Colors.BLUE_GREY_700, ft.Icons.INFO_OUTLINE)


def manejar_errores(notificador: Notificador, funcion: Callable) -> Callable:
    """Envuelve un manejador de eventos: los errores de negocio se muestran al usuario en lugar de cortar la app.

    Al terminar actualiza la página completa: Flet omite su actualización automática cuando el
    manejador ya actualizó algún control (por ejemplo, al mostrar un aviso).
    """
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except ErrorNegocio as error:
            notificador.error(str(error))
        except Exception as error:  # noqa: BLE001 - la interfaz nunca debe quedar colgada por un error
            logger.exception("Error no controlado en la interfaz")
            notificador.error(f"Ocurrió un error inesperado: {error}")
        finally:
            notificador.page.update()
    return envoltura


def abrir_dialogo(page: ft.Page, titulo: str, contenido: ft.Control, acciones: list[ft.Control],
                  ancho: int = 560, alto: int | None = None) -> ft.AlertDialog:
    if isinstance(contenido, ft.Column):  # los campos del formulario ocupan todo el ancho del diálogo
        contenido.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    dialogo = ft.AlertDialog(modal=True, title=ft.Text(titulo, weight=ft.FontWeight.BOLD),
                             content=ft.Container(contenido, width=ancho, height=alto), actions=acciones,
                             actions_alignment=ft.MainAxisAlignment.END)
    page.show_dialog(dialogo)
    return dialogo


def boton_cancelar(page: ft.Page, texto: str = "Cancelar") -> ft.TextButton:
    return ft.TextButton(texto, on_click=lambda e: page.pop_dialog())


def confirmar(page: ft.Page, titulo: str, mensaje: str, al_confirmar: Callable[[], None],
              texto_boton: str = "Confirmar", peligroso: bool = False) -> None:
    def aceptar(e):
        page.pop_dialog()
        al_confirmar()

    estilo = ft.ButtonStyle(bgcolor=ft.Colors.RED_700) if peligroso else None
    abrir_dialogo(page, titulo, ft.Text(mensaje), [boton_cancelar(page),
                                                   ft.FilledButton(texto_boton, on_click=aceptar, style=estilo)],
                  ancho=460)


def abrir_archivo(ruta: Path) -> None:
    """Abre el archivo generado con la aplicación predeterminada del sistema."""
    if hasattr(os, "startfile"):
        os.startfile(ruta)  # noqa: S606 - archivo generado por la propia aplicación


# --- Campos de formulario ---------------------------------------------------------------
def campo(etiqueta: str, valor=None, **opciones) -> ft.TextField:
    return ft.TextField(label=etiqueta, value="" if valor is None else str(valor), dense=True, **opciones)


def numero_editable(valor: float | None) -> str:
    """12.50 -> '12,5'; 14500.0 -> '14500' (sin separador de miles para poder editarlo)."""
    if valor is None:
        return ""
    return f"{valor:.4f}".rstrip("0").rstrip(".").replace(".", ",")


def campo_numero(etiqueta: str, valor=None, **opciones) -> ft.TextField:
    return campo(etiqueta, numero_editable(valor), keyboard_type=ft.KeyboardType.NUMBER, **opciones)


def campo_fecha(etiqueta: str, valor: date | None = None, **opciones) -> ft.TextField:
    return campo(etiqueta, fechas.formatear_fecha(valor), hint_text="dd/mm/aaaa", **opciones)


def campo_fecha_hora(etiqueta: str, valor: datetime | None = None, **opciones) -> ft.TextField:
    return campo(etiqueta, fechas.formatear_fecha_hora(valor), hint_text="dd/mm/aaaa hh:mm", **opciones)


def selector(etiqueta: str, opciones: list[tuple], valor=None, filtrable: bool = False, **extra) -> ft.Dropdown:
    """Dropdown a partir de pares (clave, texto). Las claves se guardan como texto.

    Sin ancho fijo, ocupa todo el ancho disponible (como los campos de texto de los formularios).
    """
    if "width" not in extra:
        extra.setdefault("expanded_insets", ft.Padding.all(0))
    return ft.Dropdown(label=etiqueta, dense=True, value=None if valor is None else str(valor),
                       options=[ft.DropdownOption(key=str(clave), text=texto) for clave, texto in opciones],
                       enable_filter=filtrable, editable=filtrable, **extra)


def cargar_opciones(dropdown: ft.Dropdown, opciones: list[tuple], conservar: bool = True) -> None:
    anterior = dropdown.value
    dropdown.options = [ft.DropdownOption(key=str(clave), text=texto) for clave, texto in opciones]
    claves = {str(clave) for clave, _ in opciones}
    dropdown.value = anterior if conservar and anterior in claves else None


def _texto(control) -> str:
    return (control.value or "").strip()


def leer_texto(control: ft.TextField, requerido: bool = False) -> str | None:
    texto = _texto(control)
    if requerido and not texto:
        raise ValidacionError(f"El campo «{control.label}» es obligatorio.")
    return texto or None


def leer_decimal(control: ft.TextField, requerido: bool = False) -> float | None:
    texto = leer_texto(control, requerido)
    if texto is None:
        return None
    try:
        return float(texto.replace(".", "").replace(",", ".") if "," in texto else texto)
    except ValueError:
        raise ValidacionError(f"«{control.label}» debe ser un número.") from None


def leer_entero(control: ft.TextField, requerido: bool = False) -> int | None:
    valor = leer_decimal(control, requerido)
    if valor is not None and valor != int(valor):
        raise ValidacionError(f"«{control.label}» debe ser un número entero.")
    return None if valor is None else int(valor)


def leer_fecha(control: ft.TextField, requerido: bool = False) -> date | None:
    texto = leer_texto(control, requerido)
    try:
        return fechas.parsear_fecha(texto)
    except ValueError:
        raise ValidacionError(f"«{control.label}» debe tener el formato dd/mm/aaaa.") from None


def leer_fecha_hora(control: ft.TextField, requerido: bool = False) -> datetime | None:
    texto = leer_texto(control, requerido)
    try:
        return fechas.parsear_fecha_hora(texto)
    except ValueError:
        raise ValidacionError(f"«{control.label}» debe tener el formato dd/mm/aaaa hh:mm.") from None


def leer_id(control: ft.Dropdown, requerido: bool = False) -> int | None:
    if not control.value:
        if requerido:
            raise ValidacionError(f"Seleccione «{control.label}».")
        return None
    return int(control.value)


def fila(*controles: ft.Control, espacio: int = 12) -> ft.Row:
    """Fila de formulario: los controles se reparten el ancho disponible."""
    for control in controles:
        control.expand = True
    return ft.Row(list(controles), spacing=espacio, vertical_alignment=ft.CrossAxisAlignment.START)


# --- Presentación de datos -----------------------------------------------------------------
def chip(texto: str, color=None) -> ft.Container:
    color = color or COLORES_ESTADO.get(texto, ft.Colors.BLUE_GREY_600)
    return ft.Container(ft.Text(formato.etiqueta(texto) if texto.isupper() else texto, size=12, color=color,
                                weight=ft.FontWeight.W_600),
                        bgcolor=ft.Colors.with_opacity(0.12, color), border_radius=12,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=3))


def encabezado(titulo: str, subtitulo: str = "", acciones: list[ft.Control] | None = None) -> ft.Row:
    textos = [ft.Text(titulo, size=24, weight=ft.FontWeight.BOLD)]
    if subtitulo:
        textos.append(ft.Text(subtitulo, size=13, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Row([ft.Column(textos, spacing=2, expand=True), *(acciones or [])],
                  vertical_alignment=ft.CrossAxisAlignment.CENTER)


def seccion(texto: str, icono, *controles: ft.Control) -> ft.Container:
    return ft.Container(
        ft.Column([ft.Row([ft.Icon(icono, color=COLOR_PRIMARIO, size=20),
                           ft.Text(texto, size=16, weight=ft.FontWeight.BOLD)]), *controles], spacing=10, tight=True),
        padding=16, border_radius=12, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT))


def tarjeta_indicador(titulo: str, valor: str, icono, color=COLOR_PRIMARIO,
                      al_hacer_clic: Callable | None = None) -> ft.Container:
    return ft.Container(
        ft.Row([ft.Container(ft.Icon(icono, color=color, size=26), bgcolor=ft.Colors.with_opacity(0.12, color),
                             border_radius=10, padding=10),
                ft.Column([ft.Text(valor, size=22, weight=ft.FontWeight.BOLD),
                           ft.Text(titulo, size=12, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=0, expand=True)],
               spacing=12),
        padding=14, border_radius=12, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        bgcolor=ft.Colors.SURFACE, on_click=al_hacer_clic, ink=al_hacer_clic is not None)


def boton_icono(icono, ayuda: str, al_hacer_clic: Callable, color=None) -> ft.IconButton:
    return ft.IconButton(icon=icono, tooltip=ayuda, on_click=al_hacer_clic, icon_color=color or COLOR_PRIMARIO,
                         icon_size=20)


class Tabla:
    """DataTable con desplazamiento, mensaje de vacío y columna opcional de acciones por fila."""

    def __init__(self, columnas: list[str | tuple[str, bool]], acciones: Callable[[object], list[ft.Control]] | None = None,
                 vacio: str = "No hay registros para mostrar.", seleccionable: bool = False,
                 al_seleccionar: Callable[[object, bool], None] | None = None, expandir: bool = True):
        definiciones = [(c, False) if isinstance(c, str) else c for c in columnas]
        if acciones:
            definiciones.append(("Acciones", False))
        self._acciones = acciones
        self._al_seleccionar = al_seleccionar
        self.tabla = ft.DataTable(
            columns=[ft.DataColumn(label=ft.Text(titulo, weight=ft.FontWeight.BOLD), numeric=numerica)
                     for titulo, numerica in definiciones],
            rows=[], heading_row_color=ft.Colors.with_opacity(0.06, COLOR_PRIMARIO), column_spacing=18,
            data_row_min_height=40, data_row_max_height=60, show_checkbox_column=seleccionable,
            horizontal_lines=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))
        self.mensaje_vacio = ft.Text(vacio, color=ft.Colors.ON_SURFACE_VARIANT, italic=True, visible=False)
        self.control = ft.Column([ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO), self.mensaje_vacio],
                                 scroll=ft.ScrollMode.AUTO, expand=expandir)
        self.datos: list = []

    @staticmethod
    def _celda(valor) -> ft.DataCell:
        if isinstance(valor, ft.Control):
            return ft.DataCell(valor)
        texto = "" if valor is None else str(valor)
        if len(texto) <= 34:
            return ft.DataCell(ft.Text(texto, size=13))
        # Los textos largos se acotan a dos líneas para que la tabla no desborde; el texto completo va en el tooltip
        return ft.DataCell(ft.Container(ft.Text(texto, size=13, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                        width=230, tooltip=texto))

    def cargar(self, filas: list[list], datos: list | None = None) -> None:
        self.datos = list(datos) if datos is not None else list(filas)
        self.tabla.rows = []
        for fila, dato in zip(filas, self.datos):
            celdas = [self._celda(v) for v in fila]
            if self._acciones:
                celdas.append(ft.DataCell(ft.Row(self._acciones(dato), spacing=0, tight=True)))
            self.tabla.rows.append(ft.DataRow(
                cells=celdas, data=dato,
                on_select_change=(lambda e, d=dato: self._cambio_seleccion(e, d)) if self._al_seleccionar else None))
        self.mensaje_vacio.visible = not filas

    def _cambio_seleccion(self, evento, dato) -> None:
        fila = evento.control
        fila.selected = not fila.selected
        self._al_seleccionar(dato, fila.selected)

    def seleccionados(self) -> list:
        return [fila.data for fila in self.tabla.rows if fila.selected]
