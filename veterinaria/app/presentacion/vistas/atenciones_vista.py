"""Proceso 3: registrar consultas médicas y emitir órdenes de derivación al laboratorio."""
from datetime import date, timedelta

import flet as ft

from app.dominio.atencion import Tratamiento
from app.dominio.enums import EstadoTurno, Prioridad, TipoAtencion
from app.dominio.excepciones import EsquemaVacunasIncompletoError, ValidacionError
from app.presentacion.componentes import (Tabla, abrir_dialogo, boton_cancelar, boton_icono, campo, campo_fecha,
                                          campo_fecha_hora, campo_numero, cargar_opciones, chip, confirmar, encabezado,
                                          fila, leer_decimal, leer_fecha, leer_fecha_hora, leer_id, leer_texto,
                                          numero_editable, seccion, selector)
from app.presentacion.vistas.base_vista import Vista
from app.servicios.atencion_service import SolicitudDerivacion
from app.utils import fechas, formato

TIPOS_ATENCION = [(t.value, formato.etiqueta(t)) for t in TipoAtencion]
PRIORIDADES = [(p.value, formato.etiqueta(p)) for p in Prioridad]


class FormularioDerivacion:
    """Campos de una orden de derivación (se usan al registrar la atención y para órdenes posteriores)."""

    def __init__(self, vista: Vista):
        laboratorios = vista.opciones_laboratorios()
        self.laboratorio = selector("Laboratorio de destino *", laboratorios,
                                    laboratorios[0][0] if laboratorios else None)
        self.prioridad = selector("Prioridad", PRIORIDADES, Prioridad.NORMAL.value)
        self.indicaciones = campo("Indicaciones clínicas", multiline=True, min_lines=1, max_lines=3)
        self.analisis = [
            ft.Checkbox(label=f"{t.nombre}: {formato.etiqueta(t.tipo_muestra_requerida).lower()}, "
                              f"{t.temp_min_c:g} a {t.temp_max_c:g} °C, {t.horas_max_viabilidad} h · {formato.moneda(t.precio)}",
                        data=t.id, col={"md": 12, "lg": 6})
            for t in vista.servicios.catalogos.listar("tipo_analisis")]
        self.control = ft.Column([
            fila(self.laboratorio, self.prioridad), self.indicaciones,
            ft.Text("Análisis a solicitar (se registra una extracción por cada tipo de muestra)", size=13,
                    weight=ft.FontWeight.W_600),
            ft.ResponsiveRow(self.analisis, run_spacing=0)], spacing=10)

    def solicitud(self) -> SolicitudDerivacion:
        ids = [check.data for check in self.analisis if check.value]
        if not ids:
            raise ValidacionError("Seleccione al menos un análisis para la orden de derivación.")
        return SolicitudDerivacion(id_laboratorio=leer_id(self.laboratorio, True), ids_tipo_analisis=ids,
                                   prioridad=Prioridad(self.prioridad.value or "NORMAL"),
                                   indicaciones=leer_texto(self.indicaciones))

    def limpiar(self) -> None:
        for check in self.analisis:
            check.value = False
        self.indicaciones.value, self.prioridad.value = "", Prioridad.NORMAL.value


