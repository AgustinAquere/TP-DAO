"""Proceso 7: emitir comprobantes de atención. El total lo calcula la estrategia de tarifa (Strategy)."""
from datetime import date, timedelta

import flet as ft

from app.dominio.enums import TipoItem
from app.dominio.excepciones import ErrorNegocio
from app.dominio.facturacion import ItemComprobante
from app.presentacion.componentes import (Tabla, a_lo_ancho, abrir_archivo, abrir_dialogo, boton_icono, campo,
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

_FONDO_CONTEXTO = "#E7F0EB"
_FONDO_ICONO = "#D3E4DB"
_FONDO_TABLA = "#E4EEE8"
_COLORES_TIPO = {
    TipoItem.SERVICIO_CLINICO: ft.Colors.TEAL_700,
    TipoItem.ANALISIS_LABORATORIO: ft.Colors.PURPLE_400,
    TipoItem.VACUNA: ft.Colors.ORANGE_800,
    TipoItem.INSUMO: ft.Colors.BLUE_GREY_600,
}

# Las atenciones pendientes van en un panel de ancho fijo: repartido en proporción con el comprobante, en
# ventanas angostas quedaba tan finito que los nombres se escribían de a una letra por renglón.
_ANCHO_PENDIENTES = 340
_ANCHO_FECHA_PENDIENTE = 76
_ANCHO_TIPO_PENDIENTE = 84
# Con el panel del comprobante más angosto que esto, cada ítem ocupa dos renglones (tipo y descripción;
# cantidad, precio e importe): en uno solo, el campo de la descripción quedaba aplastado.
_ANCHO_ITEMS_EN_UN_RENGLON = 720


def _tarjeta_contexto(etiqueta: str, valor: str, icono) -> ft.Container:
    return ft.Container(
        ft.Row([
            ft.Container(ft.Icon(icono, size=20, color=ft.Colors.TEAL_800), width=36, height=36, border_radius=18,
                         bgcolor=_FONDO_ICONO, alignment=ft.Alignment.CENTER),
            ft.Column([ft.Text(etiqueta, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                       ft.Text(valor, size=14, weight=ft.FontWeight.W_600)], spacing=0, expand=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        expand=True, bgcolor=_FONDO_CONTEXTO, border_radius=16,
        padding=ft.Padding.symmetric(horizontal=14, vertical=12))


def _columnas(*controles: ft.Control) -> ft.Row:
    anchos = (None, 210, 52, 130, 120)
    alineacion = (ft.Alignment.CENTER_LEFT, ft.Alignment.CENTER_LEFT, ft.Alignment.CENTER,
                  ft.Alignment.CENTER_RIGHT, ft.Alignment.CENTER_RIGHT)
    celdas = [ft.Container(control, width=ancho, expand=ancho is None, alignment=alin)
              for control, ancho, alin in zip(controles, anchos, alineacion)]
    return ft.Row(celdas, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _encabezado_detalle() -> ft.Container:
    texto = lambda titulo: ft.Text(titulo, size=13, weight=ft.FontWeight.BOLD)
    return ft.Container(
        _columnas(texto("Descripción"), texto("Tipo"), texto("Cant."), texto("Precio unitario"), texto("Importe")),
        bgcolor=_FONDO_TABLA, border_radius=12, padding=ft.Padding.symmetric(horizontal=12, vertical=10))


def _fila_detalle(item: ItemComprobante) -> ft.Container:
    return ft.Container(
        _columnas(ft.Text(item.descripcion, size=13),
                  chip(formato.etiqueta(item.tipo), _COLORES_TIPO[item.tipo]),
                  ft.Text(str(item.cantidad), size=13),
                  ft.Text(formato.moneda(item.precio_unitario), size=13),
                  ft.Text(formato.moneda(item.importe()), size=13)),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.35, ft.Colors.OUTLINE_VARIANT))))


def _linea_total(texto: str, valor: float, destacado: bool = False) -> ft.Text:
    return ft.Text(f"{texto}: {formato.moneda(valor)}", size=18 if destacado else 14,
                   weight=ft.FontWeight.BOLD if destacado else None,
                   color=ft.Colors.TEAL_800 if destacado else ft.Colors.ON_SURFACE_VARIANT)


def _dato_contexto(icono, texto: str) -> ft.Container:
    return ft.Container(
        ft.Row([ft.Icon(icono, size=14, color=ft.Colors.TEAL_800),
                ft.Text(texto, size=12, weight=ft.FontWeight.W_600)], spacing=4, tight=True),
        bgcolor=_FONDO_CONTEXTO, border_radius=12, padding=ft.Padding.symmetric(horizontal=8, vertical=2))


def _pista_comprobante() -> ft.Text:
    return ft.Text("Seleccione una atención para preparar su comprobante.", italic=True, size=13,
                   color=ft.Colors.ON_SURFACE_VARIANT)


def _encabezado_pendientes() -> ft.Container:
    texto = lambda titulo: ft.Text(titulo, size=13, weight=ft.FontWeight.BOLD)
    return ft.Container(
        ft.Row([ft.Container(texto("Fecha"), width=_ANCHO_FECHA_PENDIENTE),
                ft.Container(texto("Paciente"), expand=True),
                ft.Container(texto("Tipo"), width=_ANCHO_TIPO_PENDIENTE),
                ft.Container(width=40)], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=_FONDO_TABLA, border_radius=12, padding=ft.Padding.symmetric(horizontal=8, vertical=10))


class FacturacionVista(Vista):
    def construir(self) -> ft.Control:
        self._id_atencion: int | None = None
        self._items: list[ItemComprobante] = []
        self._items_en_dos_renglones = False
        self._importes: list[ft.Text] = []
        self._lecturas_items: list = []
        self.lista_pendientes = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)
        self.vacio_pendientes = ft.Text("Todas las atenciones están facturadas.", italic=True,
                                        color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        self.contexto = ft.Row([_pista_comprobante()], wrap=True, spacing=6, run_spacing=4)
        self.lista_items = ft.Column(spacing=6)
        self.servicio = selector("Servicio clínico", [], width=260)
        self.insumo = campo("Insumo", width=220)
        self.precio_insumo = campo_numero("Precio", width=110)
        self.totales = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2)
        self.boton_emitir = ft.FilledButton("Emitir comprobante", icon=ft.Icons.RECEIPT_LONG, disabled=True,
                                            on_click=self.seguro(self._emitir))
        editor = seccion("Comprobante", ft.Icons.RECEIPT_LONG, self.contexto, self.lista_items,
                         ft.Row([self.servicio, ft.IconButton(ft.Icons.ADD_CIRCLE, tooltip="Agregar servicio",
                                                              on_click=self.seguro(self._agregar_servicio)),
                                 self.insumo, self.precio_insumo,
                                 ft.IconButton(ft.Icons.ADD_CIRCLE, tooltip="Agregar insumo",
                                               on_click=self.seguro(self._agregar_insumo))], wrap=True),
                         ft.Divider(),
                         ft.Row([ft.Column([self.totales, self.boton_emitir],
                                           horizontal_alignment=ft.CrossAxisAlignment.END, spacing=8)],
                                alignment=ft.MainAxisAlignment.END))
        editor.content.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        editor.on_size_change = self._al_cambiar_ancho_editor
        editor.size_change_interval = 100
        pendientes = ft.Column([_encabezado_pendientes(), self.lista_pendientes, self.vacio_pendientes],
                               expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        emitir = ft.Row([ft.Container(pendientes, width=_ANCHO_PENDIENTES),
                         ft.Container(ft.Column([editor], scroll=ft.ScrollMode.AUTO,
                                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH), expand=True)],
                        vertical_alignment=ft.CrossAxisAlignment.START, expand=True, spacing=16)

        # En una sola fila con anchos fijos, el buscador quedaba aplastado en ventanas angostas: los filtros
        # se acomodan en dos filas hasta que la ventana es bien ancha (xxl), como en el historial de atenciones.
        recargar = self.seguro(lambda e: self._cargar_emitidos())
        col_fecha = {"xs": 6, "md": 3, "xxl": 2}
        self.desde = campo_fecha("Desde", date.today() - timedelta(days=30), col=col_fecha, al_cambiar=recargar,
                                 on_submit=recargar)
        self.hasta = campo_fecha("Hasta", date.today(), col=col_fecha, al_cambiar=recargar, on_submit=recargar)
        self.filtro_clinica = selector("Clínica", [], "", expand=True, on_select=recargar)
        self.busqueda = campo("Número, mascota, responsable o DNI", expand=True, on_submit=recargar)
        self.emitidos = Tabla(["Número", "Emisión", "Cliente", "Mascota", "Clínica", "Tarifa", ("Subtotal", True),
                               ("Total", True)], acciones=self._acciones_emitido,
                              vacio="No hay comprobantes con esos filtros.")
        buscador = ft.Row([
            self.busqueda,
            ft.IconButton(ft.Icons.SEARCH, tooltip="Buscar", on_click=recargar),
            ft.IconButton(ft.Icons.FILTER_ALT_OFF, tooltip="Quitar filtros",
                          on_click=self.seguro(self._limpiar_filtros)),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER, col={"xs": 12, "xxl": 5})
        filtros = ft.ResponsiveRow([self.desde, self.hasta,
                                    a_lo_ancho(self.filtro_clinica, {"xs": 12, "md": 6, "xxl": 3}), buscador],
                                   spacing=12, run_spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        emitidos = ft.Column([filtros, self.emitidos.control], expand=True, spacing=10)
        pestania = lambda control: ft.Container(control, padding=ft.Padding.only(top=12))
        self.pestanias = ft.Tabs(length=2, selected_index=0, expand=True,
                                 on_change=self.sincronizar_pestania("facturacion"), content=ft.Column([
            ft.TabBar(tabs=[ft.Tab(label="Emitir comprobante", icon=ft.Icons.POINT_OF_SALE),
                            ft.Tab(label="Comprobantes emitidos", icon=ft.Icons.RECEIPT_LONG)]),
            ft.TabBarView(controls=[pestania(emitir), pestania(emitidos)], expand=True)], expand=True))
        return ft.Column([encabezado("Facturación", "Comprobantes de atención con tarifa según el tipo de atención"),
                          self.pestanias], expand=True, spacing=10)

    def al_mostrar(self, id_atencion: int | None = None, pestania: int | None = None, **contexto) -> None:
        cargar_opciones(self.servicio, [(s.id, f"{s.nombre} ({formato.moneda(s.precio_base)})")
                                        for s in self.servicios.facturacion.servicios_clinicos()])
        cargar_opciones(self.filtro_clinica, [("", "Todas")] + self.opciones_clinicas())
        self._cargar_pendientes()
        self._cargar_emitidos()
        if pestania is not None:
            self.pestanias.selected_index = pestania
        if id_atencion:
            self.pestanias.selected_index = 0
            self._seleccionar(id_atencion)

    def _cargar_pendientes(self) -> None:
        atenciones = self.servicios.facturacion.atenciones_sin_comprobante()
        self.vacio_pendientes.visible = not atenciones
        self.lista_pendientes.controls = [self._fila_pendiente(atencion) for atencion in atenciones]

    def _fila_pendiente(self, atencion: dict) -> ft.Container:
        un_renglon = dict(max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        paciente = ft.Column([ft.Text(atencion["mascota"], size=13, weight=ft.FontWeight.W_600, **un_renglon),
                              ft.Text(atencion["responsable"], size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                                      **un_renglon)],
                             spacing=0, tight=True)
        momento = fechas.fecha_hora_desde_sql(atencion["fecha_hora"])
        fecha = ft.Column([ft.Text(fechas.formatear_fecha(momento), size=12),
                           ft.Text(momento.strftime("%H:%M"), size=12, color=ft.Colors.ON_SURFACE_VARIANT)],
                          spacing=0, tight=True)
        fila = ft.Container(
            ft.Row([
                ft.Container(fecha, width=_ANCHO_FECHA_PENDIENTE),
                ft.Container(paciente, expand=True),
                ft.Container(chip(atencion["tipo"]), width=_ANCHO_TIPO_PENDIENTE),
                boton_icono(ft.Icons.RECEIPT, "Preparar comprobante",
                            self.seguro(lambda e, id_atencion=atencion["id_atencion"]: self._seleccionar(id_atencion))),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            data=atencion["id_atencion"], padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.35, ft.Colors.OUTLINE_VARIANT))))
        self._pintar_fila(fila, atencion["id_atencion"] == self._id_atencion)
        return fila

    def _pintar_fila(self, fila: ft.Container, seleccionada: bool) -> None:
        fila.bgcolor = ft.Colors.with_opacity(0.55, ft.Colors.GREY_200) if seleccionada else None
        fila.border_radius = 10 if seleccionada else 0
        fila.shadow = ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.16, ft.Colors.BLACK),
                                   offset=ft.Offset(0, 1)) if seleccionada else None

    def _marcar_seleccion(self) -> None:
        for fila in self.lista_pendientes.controls:
            if isinstance(fila, ft.Container):
                self._pintar_fila(fila, fila.data == self._id_atencion)

    # --- Edición del comprobante ------------------------------------------------------------
    def _seleccionar(self, id_atencion: int) -> None:
        resumen = self.servicios.atenciones.resumen(id_atencion)
        self._id_atencion = id_atencion
        self._items = self.servicios.facturacion.items_sugeridos(id_atencion)
        self.contexto.controls = [
            _dato_contexto(ft.Icons.PETS, resumen["mascota"]),
            _dato_contexto(ft.Icons.PERSON, resumen["responsable"]),
            _dato_contexto(ft.Icons.APARTMENT, resumen["clinica"]),
            _dato_contexto(ft.Icons.CALENDAR_MONTH_OUTLINED,
                           fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(resumen["fecha_hora"]))),
        ]
        self._marcar_seleccion()
        self._mostrar_items()

    def _mostrar_items(self) -> None:
        def leer_campos(item: ItemComprobante, descripcion, cantidad, precio):
            def leer():
                item.descripcion = leer_texto(descripcion) or ""
                item.cantidad = leer_entero(cantidad, True)
                item.precio_unitario = leer_decimal(precio, True)
            return leer

        def quitar(item: ItemComprobante):
            return self.seguro(lambda e: (self._items.remove(item), self._mostrar_items(), self.page.update()))

        filas, self._importes, self._lecturas_items = [], [], []
        dos_renglones = self._items_en_dos_renglones
        for item in self._items:
            descripcion = campo("Descripción", item.descripcion, expand=True)
            cantidad = campo_numero("Cant.", item.cantidad, width=80)
            # En dos renglones el precio comparte el suyo solo con la cantidad y el importe: ocupa lo que sobra.
            ancho_precio = {"expand": True} if dos_renglones else {"width": 130}
            precio = campo("Precio unitario", numero_editable(item.precio_unitario),
                           keyboard_type=ft.KeyboardType.NUMBER, **ancho_precio)
            leer = leer_campos(item, descripcion, cantidad, precio)
            actualizar = self.seguro(lambda e, leer=leer: (leer(), self._recalcular()))
            for control in (descripcion, cantidad, precio):
                control.on_blur = control.on_submit = actualizar
            tipo = ft.Container(chip(*ETIQUETAS_ITEM[item.tipo]), width=110)
            importe = ft.Text(formato.moneda(item.importe()), width=110, text_align=ft.TextAlign.RIGHT)
            boton_quitar = ft.IconButton(ft.Icons.CLOSE, tooltip="Quitar ítem", on_click=quitar(item))
            if dos_renglones:
                centrado = ft.CrossAxisAlignment.CENTER
                filas.append(ft.Container(
                    ft.Column([ft.Row([tipo, descripcion, boton_quitar], vertical_alignment=centrado),
                               ft.Row([cantidad, precio, importe], vertical_alignment=centrado)], spacing=8),
                    padding=ft.Padding.only(bottom=8),
                    border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.35,
                                                                                         ft.Colors.OUTLINE_VARIANT)))))
            else:
                filas.append(ft.Row([tipo, descripcion, cantidad, precio, importe, boton_quitar]))
            self._importes.append(importe)
            self._lecturas_items.append(leer)
        self.lista_items.controls = filas or [ft.Text("El comprobante no tiene ítems.", italic=True)]
        self._recalcular()

    def _al_cambiar_ancho_editor(self, e: ft.LayoutSizeChangeEvent) -> None:
        """Acomoda los ítems en uno o dos renglones según el ancho que le deja la ventana al comprobante."""
        dos_renglones = e.width < _ANCHO_ITEMS_EN_UN_RENGLON
        if dos_renglones == self._items_en_dos_renglones:
            return
        self._items_en_dos_renglones = dos_renglones
        if self._items:
            self.seguro(self._reacomodar_items)(e)

    def _reacomodar_items(self, e=None) -> None:
        # Los campos se vuelven a crear: antes se guarda lo tipeado que todavía no se confirmó (sin perder el foco).
        for leer in self._lecturas_items:
            try:
                leer()
            except ErrorNegocio:
                pass  # un valor a medio escribir: el ítem conserva el anterior
        self._mostrar_items()

    def _recalcular(self) -> None:
        if self._id_atencion is None:
            return
        comprobante = self.servicios.facturacion.preparar(self._id_atencion, self._items)
        self.totales.controls = [_linea_total("Subtotal", comprobante.subtotal()),
                                 _linea_total("Recargo / Descuento", comprobante.ajuste()),
                                 _linea_total("TOTAL", comprobante.total(), True)]
        for importe, item in zip(self._importes, self._items):
            importe.value = formato.moneda(item.importe())
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
        self.contexto.controls = [_pista_comprobante()]
        self.boton_emitir.disabled = True
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
    def _limpiar_filtros(self, e=None) -> None:
        self.busqueda.value = ""
        self.filtro_clinica.value = ""
        self.desde.value = fechas.formatear_fecha(date.today() - timedelta(days=30))
        self.hasta.value = fechas.formatear_fecha(date.today())
        self._cargar_emitidos()

    def _cargar_emitidos(self) -> None:
        comprobantes = self.servicios.facturacion.listar(
            leer_fecha(self.desde), leer_fecha(self.hasta),
            int(self.filtro_clinica.value) if self.filtro_clinica.value else None,
            self.busqueda.value or "")
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
        filas = [_fila_detalle(item) for item in comprobante.items] or [
            ft.Text("El comprobante no tiene ítems.", italic=True)]
        contenido = ft.Column([
            ft.Row([
                _tarjeta_contexto("Clínica:", fila["clinica"], ft.Icons.APARTMENT),
                _tarjeta_contexto("Responsable:", f"{fila['cliente']} (DNI {fila['dni']})", ft.Icons.PERSON),
                _tarjeta_contexto("Paciente:", f"{fila['mascota']} ({fila['especie']})", ft.Icons.PETS),
            ], spacing=12),
            ft.Column([_encabezado_detalle(), *filas], spacing=0),
            ft.Column([_linea_total("Subtotal", comprobante.subtotal()),
                       _linea_total("Recargo / Descuento", comprobante.ajuste()),
                       _linea_total("TOTAL", comprobante.total(), True)],
                      horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
        ], tight=True, spacing=16)
        estilo_pill = dict(shape=ft.RoundedRectangleBorder(radius=20),
                           padding=ft.Padding.symmetric(horizontal=18, vertical=10))
        cerrar = ft.OutlinedButton("Cerrar", on_click=lambda e: self.page.pop_dialog(),
                                   style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT,
                                                        side=ft.BorderSide(1, ft.Colors.OUTLINE), **estilo_pill))
        descargar = ft.FilledButton("Descargar PDF", icon=ft.Icons.DOWNLOAD,
                                    style=ft.ButtonStyle(bgcolor=ft.Colors.TEAL_800, color=ft.Colors.WHITE, **estilo_pill),
                                    on_click=self.seguro(lambda e: self._pdf(fila, fila["id_atencion"])))
        abrir_dialogo(self.page, f"Comprobante {comprobante.numero}", contenido, [cerrar, descargar], ancho=920)

    def _pdf(self, fila: dict, id_atencion: int) -> None:
        comprobante = self.servicios.facturacion.obtener(fila["id_comprobante"])
        ruta = exportar_comprobante_pdf(comprobante, fila, self.servicios.facturacion.descripcion_tarifa(id_atencion))
        self.notificar.exito(f"PDF generado: {ruta}")
        abrir_archivo(ruta)
