"""Trazabilidad inmutable de cada muestra: historial completo de estados desde la extracción."""
import flet as ft

from app.presentacion.componentes import (COLORES_ESTADO, Tabla, abrir_dialogo, boton_cancelar, boton_icono, campo,
                                          campo_numero, chip, encabezado, fila, leer_decimal, leer_texto)
from app.presentacion.vistas.base_vista import Vista
from app.utils import fechas, formato

ICONOS_ESTADO = {
    "EXTRAIDA": ft.Icons.COLORIZE, "EMPAQUETADA": ft.Icons.INVENTORY_2, "EN_TRANSITO": ft.Icons.LOCAL_SHIPPING,
    "RECIBIDA": ft.Icons.MOVE_TO_INBOX, "ANALIZADA": ft.Icons.FACT_CHECK, "RECHAZADA": ft.Icons.BLOCK,
}


class TrazabilidadVista(Vista):
    def construir(self) -> ft.Control:
        self.busqueda = campo("Código de muestra, orden o mascota", prefix_icon=ft.Icons.SEARCH,
                              on_change=self.seguro(lambda e: self.al_mostrar()))
        self.tabla = Tabla(["Muestra", "Tipo", "Estado", "Extracción", "Orden", "Remito", "Mascota", "Análisis"],
                           acciones=self._acciones, vacio="No se encontraron muestras.")
        return ft.Column([
            encabezado("Trazabilidad de muestras",
                       "El historial de estados es inmutable: solo se agregan cambios, nunca se modifican ni borran"),
            fila(self.busqueda), self.tabla.control], expand=True, spacing=12)

    def al_mostrar(self, **contexto) -> None:
        muestras = self.servicios.derivaciones.buscar_muestras(self.busqueda.value or "")
        self.tabla.cargar([[m["codigo"], formato.etiqueta(m["tipo"]), chip(m["estado"]),
                            fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(m["fecha_hora_extraccion"])),
                            m["orden"], m["remito"] or "—", m["mascota"], m["analisis"]] for m in muestras], muestras)

    def _acciones(self, muestra: dict) -> list[ft.Control]:
        acciones = [boton_icono(ft.Icons.TIMELINE, "Ver historial de estados",
                                self.seguro(lambda e: self._historial(muestra["id_muestra"])))]
        if muestra["estado"] == "RECHAZADA":
            acciones.append(boton_icono(ft.Icons.REPLAY, "Registrar nueva extracción",
                                        self.seguro(lambda e: self._dialogo_reextraccion(muestra)), ft.Colors.ORANGE_800))
        return acciones

    def _historial(self, id_muestra: int) -> None:
        muestra = self.servicios.derivaciones.trazabilidad(id_muestra)
        pasos = []
        for cambio in muestra.historial():  # recorrido con el iterador del historial (patrón Iterator)
            color = COLORES_ESTADO.get(cambio.estado_nuevo, ft.Colors.BLUE_GREY_600)
            negrita = lambda texto: ft.Text(texto, weight=ft.FontWeight.W_600)
            transicion = [negrita(formato.etiqueta(cambio.estado_anterior)),
                          ft.Icon(ft.Icons.ARROW_FORWARD, size=16)] if cambio.estado_anterior else []
            pasos.append(ft.ListTile(
                leading=ft.Container(ft.Icon(ICONOS_ESTADO.get(cambio.estado_nuevo), color=ft.Colors.WHITE, size=18),
                                     bgcolor=color, border_radius=20, padding=8),
                title=ft.Row([*transicion, negrita(formato.etiqueta(cambio.estado_nuevo))], spacing=6),
                subtitle=ft.Text(f"{fechas.formatear_fecha_hora(cambio.fecha_hora)} · {cambio.responsable}"
                                 + (f"\n{cambio.observacion}" if cambio.observacion else "")),
                is_three_line=bool(cambio.observacion)))
        rango = muestra.rango_temperatura_requerido()
        resumen = ft.Row([chip(muestra.nombre_estado()), ft.Text(f"{formato.etiqueta(muestra.tipo)} · "
                                                                  f"{len(muestra.historial())} cambios registrados"),
                          ft.Text(f"Conservación {rango[0]:g} a {rango[1]:g} °C · viabilidad "
                                  f"{muestra.horas_max_viabilidad()} h" if rango else "")], wrap=True)
        abrir_dialogo(self.page, f"Trazabilidad de la muestra {muestra.codigo}",
                      ft.Column([resumen, ft.Divider(), *pasos], scroll=ft.ScrollMode.AUTO, spacing=0),
                      [boton_cancelar(self.page, "Cerrar")], ancho=640, alto=520)

    def _dialogo_reextraccion(self, muestra: dict) -> None:
        responsable = campo("Responsable de la extracción *")
        volumen = campo_numero("Volumen (ml)")

        def registrar(e):
            nueva = self.servicios.derivaciones.reextraer_muestra(muestra["id_muestra"], leer_texto(responsable, True),
                                                                  leer_decimal(volumen))
            self.page.pop_dialog()
            self.notificar.exito(f"Nueva muestra {nueva.codigo} registrada; queda pendiente de empaquetar.")
            self.al_mostrar()
            self.page.update()

        abrir_dialogo(self.page, f"Nueva extracción para {muestra['codigo']}", ft.Column([
            ft.Text("La muestra rechazada conserva su historial. Los análisis sin resultado se asignan a la nueva "
                    "muestra de la misma orden."), responsable, volumen], tight=True, spacing=12),
            [boton_cancelar(self.page), ft.FilledButton("Registrar extracción", on_click=self.seguro(registrar))])
