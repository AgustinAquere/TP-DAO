"""Ventana principal: menú lateral por categorías y área de contenido con la vista activa."""
from dataclasses import dataclass, field

import flet as ft

from app import config
from app.presentacion.componentes import COLOR_PRIMARIO, Notificador
from app.presentacion.vistas.atenciones_vista import AtencionesVista
from app.presentacion.vistas.catalogos_vista import CatalogosVista
from app.presentacion.vistas.clientes_vista import ClientesVista
from app.presentacion.vistas.envios_vista import EnviosVista
from app.presentacion.vistas.facturacion_vista import FacturacionVista
from app.presentacion.vistas.inicio_vista import InicioVista
from app.presentacion.vistas.laboratorio_vista import LaboratorioVista
from app.presentacion.vistas.mascotas_vista import MascotasVista
from app.presentacion.vistas.reportes_vista import ReportesVista
from app.presentacion.vistas.trazabilidad_vista import TrazabilidadVista
from app.presentacion.vistas.turnos_vista import TurnosVista

ANCHO_ABIERTO = 280
ANCHO_CERRADO = 72

VISTAS = {
    "inicio": InicioVista,
    "clientes": ClientesVista,
    "mascotas": MascotasVista,
    "turnos": TurnosVista,
    "atenciones": AtencionesVista,
    "envios": EnviosVista,
    "laboratorio": LaboratorioVista,
    "trazabilidad": TrazabilidadVista,
    "facturacion": FacturacionVista,
    "reportes": ReportesVista,
    "catalogos": CatalogosVista,
}


@dataclass(frozen=True)
class Entrada:
    id: str
    etiqueta: str
    clave: str
    contexto: dict = field(default_factory=dict, hash=False, compare=False)


@dataclass(frozen=True)
class Grupo:
    id: str
    etiqueta: str
    icono: str
    entradas: tuple[Entrada, ...]


INICIO = Entrada("inicio", "Inicio", "inicio")

GRUPOS = (
    Grupo("pacientes", "Pacientes y Agenda", ft.Icons.CALENDAR_MONTH_OUTLINED, (
        Entrada("clientes", "Clientes", "clientes"),
        Entrada("mascotas", "Mascotas e HC", "mascotas"),
        Entrada("turnos", "Agenda de turnos", "turnos"),
    )),
    Grupo("clinica", "Clínica Médica", ft.Icons.MEDICAL_SERVICES_OUTLINED, (
        Entrada("atenciones_nueva", "Registrar nueva atención", "atenciones", {"pestania": 0}),
        Entrada("atenciones_historial", "Historial de atenciones", "atenciones", {"pestania": 1}),
    )),
    Grupo("logistica", "Logística de Muestras", ft.Icons.LOCAL_SHIPPING_OUTLINED, (
        Entrada("envios_armar", "Armar remito biológico", "envios", {"pestania": 0}),
        Entrada("envios_remitos", "Remitos y cadena de envío", "envios", {"pestania": 1}),
        Entrada("trazabilidad", "Trazabilidad de muestras", "trazabilidad"),
    )),
    Grupo("laboratorio", "Laboratorio Central", ft.Icons.BIOTECH_OUTLINED, (
        Entrada("lab_recepcion", "Recepción de remitos", "laboratorio", {"pestania": 0}),
        Entrada("lab_pendientes", "Análisis pendientes", "laboratorio", {"pestania": 1}),
        Entrada("lab_resultados", "Resultados emitidos", "laboratorio", {"pestania": 2}),
    )),
    Grupo("gestion", "Facturación y Reportes", ft.Icons.RECEIPT_LONG_OUTLINED, (
        Entrada("fact_emitir", "Emitir comprobante", "facturacion", {"pestania": 0}),
        Entrada("fact_emitidos", "Comprobantes emitidos", "facturacion", {"pestania": 1}),
        Entrada("reportes", "Reportes estadísticos", "reportes"),
    )),
    Grupo("catalogos", "Catálogos", ft.Icons.TUNE_OUTLINED, (
        Entrada("cat_red", "Red y Profesionales", "catalogos", {"grupo": "red"}),
        Entrada("cat_logistica", "Logística", "catalogos", {"grupo": "logistica"}),
        Entrada("cat_practicas", "Prácticas y Vacunación", "catalogos", {"grupo": "practicas"}),
    )),
)

_POR_ID = {entrada.id: (grupo, entrada) for grupo in GRUPOS for entrada in grupo.entradas}
_POR_ID[INICIO.id] = (None, INICIO)


