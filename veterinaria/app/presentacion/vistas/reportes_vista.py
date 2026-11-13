"""Reportes: se eligen del catálogo, se filtran por período y se exportan a PDF o CSV."""
from datetime import date, timedelta

import flet as ft

from app.presentacion.componentes import (COLOR_PRIMARIO, Tabla, abrir_archivo, campo_fecha, encabezado, leer_fecha,
                                          seccion, selector, tarjeta_indicador)
from app.presentacion.vistas.base_vista import Vista
from app.reportes.exportador import exportar_csv, exportar_pdf
from app.reportes.graficos import generar_png
from app.reportes.modelo import Reporte
from app.utils import fechas

# (clave, texto, rango a partir de hoy). El primero que coincide queda marcado en la barra.
PERIODOS = (
    ("30", "Últimos 30 días", lambda hoy: (hoy - timedelta(days=30), hoy)),
    ("90", "Últimos 90 días", lambda hoy: (hoy - timedelta(days=90), hoy)),
    ("mes", "Este mes", lambda hoy: (hoy.replace(day=1), hoy)),
    ("anio", "Este año", lambda hoy: (date(hoy.year, 1, 1), hoy)),
)


def _icono(nombre: str):
    return getattr(ft.Icons, nombre.upper(), ft.Icons.INSIGHTS)


def _clave_periodo(desde: date, hasta: date, hoy: date | None = None) -> str | None:
    hoy = hoy or date.today()
    for clave, _, rango in PERIODOS:
        if (desde, hasta) == rango(hoy):
            return clave
    return None


