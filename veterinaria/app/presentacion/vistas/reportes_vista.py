"""Reportes: se eligen del catálogo del servicio, se muestran en pantalla y se exportan a PDF o CSV."""
from datetime import date, timedelta

import flet as ft

from app.presentacion.componentes import (COLOR_PRIMARIO, Tabla, abrir_archivo, campo_fecha, encabezado, leer_fecha,
                                          seccion, selector, tarjeta_indicador)
from app.presentacion.vistas.base_vista import Vista
from app.reportes.exportador import exportar_csv, exportar_pdf
from app.reportes.graficos import generar_png
from app.reportes.modelo import Reporte


class ReportesVista(Vista):
    def construir(self) -> ft.Control:
        self._definiciones = self.servicios.reportes.catalogo()
        self._clave = self._definiciones[0].clave
        self._reporte: Reporte | None = None
        self.lista = ft.Column(spacing=6)
        self.desde = campo_fecha("Desde", date.today() - timedelta(days=90), width=150)
        self.hasta = campo_fecha("Hasta", date.today(), width=150)
        self.agrupar = selector("Agrupar por", [], width=220)
        self.resultado = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        acciones = ft.Row([
            self.desde, self.hasta, self.agrupar,
            ft.FilledButton("Generar", icon=ft.Icons.PLAY_ARROW, on_click=self.seguro(lambda e: self._generar())),
            ft.OutlinedButton("PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=self.seguro(lambda e: self._exportar(exportar_pdf))),
            ft.OutlinedButton("CSV", icon=ft.Icons.TABLE_VIEW, on_click=self.seguro(lambda e: self._exportar(exportar_csv))),
        ], wrap=True)
        return ft.Column([
            encabezado("Reportes", "Indicadores de atención, laboratorio, transporte y facturación"),
            ft.Row([ft.Container(self.lista, width=300),
                    ft.Column([acciones, self.resultado], expand=True, spacing=12)],
                   expand=True, vertical_alignment=ft.CrossAxisAlignment.START, spacing=18),
        ], expand=True, spacing=12)

    def al_mostrar(self, **contexto) -> None:
        self._mostrar_lista()
        self._generar()

    def _mostrar_lista(self) -> None:
        def elegir(clave: str):
            return self.seguro(lambda e: (setattr(self, "_clave", clave), self._mostrar_lista(), self._generar()))
        self.lista.controls = [
            ft.Container(ft.ListTile(leading=ft.Icon(getattr(ft.Icons, d.icono.upper(), ft.Icons.INSIGHTS),
                                                     color=COLOR_PRIMARIO),
                                     title=ft.Text(d.titulo, size=14, weight=ft.FontWeight.W_600),
                                     subtitle=ft.Text(d.descripcion, size=12), on_click=elegir(d.clave),
                                     selected=d.clave == self._clave),
                         border_radius=10, border=ft.Border.all(1, COLOR_PRIMARIO if d.clave == self._clave
                                                                else ft.Colors.OUTLINE_VARIANT),
                         bgcolor=ft.Colors.with_opacity(0.06, COLOR_PRIMARIO) if d.clave == self._clave else None)
            for d in self._definiciones]
        definicion = next(d for d in self._definiciones if d.clave == self._clave)
        self.agrupar.options = [ft.DropdownOption(key=k, text=t) for k, t in definicion.agrupaciones.items()]
        self.agrupar.visible = bool(definicion.agrupaciones)
        if definicion.agrupaciones and self.agrupar.value not in definicion.agrupaciones:
            self.agrupar.value = next(iter(definicion.agrupaciones))

    def _generar(self) -> None:
        reporte = self.servicios.reportes.generar(self._clave, leer_fecha(self.desde, True), leer_fecha(self.hasta, True),
                                                  self.agrupar.value if self.agrupar.visible else None)
        self._reporte = reporte
        controles = [ft.Column([ft.Text(reporte.titulo, size=20, weight=ft.FontWeight.BOLD),
                                ft.Text(reporte.descripcion, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(" · ".join(f"{k}: {v}" for k, v in reporte.parametros.items()), size=12)],
                               spacing=2)]
        if reporte.indicadores:
            ancho = 12 / len(reporte.indicadores)  # todas las tarjetas en una fila en pantallas anchas
            controles.append(ft.ResponsiveRow([ft.Container(tarjeta_indicador(nombre, valor, ft.Icons.ANALYTICS),
                                                            col={"md": 6, "xl": ancho}) for nombre, valor in reporte.indicadores],
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