def _id_destino(clave: str, pestania: int | None, grupo: str | None) -> str:
    """Qué ítem del menú corresponde a la vista que se está mostrando."""
    if clave == "atenciones":
        return "atenciones_historial" if pestania == 1 else "atenciones_nueva"
    if clave == "envios":
        return "envios_remitos" if pestania == 1 else "envios_armar"
    if clave == "laboratorio":
        return {1: "lab_pendientes", 2: "lab_resultados"}.get(pestania, "lab_recepcion")
    if clave == "facturacion":
        return "fact_emitidos" if pestania == 1 else "fact_emitir"
    if clave == "catalogos":
        return {"logistica": "cat_logistica", "practicas": "cat_practicas"}.get(grupo, "cat_red")
    return clave


class VeterinariaApp:
    def __init__(self, page: ft.Page, servicios):
        self.page = page
        self.servicios = servicios
        self.notificador = Notificador(page)
        self._vistas = {}
        self._abierto = True
        self._abierta: str | None = None
        self._activo = INICIO.id
        self._suspender = False
        self._configurar_pagina()
        self._encabezado = ft.Container()
        self._lista = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, expand=True,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.panel = ft.Container(
            ft.Column([self._encabezado, self._lista], spacing=4, expand=True,
                      horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            width=ANCHO_ABIERTO, bgcolor=ft.Colors.with_opacity(0.045, ft.Colors.TEAL),
            animate_size=200)
        self.contenido = ft.Container(expand=True, padding=ft.Padding.only(left=24, right=24, top=18, bottom=12))
        page.add(ft.Row([self.panel, ft.VerticalDivider(width=1), self.contenido], expand=True, spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH))
        self.navegar("inicio")

    def _configurar_pagina(self) -> None:
        self.page.title = config.APP_TITULO
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)
        self.page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("es", "AR"), ft.Locale("en", "US")],
            current_locale=ft.Locale("es", "AR"))
        self.page.padding = 0
        self.page.window.width = 1440
        self.page.window.height = 900
        self.page.window.min_width = 1100
        self.page.window.min_height = 700

    def navegar(self, clave: str, **contexto) -> None:
        """Muestra la vista indicada; `contexto` permite abrirla en una pestaña o con datos preseleccionados."""
        if clave not in self._vistas:
            self._vistas[clave] = VISTAS[clave](self)
        vista = self._vistas[clave]
        self._suspender = True
        try:
            self.contenido.content = vista.control
            vista.seguro(vista.al_mostrar)(**contexto)
            self._marcar(clave, **contexto)
        finally:
            self._suspender = False
        self.page.update()

    def sincronizar(self, clave: str, **contexto) -> None:
        """Actualiza el ítem activo cuando el usuario cambia de pestaña dentro de la vista."""
        if self._suspender:
            return
        self._marcar(clave, **contexto)
        self.page.update()

    def _marcar(self, clave: str, **contexto) -> None:
        self._activo = _id_destino(clave, contexto.get("pestania"), contexto.get("grupo"))
        grupo, _ = _POR_ID.get(self._activo, (None, None))
        self._abierta = grupo.id if grupo else None
        self._pintar_menu()

    def _alternar_menu(self, e) -> None:
        self._abierto = not self._abierto
        self.panel.width = ANCHO_ABIERTO if self._abierto else ANCHO_CERRADO
        self._pintar_menu()
        self.page.update()

    def _alternar_grupo(self, id_grupo: str) -> None:
        self._abierta = None if self._abierta == id_grupo else id_grupo
        self._pintar_menu()
        self.page.update()

    def _ir(self, entrada: Entrada):
        return lambda e: self.navegar(entrada.clave, **entrada.contexto)

    def _pintar_menu(self) -> None:
        self._encabezado.content = self._fila_encabezado()
        self._lista.controls = self._filas_abiertas() if self._abierto else self._filas_cerradas()

    def _fila_encabezado(self) -> ft.Control:
        boton = ft.IconButton(ft.Icons.MENU, tooltip="Contraer menú" if self._abierto else "Expandir menú",
                              on_click=self._alternar_menu)
        if not self._abierto:
            return ft.Container(boton, padding=ft.Padding.only(top=6), alignment=ft.Alignment.CENTER)
        return ft.Container(ft.Row([
            boton,
            ft.Icon(ft.Icons.PETS, color=COLOR_PRIMARIO, size=28),
            ft.Column([ft.Text("VetRed", size=18, weight=ft.FontWeight.BOLD),
                       ft.Text("Clínicas y laboratorio", size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
                      spacing=0, expand=True),
        ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=4, right=8, top=8, bottom=6))

    def _filas_abiertas(self) -> list[ft.Control]:
        filas = [self._fila_inicio()]
        for grupo in GRUPOS:
            abierta = self._abierta == grupo.id
            filas.append(self._fila_grupo(grupo, abierta))
            if abierta:
                filas.extend(self._fila_entrada(entrada) for entrada in grupo.entradas)
        return filas

    def _filas_cerradas(self) -> list[ft.Control]:
        filas = [self._icono(ft.Icons.DASHBOARD_OUTLINED, "Inicio", self._activo == INICIO.id, self._ir(INICIO))]
        for grupo in GRUPOS:
            activo = any(entrada.id == self._activo for entrada in grupo.entradas)
            filas.append(self._icono(grupo.icono, grupo.etiqueta, activo, menu=[
                ft.PopupMenuItem(content=entrada.etiqueta, checked=entrada.id == self._activo,
                                 on_click=self._ir(entrada)) for entrada in grupo.entradas]))
        return filas

    def _fila_inicio(self) -> ft.Control:
        return self._pastilla(
            ft.Row([ft.Icon(ft.Icons.DASHBOARD_OUTLINED, size=20,
                            color=COLOR_PRIMARIO if self._activo == INICIO.id else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(INICIO.etiqueta, size=13.5, expand=True, weight=ft.FontWeight.W_600,
                            color=COLOR_PRIMARIO if self._activo == INICIO.id else None)], spacing=10),
            self._activo == INICIO.id, self._ir(INICIO), horizontal=8)

    def _fila_grupo(self, grupo: Grupo, abierta: bool) -> ft.Control:
        contiene = any(entrada.id == self._activo for entrada in grupo.entradas)
        return ft.Container(
            ft.Row([ft.Icon(grupo.icono, size=20, color=COLOR_PRIMARIO if contiene else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(grupo.etiqueta, size=13, expand=True, weight=ft.FontWeight.W_600,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Icon(ft.Icons.EXPAND_MORE if abierta else ft.Icons.CHEVRON_RIGHT, size=18,
                            color=ft.Colors.ON_SURFACE_VARIANT)], spacing=8),
            bgcolor=ft.Colors.with_opacity(0.10, COLOR_PRIMARIO) if abierta or contiene else None,
            border_radius=24, ink=True, on_click=lambda e, g=grupo.id: self._alternar_grupo(g),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            margin=ft.Margin.symmetric(horizontal=8, vertical=1))

    def _fila_entrada(self, entrada: Entrada) -> ft.Control:
        activa = entrada.id == self._activo
        return self._pastilla(
            ft.Text(entrada.etiqueta, size=13, weight=ft.FontWeight.W_600 if activa else None,
                    color=COLOR_PRIMARIO if activa else None),
            activa, self._ir(entrada), izquierda=36)

    def _pastilla(self, contenido: ft.Control, activa: bool, al_hacer_clic, horizontal: int = 10,
                  izquierda: int | None = None) -> ft.Control:
        return ft.Container(
            contenido, bgcolor=ft.Colors.with_opacity(0.18, COLOR_PRIMARIO) if activa else None,
            border_radius=20, ink=True, on_click=al_hacer_clic,
            padding=ft.Padding.only(left=izquierda if izquierda is not None else 12, right=12, top=7, bottom=7),
            margin=ft.Margin.only(left=horizontal if izquierda is None else 8, right=10, top=1, bottom=1))

    def _icono(self, icono, ayuda: str, activo: bool, al_hacer_clic=None, menu=None) -> ft.Control:
        color = COLOR_PRIMARIO if activo else ft.Colors.ON_SURFACE_VARIANT
        if menu is not None:
            control = ft.PopupMenuButton(icon=icono, tooltip=ayuda, icon_color=color, items=menu,
                                         menu_position=ft.PopupMenuPosition.UNDER)
        else:
            control = ft.IconButton(icon=icono, tooltip=ayuda, icon_color=color, on_click=al_hacer_clic)
        return ft.Container(control, bgcolor=ft.Colors.with_opacity(0.16, COLOR_PRIMARIO) if activo else None,
                            border_radius=16, alignment=ft.Alignment.CENTER)