class AtencionesVista(Vista):
    def construir(self) -> ft.Control:
        self.pestanias = ft.Tabs(length=2, selected_index=0, expand=True, content=ft.Column([
            ft.TabBar(tabs=[ft.Tab(label="Registrar atención", icon=ft.Icons.NOTE_ADD),
                            ft.Tab(label="Atenciones registradas", icon=ft.Icons.HISTORY)]),
            ft.TabBarView(controls=[self._construir_formulario(), self._construir_historial()], expand=True),
        ], expand=True))
        return ft.Column([encabezado("Atenciones clínicas", "Consultas, controles y urgencias; derivación al laboratorio"),
                          self.pestanias], expand=True, spacing=10)

    # --- Formulario de registro -------------------------------------------------------------
    def _construir_formulario(self) -> ft.Control:
        self.turno = selector("Turno reservado (opcional)", [], on_select=self.seguro(self._cambio_turno))
        self.mascota = selector("Mascota *", [], filtrable=True, on_select=self.seguro(self._cambio_mascota))
        self.veterinario = selector("Veterinario *", [], on_select=self.seguro(self._cambio_veterinario))
        self.clinica = selector("Clínica *", [])
        self.tipo = selector("Tipo de atención *", TIPOS_ATENCION, TipoAtencion.CONSULTA.value)
        self.fecha_hora = campo_fecha_hora("Fecha y hora *", fechas.ahora())
        self.motivo = campo("Motivo de consulta *")
        self.anamnesis = campo("Anamnesis", multiline=True, min_lines=2, max_lines=4)
        self.diagnostico = campo("Diagnóstico")
        self.peso = campo_numero("Peso registrado (kg)")
        self.panel_vacunas = ft.Column(spacing=6)
        self.otra_vacuna = selector("Otra vacuna (no obligatoria)", [], width=320)
        self._vacunas_pendientes: list[tuple[ft.Checkbox, ft.TextField]] = []
        self._vacunas_extra: list[tuple[int, str, str]] = []
        self.lista_extra = ft.Row(wrap=True)
        self.lote_extra = campo("Lote", width=140)
        self._tratamientos: list[Tratamiento] = []
        self.lista_tratamientos = ft.Column(spacing=4)
        self.derivacion = FormularioDerivacion(self)
        self.derivar = ft.Switch(label="Emitir orden de derivación al laboratorio",
                                 on_change=self.seguro(self._cambio_derivar))
        self.derivacion.control.visible = False
        formulario = ft.Column([
            seccion("Datos de la atención", ft.Icons.ASSIGNMENT,
                    fila(self.turno, self.tipo), fila(self.mascota, self.fecha_hora),
                    fila(self.veterinario, self.clinica), fila(self.motivo), fila(self.anamnesis),
                    fila(self.diagnostico, self.peso)),
            seccion("Control del esquema de vacunas obligatorias", ft.Icons.VACCINES, self.panel_vacunas,
                    ft.Row([self.otra_vacuna, self.lote_extra,
                            ft.OutlinedButton("Agregar vacuna", icon=ft.Icons.ADD,
                                              on_click=self.seguro(self._agregar_vacuna_extra))]), self.lista_extra),
            seccion("Tratamientos indicados", ft.Icons.MEDICATION, self.lista_tratamientos,
                    ft.OutlinedButton("Agregar tratamiento", icon=ft.Icons.ADD,
                                      on_click=self.seguro(lambda e: self._dialogo_tratamiento()))),
            seccion("Derivación al laboratorio", ft.Icons.BIOTECH, self.derivar, self.derivacion.control),
            ft.Row([ft.FilledButton("Registrar atención", icon=ft.Icons.SAVE,
                                    on_click=self.seguro(lambda e: self._registrar(False))),
                    ft.TextButton("Limpiar formulario", on_click=self.seguro(lambda e: self._limpiar()))]),
        ], spacing=14, scroll=ft.ScrollMode.AUTO)
        self._mostrar_tratamientos()
        self.panel_vacunas.controls = [ft.Text("Seleccione una mascota para controlar su esquema.", italic=True)]
        return ft.Container(formulario, padding=ft.Padding.only(top=12, right=8))

    def al_mostrar(self, id_turno: int | None = None, **contexto) -> None:
        cargar_opciones(self.mascota, self.opciones_mascotas())
        cargar_opciones(self.veterinario, self.opciones_veterinarios())
        cargar_opciones(self.otra_vacuna, [(v.id, v.nombre) for v in self.servicios.catalogos.listar("vacuna")])
        self._turnos = {str(t["id_turno"]): t for t in self.servicios.turnos.pendientes_de_atencion()}
        if id_turno and str(id_turno) not in self._turnos:  # turno de otro día abierto desde la agenda
            self._turnos |= {str(t["id_turno"]): t for t in self.servicios.turnos.listar(estado=EstadoTurno.RESERVADO)
                             if t["id_turno"] == id_turno}
        cargar_opciones(self.turno, [(clave, f"{fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(t['fecha_hora_inicio']))}"
                                             f" · {t['mascota']} · {t['veterinario']}")
                                     for clave, t in self._turnos.items()])
        if id_turno:
            self.pestanias.selected_index = 0
            self.turno.value = str(id_turno)
            self._cambio_turno(None)
        self._cargar_historial()

    def _cambio_turno(self, e) -> None:
        turno = self._turnos.get(self.turno.value or "")
        if not turno:
            return
        self.mascota.value, self.veterinario.value = str(turno["id_mascota"]), str(turno["id_veterinario"])
        self._cambio_veterinario(None)
        self.clinica.value = str(turno["id_clinica"])
        self.tipo.value = TipoAtencion.CONSULTA.value
        self._cambio_mascota(None)

    def _cambio_veterinario(self, e) -> None:
        id_veterinario = leer_id(self.veterinario)
        veterinario = next((v for v in self.servicios.catalogos.listar("veterinario") if v.id == id_veterinario), None)
        nombres = dict(self.opciones_clinicas())
        cargar_opciones(self.clinica, [(i, nombres[i]) for i in veterinario.ids_clinicas] if veterinario else [])
        if self.clinica.value is None and self.clinica.options:
            self.clinica.value = self.clinica.options[0].key

    def _cambio_mascota(self, e) -> None:
        """Muestra las vacunas obligatorias pendientes de la mascota para aplicarlas en esta atención."""
        self._vacunas_pendientes = []
        id_mascota = leer_id(self.mascota)
        if id_mascota is None:
            self.panel_vacunas.controls = [ft.Text("Seleccione una mascota.", italic=True)]
            return
        dia = (leer_fecha_hora(self.fecha_hora) or fechas.ahora()).date()
        pendientes = self.servicios.atenciones.vacunas_pendientes(id_mascota, dia)
        mascota = self.servicios.mascotas.obtener(id_mascota)
        self.peso.value = numero_editable(mascota.peso_kg)  # último peso registrado, para actualizarlo si cambió
        if not pendientes:
            self.panel_vacunas.controls = [chip("Esquema obligatorio al día", ft.Colors.GREEN_700)]
            return
        controles = [ft.Text(f"{mascota.nombre} tiene {len(pendientes)} vacuna(s) obligatoria(s) pendiente(s). "
                             "Marque las que se aplican en esta atención:", color=ft.Colors.ORANGE_800)]
        for vo in pendientes:
            exigible = vo.fecha_vencimiento(mascota)
            check = ft.Checkbox(label=f"{vo.nombre_vacuna} (exigible desde {fechas.formatear_fecha(exigible)})",
                                value=True, data=vo.id_vacuna, expand=True)
            lote = campo("Lote *", width=160)
            self._vacunas_pendientes.append((check, lote))
            controles.append(ft.Row([check, lote]))
        self.panel_vacunas.controls = controles

    def _agregar_vacuna_extra(self, e) -> None:
        id_vacuna = leer_id(self.otra_vacuna, requerido=True)
        lote = leer_texto(self.lote_extra, requerido=True)
        nombre = next(o.text for o in self.otra_vacuna.options if o.key == str(id_vacuna))
        self._vacunas_extra.append((id_vacuna, nombre, lote))
        self.otra_vacuna.value, self.lote_extra.value = None, ""
        self._mostrar_vacunas_extra()

    def _mostrar_vacunas_extra(self) -> None:
        def quitar(indice):
            return lambda e: (self._vacunas_extra.pop(indice), self._mostrar_vacunas_extra(), self.page.update())
        self.lista_extra.controls = [ft.Chip(label=ft.Text(f"{nombre} · lote {lote}"), on_delete=quitar(i))
                                     for i, (_, nombre, lote) in enumerate(self._vacunas_extra)]

    def _dialogo_tratamiento(self) -> None:
        inicio = (leer_fecha_hora(self.fecha_hora) or fechas.ahora()).date()
        descripcion, medicamento = campo("Descripción *"), campo("Medicamento")
        dosis, frecuencia = campo("Dosis"), campo("Frecuencia")
        desde, hasta = campo_fecha("Inicio *", inicio), campo_fecha("Fin (vacío si es continuo)")

        def agregar(e):
            tratamiento = Tratamiento(descripcion=leer_texto(descripcion) or "", medicamento=leer_texto(medicamento),
                                      dosis=leer_texto(dosis), frecuencia=leer_texto(frecuencia),
                                      fecha_inicio=leer_fecha(desde, True), fecha_fin=leer_fecha(hasta))
            tratamiento.validar()
            self._tratamientos.append(tratamiento)
            self._mostrar_tratamientos()
            self.page.pop_dialog()

        abrir_dialogo(self.page, "Agregar tratamiento",
                      ft.Column([descripcion, fila(medicamento, dosis), frecuencia, fila(desde, hasta)], tight=True,
                                spacing=12),
                      [boton_cancelar(self.page), ft.FilledButton("Agregar", on_click=self.seguro(agregar))])

    def _mostrar_tratamientos(self) -> None:
        def quitar(tratamiento):
            return lambda e: (self._tratamientos.remove(tratamiento), self._mostrar_tratamientos(), self.page.update())
        self.lista_tratamientos.controls = [
            ft.Row([ft.Icon(ft.Icons.MEDICATION, size=18),
                    ft.Text(f"{t.descripcion} · {t.medicamento or ''} {t.dosis or ''} {t.frecuencia or ''} "
                            f"({fechas.formatear_fecha(t.fecha_inicio)} – {fechas.formatear_fecha(t.fecha_fin) or 'continuo'})",
                            expand=True),
                    ft.IconButton(ft.Icons.CLOSE, tooltip="Quitar", on_click=quitar(t))]) for t in self._tratamientos
        ] or [ft.Text("Sin tratamientos indicados.", italic=True, color=ft.Colors.ON_SURFACE_VARIANT)]

    def _cambio_derivar(self, e) -> None:
        self.derivacion.control.visible = self.derivar.value

    def _vacunas_a_aplicar(self) -> list[tuple[int, str]]:
        vacunas = []
        for check, lote in self._vacunas_pendientes:
            if check.value:
                vacunas.append((check.data, leer_texto(lote) or ""))
        return vacunas + [(id_vacuna, lote) for id_vacuna, _, lote in self._vacunas_extra]

    def _registrar(self, confirmado: bool) -> None:
        datos = dict(
            id_mascota=leer_id(self.mascota, True), id_veterinario=leer_id(self.veterinario, True),
            id_clinica=leer_id(self.clinica, True), tipo=TipoAtencion(self.tipo.value),
            fecha_hora=leer_fecha_hora(self.fecha_hora, True), motivo=leer_texto(self.motivo) or "",
            id_turno=int(self.turno.value) if self.turno.value else None, anamnesis=leer_texto(self.anamnesis),
            diagnostico=leer_texto(self.diagnostico), peso_registrado_kg=leer_decimal(self.peso),
            tratamientos=list(self._tratamientos), vacunas=self._vacunas_a_aplicar(),
            derivacion=self.derivacion.solicitud() if self.derivar.value else None)
        try:
            atencion = self.servicios.atenciones.registrar(**datos, confirmar_esquema_incompleto=confirmado)
        except EsquemaVacunasIncompletoError as error:
            confirmar(self.page, "Esquema de vacunación incompleto",
                      f"{error}\n\n¿Registrar la atención de todos modos? Las vacunas quedarán pendientes "
                      "y aparecerán en el reporte de vacunas pendientes.",
                      self.seguro(lambda: self._registrar(True)), "Registrar de todos modos")
            return
        mensaje = "Atención registrada."
        if atencion.ordenes:
            orden = atencion.ordenes[0]
            mensaje += f" Orden {orden.numero} emitida con {len(orden.muestras)} muestra(s) extraída(s)."
        if atencion.vacunas_pendientes:
            mensaje += f" Quedan {len(atencion.vacunas_pendientes)} vacuna(s) pendiente(s)."
        self.notificar.exito(mensaje)
        self._limpiar()
        self.al_mostrar()
        self.page.update()

    def _limpiar(self) -> None:
        for control in (self.turno, self.mascota):
            control.value = None
        for control in (self.motivo, self.anamnesis, self.diagnostico, self.peso):
            control.value = ""
        self.fecha_hora.value = fechas.formatear_fecha_hora(fechas.ahora())
        self.tipo.value = TipoAtencion.CONSULTA.value
        self._tratamientos, self._vacunas_extra, self._vacunas_pendientes = [], [], []
        self.derivar.value, self.derivacion.control.visible = False, False
        self.derivacion.limpiar()
        self._mostrar_tratamientos()
        self._mostrar_vacunas_extra()
        self.panel_vacunas.controls = [ft.Text("Seleccione una mascota para controlar su esquema.", italic=True)]

    # --- Historial ------------------------------------------------------------------------------
    def _construir_historial(self) -> ft.Control:
        recargar = self.seguro(lambda e: self._cargar_historial())
        self.desde = campo_fecha("Desde", date.today() - timedelta(days=30), width=150, on_submit=recargar)
        self.hasta = campo_fecha("Hasta", date.today(), width=150, on_submit=recargar)
        self.filtro_clinica = selector("Clínica", [("", "Todas")] + self.opciones_clinicas(), "", width=280,
                                       on_select=recargar)
        self.filtro_texto = campo("Mascota, responsable o diagnóstico", prefix_icon=ft.Icons.SEARCH, expand=True,
                                  on_change=recargar)
        self.historial = Tabla(["Fecha", "Mascota", "Responsable", "Tipo", "Veterinario", "Clínica", "Diagnóstico",
                                "Órdenes", "Comprobante"], acciones=self._acciones_historial,
                               vacio="No hay atenciones en el período.")
        return ft.Container(ft.Column([
            ft.Row([self.desde, self.hasta, self.filtro_clinica, self.filtro_texto,
                    ft.IconButton(ft.Icons.SEARCH, tooltip="Buscar", on_click=recargar)]),
            self.historial.control], expand=True, spacing=12), padding=ft.Padding.only(top=12))

    def _cargar_historial(self) -> None:
        atenciones = self.servicios.atenciones.listar(leer_fecha(self.desde), leer_fecha(self.hasta),
                                                      int(self.filtro_clinica.value) if self.filtro_clinica.value else None,
                                                      self.filtro_texto.value or "")
        self.historial.cargar([[fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(a["fecha_hora"])),
                                a["mascota"], a["responsable"], chip(a["tipo"]), a["veterinario"], a["clinica"],
                                a["diagnostico"] or "—", a["ordenes"] or "—", a["comprobante"] or "Pendiente"]
                               for a in atenciones], atenciones)

    def _acciones_historial(self, atencion: dict) -> list[ft.Control]:
        acciones = [boton_icono(ft.Icons.VISIBILITY, "Ver detalle", self.seguro(lambda e: self._detalle(atencion))),
                    boton_icono(ft.Icons.BIOTECH, "Emitir nueva orden de derivación",
                                self.seguro(lambda e: self._dialogo_orden(atencion)))]
        if not atencion["comprobante"]:
            acciones.append(boton_icono(ft.Icons.RECEIPT_LONG, "Facturar",
                                        lambda e: self.app.navegar("facturacion", id_atencion=atencion["id_atencion"])))
        return acciones

    def _detalle(self, resumen: dict) -> None:
        atencion = self.servicios.atenciones.obtener(resumen["id_atencion"])
        lineas = [
            ft.Text(f"{resumen['mascota']} ({resumen['especie']}) · Responsable: {resumen['responsable']}"),
            ft.Text(f"{resumen['veterinario']} · {resumen['clinica']} · "
                    f"{fechas.formatear_fecha_hora(atencion.fecha_hora)}"),
            ft.Divider(),
            ft.Text(f"Motivo: {atencion.motivo}"), ft.Text(f"Anamnesis: {atencion.anamnesis or '—'}"),
            ft.Text(f"Diagnóstico: {atencion.diagnostico or '—'}"),
            ft.Text(f"Peso registrado: {formato.numero(atencion.peso_registrado_kg)} kg"),
            ft.Text("Tratamientos", weight=ft.FontWeight.BOLD),
            *([ft.Text(f"• {t.descripcion}: {t.medicamento or ''} {t.dosis or ''} {t.frecuencia or ''}")
               for t in atencion.tratamientos] or [ft.Text("Sin tratamientos.", italic=True)]),
            ft.Text("Vacunas aplicadas", weight=ft.FontWeight.BOLD),
            *([ft.Text(f"• {a.nombre_vacuna} (lote {a.lote})") for a in atencion.aplicaciones]
              or [ft.Text("Ninguna.", italic=True)]),
            ft.Text("Órdenes de derivación", weight=ft.FontWeight.BOLD),
            *([ft.Row([ft.Text(f"• {o['numero']} » {o['laboratorio']}: {o['analisis']}", expand=True), chip(o["estado"])])
               for o in self.servicios.atenciones.ordenes_de(atencion.id)] or [ft.Text("Ninguna.", italic=True)]),
        ]
        abrir_dialogo(self.page, f"Atención del {fechas.formatear_fecha(atencion.fecha_hora.date())}",
                      ft.Column(lineas, scroll=ft.ScrollMode.AUTO, spacing=6, tight=True),
                      [boton_cancelar(self.page, "Cerrar")], ancho=680)

    def _dialogo_orden(self, resumen: dict) -> None:
        formulario = FormularioDerivacion(self)

        def emitir(e):
            orden = self.servicios.atenciones.emitir_orden(resumen["id_atencion"], formulario.solicitud())
            self.page.pop_dialog()
            self.notificar.exito(f"Orden {orden.numero} emitida con {len(orden.muestras)} muestra(s).")
            self._cargar_historial()

        abrir_dialogo(self.page, f"Nueva orden de derivación · {resumen['mascota']}", formulario.control,
                      [boton_cancelar(self.page), ft.FilledButton("Emitir orden", icon=ft.Icons.SEND,
                                                                  on_click=self.seguro(emitir))], ancho=760)
