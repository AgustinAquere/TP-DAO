"""Proceso 7: emitir comprobantes de atención. El total lo calcula la estrategia de tarifa (Strategy)."""
from datetime import date, timedelta

import flet as ft

from app.dominio.enums import TipoItem
from app.dominio.facturacion import ItemComprobante
from app.presentacion.componentes import (Tabla, abrir_archivo, abrir_dialogo, boton_cancelar, boton_icono, campo,
                                          campo_fecha, campo_numero, cargar_opciones, chip, encabezado, leer_decimal,
                                          leer_entero, leer_fecha, leer_id, leer_texto, numero_editable, seccion,
                                          selector)
from app.presentacion.vistas.base_vista import Vista
from app.reportes.exportador import exportar_comprobante_pdf
from app.utils import fechas, formato

ETIQUETAS_ITEM = {
    TipoItem.SERVICIO_CLINICO: ("Servicio", ft.Colors.TEAL_700),
    TipoItem.ANALISIS_LABORATORIO: ("Análisis", ft.Colors.PURPLE_500),
    TipoItem.VACUNA: ("Vacuna", ft.Colors.ORANGE_800),
    TipoItem.INSUMO: ("Insumo", ft.Colors.BLUE_GREY_600),
}


class FacturacionVista(Vista):
    def construir(self) -> ft.Control:
        self._id_atencion: int | None = None
        self._items: list[ItemComprobante] = []
        self.pendientes = Tabla(["Fecha", "Paciente", "Tipo"],
                                acciones=lambda a: [boton_icono(ft.Icons.RECEIPT, "Preparar comprobante",
                                                                self.seguro(lambda e: self._seleccionar(a["id_atencion"])))],
                                vacio="Todas las atenciones están facturadas.")
        self.titulo_atencion = ft.Text("Seleccione una atención para preparar su comprobante.", italic=True)
        self.tarifa = ft.Text(color=ft.Colors.TEAL_800, weight=ft.FontWeight.W_600)
        self.lista_items = ft.Column(spacing=6)
        self.servicio = selector("Servicio clínico", [], width=260)
        self.insumo = campo("Insumo", width=220)
        self.precio_insumo = campo_numero("Precio", width=110)
        self.totales = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
        self.boton_emitir = ft.FilledButton("Emitir comprobante", icon=ft.Icons.RECEIPT_LONG, disabled=True,
                                            on_click=self.seguro(self._emitir))
        editor = seccion("Comprobante", ft.Icons.RECEIPT_LONG, self.titulo_atencion, self.tarifa, self.lista_items,
                         ft.Row([self.servicio, ft.IconButton(ft.Icons.ADD_CIRCLE, tooltip="Agregar servicio",
                                                              on_click=self.seguro(self._agregar_servicio)),
                                 self.insumo, self.precio_insumo,
                                 ft.IconButton(ft.Icons.ADD_CIRCLE, tooltip="Agregar insumo",
                                               on_click=self.seguro(self._agregar_insumo))], wrap=True),
                         ft.Divider(), self.totales, ft.Row([self.boton_emitir], alignment=ft.MainAxisAlignment.END))
        emitir = ft.Row([ft.Container(self.pendientes.control, expand=4),
                         ft.Container(ft.Column([editor], scroll=ft.ScrollMode.AUTO), expand=7)],
                        vertical_alignment=ft.CrossAxisAlignment.START, expand=True, spacing=16)

        recargar = self.seguro(lambda e: self._cargar_emitidos())
        self.desde = campo_fecha("Desde", date.today() - timedelta(days=30), width=150, on_submit=recargar)
        self.hasta = campo_fecha("Hasta", date.today(), width=150, on_submit=recargar)
        self.filtro_clinica = selector("Clínica", [], "", width=280, on_select=recargar)
        self.emitidos = Tabla(["Número", "Emisión", "Cliente", "Mascota", "Clínica", "Tarifa", ("Subtotal", True),
                               ("Total", True)], acciones=self._acciones_emitido, vacio="No hay comprobantes en el período.")
        emitidos = ft.Column([ft.Row([self.desde, self.hasta, self.filtro_clinica,
                                      ft.IconButton(ft.Icons.SEARCH, tooltip="Buscar", on_click=recargar)]),
                              self.emitidos.control], expand=True, spacing=10)
        pestania = lambda control: ft.Container(control, padding=ft.Padding.only(top=12))
        self.pestanias = ft.Tabs(length=2, selected_index=0, expand=True, content=ft.Column([
            ft.TabBar(tabs=[ft.Tab(label="Emitir comprobante", icon=ft.Icons.POINT_OF_SALE),
                            ft.Tab(label="Comprobantes emitidos", icon=ft.Icons.RECEIPT_LONG)]),
            ft.TabBarView(controls=[pestania(emitir), pestania(emitidos)], expand=True)], expand=True))
        return ft.Column([encabezado("Facturación", "Comprobantes de atención con tarifa según el tipo de atención"),
                          self.pestanias], expand=True, spacing=10)

    def al_mostrar(self, id_atencion: int | None = None, **contexto) -> None:
        cargar_opciones(self.servicio, [(s.id, f"{s.nombre} ({formato.moneda(s.precio_base)})")
                                        for s in self.servicios.facturacion.servicios_clinicos()])
        cargar_opciones(self.filtro_clinica, [("", "Todas")] + self.opciones_clinicas())
        self._cargar_pendientes()
        self._cargar_emitidos()
        if id_atencion:
            self.pestanias.selected_index = 0
            self._seleccionar(id_atencion)

    def _cargar_pendientes(self) -> None:
        atenciones = self.servicios.facturacion.atenciones_sin_comprobante()
        paciente = lambda a: ft.Column([ft.Text(a["mascota"], size=13, weight=ft.FontWeight.W_600),
                                        ft.Text(a["responsable"], size=12, color=ft.Colors.ON_SURFACE_VARIANT)],
                                       spacing=0, tight=True)
        self.pendientes.cargar([[fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(a["fecha_hora"])), paciente(a),
                                 chip(a["tipo"])] for a in atenciones], atenciones)

    # --- Edición del comprobante ------------------------------------------------------------
    def _seleccionar(self, id_atencion: int) -> None:
        resumen = self.servicios.atenciones.resumen(id_atencion)
        self._id_atencion = id_atencion
        self._items = self.servicios.facturacion.items_sugeridos(id_atencion)
        self.titulo_atencion.value = (f"{resumen['mascota']} · {resumen['responsable']} · {resumen['clinica']} · "
                                      f"{fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(resumen['fecha_hora']))}")
        self.titulo_atencion.italic = False
        self.tarifa.value = f"Estrategia de tarifa: {self.servicios.facturacion.descripcion_tarifa(id_atencion)}"
        self._mostrar_items()

    def _mostrar_items(self) -> None:
        def al_cambiar(item: ItemComprobante, descripcion, cantidad, precio):
            def actualizar(e):
                item.descripcion = leer_texto(descripcion) or ""
                item.cantidad = leer_entero(cantidad, True)
                item.precio_unitario = leer_decimal(precio, True)
                self._recalcular()
            return self.seguro(actualizar)

        def quitar(item: ItemComprobante):
            return self.seguro(lambda e: (self._items.remove(item), self._mostrar_items(), self.page.update()))

        filas = []
        for item in self._items:
            descripcion = campo("Descripción", item.descripcion, expand=True)
            cantidad = campo_numero("Cant.", item.cantidad, width=80)
            precio = campo("Precio unitario", numero_editable(item.precio_unitario), width=130,
                           keyboard_type=ft.KeyboardType.NUMBER)
            for control in (descripcion, cantidad, precio):
                control.on_blur = control.on_submit = al_cambiar(item, descripcion, cantidad, precio)
            filas.append(ft.Row([ft.Container(chip(*ETIQUETAS_ITEM[item.tipo]), width=110),
                                 descripcion, cantidad, precio,
                                 ft.Text(formato.moneda(item.importe()), width=110, text_align=ft.TextAlign.RIGHT),
                                 ft.IconButton(ft.Icons.CLOSE, tooltip="Quitar ítem", on_click=quitar(item))]))
        self.lista_items.controls = filas or [ft.Text("El comprobante no tiene ítems.", italic=True)]
        self._recalcular()

    def _recalcular(self) -> None:
        if self._id_atencion is None:
            return
        comprobante = self.servicios.facturacion.preparar(self._id_atencion, self._items)
        linea = lambda texto, valor, negrita=False: ft.Text(f"{texto}: {formato.moneda(valor)}", size=16 if negrita else 14,
                                                            weight=ft.FontWeight.BOLD if negrita else None)
        self.totales.controls = [linea("Subtotal", comprobante.subtotal()),
                                 linea("Recargo / descuento por tarifa", comprobante.ajuste()),
                                 linea("TOTAL", comprobante.total(), True)]
        for fila, item in zip(self.lista_items.controls, self._items):
            if isinstance(fila, ft.Row):
                fila.controls[4].value = formato.moneda(item.importe())
        self.boton_emitir.disabled = not self._items

    def _agregar_servicio(self, e) -> None:
        id_servicio = leer_id(self.servicio, True)
        servicio = next(s for s in self.servicios.facturacion.servicios_clinicos() if s.id == id_servicio)
        self._items.append(ItemComprobante(tipo=TipoItem.SERVICIO_CLINICO, descripcion=servicio.nombre,
                                           precio_unitario=servicio.precio_base, id_servicio=servicio.id))
        self._mostrar_items()

    def _agregar_insumo(self, e) -> None:
        self._items.append(ItemComprobante(tipo=TipoItem.INSUMO, descripcion=leer_texto(self.insumo, True),
                                           precio_unitario=leer_decimal(self.precio_insumo, True)))
        self.insumo.value, self.precio_insumo.value = "", ""
        self._mostrar_items()

    def _emitir(self, e) -> None:
        if self._id_atencion is None:
            return
        comprobante = self.servicios.facturacion.emitir(self._id_atencion, self._items)
        id_atencion = self._id_atencion
        self._id_atencion, self._items = None, []
        self.lista_items.controls, self.totales.controls = [], []
        self.titulo_atencion.value, self.titulo_atencion.italic = "Seleccione una atención para preparar su comprobante.", True
        self.tarifa.value, self.boton_emitir.disabled = "", True
        self._cargar_pendientes()
        self._cargar_emitidos()
        fila = next((c for c in self.servicios.facturacion.listar() if c["id_comprobante"] == comprobante.id), None)

        def abrir_pdf(e):
            self.page.pop_dialog()
            self._pdf(fila, id_atencion)

        abrir_dialogo(self.page, "Comprobante emitido", ft.Text(
            f"Comprobante {comprobante.numero} emitido por {formato.moneda(comprobante.total())} "
            f"(tarifa {formato.etiqueta(comprobante.estrategia_tarifa).lower()})."),
            [ft.TextButton("Generar PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=self.seguro(abrir_pdf)),
             ft.FilledButton("Aceptar", on_click=lambda e: self.page.pop_dialog())], ancho=460)

    # --- Comprobantes emitidos ------------------------------------------------------------------
    def _cargar_emitidos(self) -> None:
        comprobantes = self.servicios.facturacion.listar(leer_fecha(self.desde), leer_fecha(self.hasta),
                                                         int(self.filtro_clinica.value) if self.filtro_clinica.value else None)
        self.emitidos.cargar([[c["numero"], fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(c["fecha_emision"])),
                               c["cliente"], c["mascota"], c["clinica"], chip(c["estrategia_tarifa"]),
                               formato.moneda(c["subtotal"]), formato.moneda(c["total"])] for c in comprobantes],
                             comprobantes)

    def _acciones_emitido(self, fila: dict) -> list[ft.Control]:
        return [boton_icono(ft.Icons.VISIBILITY, "Ver detalle", self.seguro(lambda e: self._detalle(fila))),
                boton_icono(ft.Icons.PICTURE_AS_PDF, "Generar PDF",
                            self.seguro(lambda e: self._pdf(fila, fila["id_atencion"])))]

    def _detalle(self, fila: dict) -> None:
        comprobante = self.servicios.facturacion.obtener(fila["id_comprobante"])
        tabla = Tabla(["Descripción", "Tipo", ("Cant.", True), ("Precio unitario", True), ("Importe", True)],
                      expandir=False)
        tabla.cargar([[i.descripcion, formato.etiqueta(i.tipo), i.cantidad, formato.moneda(i.precio_unitario),
                       formato.moneda(i.importe())] for i in comprobante.items])
        abrir_dialogo(self.page, f"Comprobante {comprobante.numero}", ft.Column([
            ft.Text(f"{fila['clinica']} · {fila['cliente']} (DNI {fila['dni']}) · {fila['mascota']}"),
            tabla.control,
            ft.Text(f"Subtotal {formato.moneda(comprobante.subtotal())} · Recargo/descuento "
                    f"{formato.moneda(comprobante.ajuste())} · TOTAL {formato.moneda(comprobante.total())}",
                    weight=ft.FontWeight.BOLD)], tight=True, spacing=10),
            [boton_cancelar(self.page, "Cerrar")], ancho=760)

    def _pdf(self, fila: dict, id_atencion: int) -> None:
        comprobante = self.servicios.facturacion.obtener(fila["id_comprobante"])
        ruta = exportar_comprobante_pdf(comprobante, fila, self.servicios.facturacion.descripcion_tarifa(id_atencion))
        self.notificar.exito(f"PDF generado: {ruta}")
        abrir_archivo(ruta)