class ReportesVista(Vista):
    def construir(self) -> ft.Control:
        self._definiciones = self.servicios.reportes.catalogo()
        self._clave = self._definiciones[0].clave
        self._reporte: Reporte | None = None
        self._periodo: str | None = "90"
        self._suspender = False
        generar = self.seguro(lambda e: self._generar())
        self.reporte = selector("Reporte", [(d.clave, d.titulo) for d in self._definiciones], self._clave,
                                width=280, menu_width=480, menu_height=320,
                                on_select=self.seguro(self._cambiar_reporte))
        self.buscar = ft.TextField(hint_text="Buscar", dense=True, prefix_icon=ft.Icons.SEARCH, width=280,
                                   tooltip="Filtra el selector por nombre o descripción",
                                   on_change=self.seguro(self._filtrar_reportes),
                                   on_submit=self.seguro(self._elegir_busqueda))
        self.desde = campo_fecha("Desde", date.today() - timedelta(days=90), width=156,
                                 al_cambiar=generar, on_submit=generar)
        self.hasta = campo_fecha("Hasta", date.today(), width=156, al_cambiar=generar, on_submit=generar)
        self.agrupar = selector("Agrupar por", [], width=168, on_select=self.seguro(self._cambiar_agrupacion))
        self.atajos = ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.banner = ft.Container(border_radius=12, padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                                   bgcolor=ft.Colors.with_opacity(0.12, COLOR_PRIMARIO))
        self.resultado = ft.Column(spacing=14)
        botones = ft.Row([
            ft.FilledButton("Generar", icon=ft.Icons.PLAY_ARROW, on_click=generar),
            ft.OutlinedButton("PDF", icon=ft.Icons.PICTURE_AS_PDF,
                              on_click=self.seguro(lambda e: self._exportar(exportar_pdf))),
            ft.OutlinedButton("CSV", icon=ft.Icons.DOWNLOAD,
                              on_click=self.seguro(lambda e: self._exportar(exportar_csv))),
        ], spacing=8)
        barra = ft.Container(
            ft.Column([
                ft.Row([
                    ft.Column([self.reporte, self.buscar], spacing=4, width=280, tight=True),
                    self.desde, self.hasta, self.agrupar, botones,
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.atajos,
            ], spacing=10),
            padding=ft.Padding.symmetric(horizontal=14, vertical=12), border_radius=12,
            bgcolor=ft.Colors.SURFACE, border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT))
        self._sincronizar_filtros()
        self._pintar_atajos()
        return ft.Column([
            encabezado("Reportes", "Indicadores de atención, laboratorio, transporte y facturación"),
            barra,
            ft.Column([self.banner, self.resultado], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True),
        ], expand=True, spacing=12)

    def al_mostrar(self, **contexto) -> None:
        self._suspender = True
        try:
            self._sincronizar_filtros()
            self._generar()
        finally:
            self._suspender = False

    def _definicion(self):
        return next(d for d in self._definiciones if d.clave == self._clave)

    def _sincronizar_filtros(self) -> None:
        definicion = self._definicion()
        self.reporte.value = definicion.clave
        self.reporte.leading_icon = _icono(definicion.icono)
        self._filtrar_reportes()
        self.agrupar.options = [ft.DropdownOption(key=k, text=t) for k, t in definicion.agrupaciones.items()]
        self.agrupar.visible = bool(definicion.agrupaciones)
        if definicion.agrupaciones and self.agrupar.value not in definicion.agrupaciones:
            self.agrupar.value = next(iter(definicion.agrupaciones))

    def _cambiar_reporte(self, e) -> None:
        if self.reporte.value not in {d.clave for d in self._definiciones} or self.reporte.value == self._clave:
            return
        self._clave = self.reporte.value
        self.buscar.value = ""
        self._suspender = True
        try:
            self._sincronizar_filtros()
            self._generar()
        finally:
            self._suspender = False

    def _opcion(self, definicion) -> ft.DropdownOption:
        return ft.DropdownOption(key=definicion.clave, text=definicion.titulo, leading_icon=_icono(definicion.icono))

    def _filtrar_reportes(self, e=None) -> None:
        texto = (self.buscar.value or "").strip().lower()
        visibles = [d for d in self._definiciones
                    if not texto or texto in d.titulo.lower() or texto in d.descripcion.lower()]
        if not any(d.clave == self._clave for d in visibles):
            visibles.insert(0, self._definicion())
        self.reporte.options = [self._opcion(d) for d in visibles]

    def _elegir_busqueda(self, e) -> None:
        """Enter con una sola coincidencia abre ese reporte."""
        texto = (self.buscar.value or "").strip().lower()
        coincidencias = [d for d in self._definiciones
                         if texto and (texto in d.titulo.lower() or texto in d.descripcion.lower())]
        if len(coincidencias) != 1:
            return
        self.reporte.value = coincidencias[0].clave
        self._cambiar_reporte(e)

    def _cambiar_agrupacion(self, e) -> None:
        if not self._suspender and self.agrupar.visible:
            self._generar()

    def _chip_periodo(self, clave: str, texto: str) -> ft.Control:
        activo = clave == self._periodo
        return ft.Container(
            ft.Text(texto, size=12, weight=ft.FontWeight.W_600,
                    color=ft.Colors.WHITE if activo else COLOR_PRIMARIO),
            bgcolor=COLOR_PRIMARIO if activo else ft.Colors.with_opacity(0.10, COLOR_PRIMARIO),
            border_radius=16, padding=ft.Padding.symmetric(horizontal=12, vertical=5), ink=True,
            on_click=self.seguro(lambda e, c=clave: self._aplicar_periodo(c)))

    def _pintar_atajos(self) -> None:
        self.atajos.controls = [ft.Text("Período", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                *[self._chip_periodo(clave, texto) for clave, texto, _ in PERIODOS]]

    def _aplicar_periodo(self, clave: str) -> None:
        desde, hasta = next(rango for c, _, rango in PERIODOS if c == clave)(date.today())
        self.desde.value = fechas.formatear_fecha(desde)
        self.hasta.value = fechas.formatear_fecha(hasta)
        self._generar()

    def _mostrar_banner(self, reporte: Reporte) -> None:
        self.banner.content = ft.Row([
            ft.Container(ft.Icon(_icono(self._definicion().icono), color=COLOR_PRIMARIO, size=26),
                         bgcolor=ft.Colors.with_opacity(0.16, COLOR_PRIMARIO), border_radius=24, padding=10),
            ft.Column([
                ft.Text(reporte.titulo, size=20, weight=ft.FontWeight.BOLD),
                ft.Text(reporte.descripcion, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(" · ".join(f"{k}: {v}" for k, v in reporte.parametros.items()),
                        size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=2, expand=True),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _generar(self) -> None:
        desde, hasta = leer_fecha(self.desde, True), leer_fecha(self.hasta, True)
        self._periodo = _clave_periodo(desde, hasta)
        self._pintar_atajos()
        reporte = self.servicios.reportes.generar(self._clave, desde, hasta,
                                                  self.agrupar.value if self.agrupar.visible else None)
        self._reporte = reporte
        self._mostrar_banner(reporte)
        controles = []
        if reporte.indicadores:
            ancho = 12 / len(reporte.indicadores)  # todas las tarjetas en una fila en pantallas anchas
            controles.append(ft.ResponsiveRow([ft.Container(tarjeta_indicador(nombre, valor, ft.Icons.ANALYTICS),
                                                            col={"md": 6, "xl": ancho})
                                               for nombre, valor in reporte.indicadores],
                                              spacing=10, run_spacing=10))
        if reporte.grafico and reporte.grafico.etiquetas:
            controles.append(ft.Container(ft.Image(src=generar_png(reporte.grafico, 9, 3.6), fit=ft.BoxFit.CONTAIN,
                                                   height=340), alignment=ft.Alignment.CENTER))
        for seccion_reporte in reporte.secciones:
            tabla = Tabla([(c.titulo, c.numerica) for c in seccion_reporte.columnas], vacio=seccion_reporte.vacio,
                          expandir=False)
            tabla.cargar(seccion_reporte.filas_formateadas())
            controles.append(seccion(seccion_reporte.titulo, ft.Icons.TABLE_CHART, tabla.control))
        self.resultado.controls = controles

    def _exportar(self, exportador) -> None:
        if self._reporte is None:
            self._generar()
        ruta = exportador(self._reporte)
        self.notificar.exito(f"Archivo generado: {ruta}")
        abrir_archivo(ruta)
