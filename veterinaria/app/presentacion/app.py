"""Ventana principal: barra de navegación lateral y área de contenido con la vista activa."""
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
from app.servicios.contenedor import Servicios

# (clave, etiqueta, ícono, ícono seleccionado, clase de la vista)
SECCIONES = [
    ("inicio", "Inicio", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD, InicioVista),
    ("clientes", "Clientes", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE, ClientesVista),
    ("mascotas", "Mascotas", ft.Icons.PETS_OUTLINED, ft.Icons.PETS, MascotasVista),
    ("turnos", "Agenda de turnos", ft.Icons.CALENDAR_MONTH_OUTLINED, ft.Icons.CALENDAR_MONTH, TurnosVista),
    ("atenciones", "Atenciones", ft.Icons.MEDICAL_SERVICES_OUTLINED, ft.Icons.MEDICAL_SERVICES, AtencionesVista),
    ("envios", "Empaquetado y envío", ft.Icons.LOCAL_SHIPPING_OUTLINED, ft.Icons.LOCAL_SHIPPING, EnviosVista),
    ("laboratorio", "Laboratorio", ft.Icons.BIOTECH_OUTLINED, ft.Icons.BIOTECH, LaboratorioVista),
    ("trazabilidad", "Trazabilidad", ft.Icons.TIMELINE_OUTLINED, ft.Icons.TIMELINE, TrazabilidadVista),
    ("facturacion", "Facturación", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG, FacturacionVista),
    ("reportes", "Reportes", ft.Icons.INSIGHTS_OUTLINED, ft.Icons.INSIGHTS, ReportesVista),
    ("catalogos", "Catálogos", ft.Icons.TUNE_OUTLINED, ft.Icons.TUNE, CatalogosVista),
]


class VeterinariaApp:
    def __init__(self, page: ft.Page, servicios: Servicios):
        self.page = page
        self.servicios = servicios
        self.notificador = Notificador(page)
        self._vistas = {}
        self._configurar_pagina()
        self.rail = ft.NavigationRail(
            selected_index=0, extended=True, min_extended_width=210, label_type=ft.NavigationRailLabelType.NONE,
            leading=ft.Container(ft.Row([ft.Icon(ft.Icons.PETS, color=COLOR_PRIMARIO, size=30),
                                         ft.Column([ft.Text("VetRed", size=20, weight=ft.FontWeight.BOLD),
                                                    ft.Text("Clínicas y laboratorio", size=11,
                                                            color=ft.Colors.ON_SURFACE_VARIANT)], spacing=0)]),
                                 padding=ft.Padding.only(left=8, top=12, bottom=12)),
            destinations=[ft.NavigationRailDestination(icon=icono, selected_icon=seleccionado, label=etiqueta)
                          for _, etiqueta, icono, seleccionado, _ in SECCIONES],
            on_change=lambda e: self.navegar(SECCIONES[e.control.selected_index][0]))
        self.contenido = ft.Container(expand=True, padding=ft.Padding.only(left=24, right=24, top=18, bottom=12))
        page.add(ft.Row([self.rail, ft.VerticalDivider(width=1), self.contenido], expand=True, spacing=0))
        self.navegar("inicio")

    def _configurar_pagina(self) -> None:
        self.page.title = config.APP_TITULO
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.TEAL)
        self.page.padding = 0
        self.page.window.width = 1440
        self.page.window.height = 900
        self.page.window.min_width = 1100
        self.page.window.min_height = 700

    def navegar(self, clave: str, **contexto) -> None:
        """Muestra la vista indicada; `contexto` permite abrirla con datos preseleccionados."""
        indice, clase = next((i, s[4]) for i, s in enumerate(SECCIONES) if s[0] == clave)
        if clave not in self._vistas:
            self._vistas[clave] = clase(self)
        vista = self._vistas[clave]
        self.rail.selected_index = indice
        self.contenido.content = vista.control
        vista.seguro(vista.al_mostrar)(**contexto)
        self.page.update()
