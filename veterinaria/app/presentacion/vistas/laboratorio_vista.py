"""Procesos 6 y 7: recepción en el laboratorio (verificación del precinto) y carga de resultados."""
import flet as ft

from app.dominio.laboratorio import DetalleResultado
from app.presentacion.componentes import (Tabla, abrir_dialogo, boton_cancelar, boton_icono, campo, campo_fecha_hora,
                                          campo_numero, cargar_opciones, chip, encabezado, fila, leer_decimal,
                                          leer_fecha_hora, leer_id, leer_texto, numero_editable, selector)
from app.presentacion.vistas.base_vista import Vista
from app.utils import fechas, formato


class LaboratorioVista(Vista):
    def construir(self) -> ft.Control:
        self.laboratorio = selector("Laboratorio", [], width=420, on_select=self.seguro(lambda e: self._cargar()))
        self.por_recibir = Tabla(["Remito", "Origen", "Conservadora", ("Muestras", True), "Despachado",
                                  "Último transportista", "Precinto"], acciones=self._acciones_recepcion,
                                 vacio="No hay remitos en tránsito hacia el laboratorio.")
        self.pendientes = Tabla(["Prioridad", "Orden", "Muestra", "Tipo", "Análisis", "Mascota", "Recibida"],
                                acciones=lambda a: [boton_icono(ft.Icons.EDIT_NOTE, "Cargar resultado",
                                                                self.seguro(lambda e: self._dialogo_resultado(a)))],
                                vacio="No hay análisis pendientes de resultado.")
        self.busqueda = campo("Buscar por orden, mascota o análisis", prefix_icon=ft.Icons.SEARCH,
                              on_change=self.seguro(lambda e: self._cargar_resultados()))
        self.resultados = Tabla(["Fecha", "Orden", "Muestra", "Mascota", "Análisis", "Bioquímico", "Fuera de rango"],
                                acciones=lambda r: [boton_icono(ft.Icons.VISIBILITY, "Ver resultado",
                                                                self.seguro(lambda e: self._ver_resultado(r)))],
                                vacio="Todavía no se emitieron resultados.")
        pestania = lambda control: ft.Container(control, padding=ft.Padding.only(top=12))
        return ft.Column([
            encabezado("Laboratorio central", "Recepción de remitos, verificación del precinto y resultados",
                       [self.laboratorio]),
            ft.Tabs(length=3, selected_index=0, expand=True, content=ft.Column([
                ft.TabBar(tabs=[ft.Tab(label="Recepción de remitos", icon=ft.Icons.MOVE_TO_INBOX),
                                ft.Tab(label="Análisis pendientes", icon=ft.Icons.PENDING_ACTIONS),
                                ft.Tab(label="Resultados emitidos", icon=ft.Icons.FACT_CHECK)]),
                ft.TabBarView(expand=True, controls=[
                    pestania(self.por_recibir.control), pestania(self.pendientes.control),
                    pestania(ft.Column([fila(self.busqueda), self.resultados.control], expand=True))]),
            ], expand=True)),
        ], expand=True, spacing=10)

    def al_mostrar(self, **contexto) -> None:
        laboratorios = self.opciones_laboratorios()
        cargar_opciones(self.laboratorio, laboratorios)
        if self.laboratorio.value is None and laboratorios:
            self.laboratorio.value = str(laboratorios[0][0])
        self._cargar()

    def _cargar(self) -> None:
        id_laboratorio = leer_id(self.laboratorio)
        remitos = self.servicios.laboratorio.remitos_por_recibir(id_laboratorio)
        self.por_recibir.cargar([[r["numero"], r["clinica"], r["conservadora"], r["cantidad_muestras"],
                                  fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(r["salida"])),
                                  r["transportista"], r["precinto"]] for r in remitos], remitos)
        analisis = self.servicios.laboratorio.analisis_pendientes(id_laboratorio)
        self.pendientes.cargar([[chip(a["prioridad"]), a["orden"], a["muestra"], formato.etiqueta(a["tipo_muestra"]),
                                 a["analisis"], f"{a['mascota']} ({a['especie']})",
                                 fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(a["recibida"]))]
                                for a in analisis], analisis)
        self._cargar_resultados()

    def _cargar_resultados(self) -> None:
        resultados = self.servicios.laboratorio.resultados(leer_id(self.laboratorio), self.busqueda.value or "")
        self.resultados.cargar([[fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(r["fecha_hora"])), r["orden"],
                                 r["muestra"], r["mascota"], r["analisis"], r["bioquimico"],
                                 chip(f"{r['fuera_de_rango']} parámetro(s)", ft.Colors.RED_700) if r["fuera_de_rango"]
                                 else chip("Normal", ft.Colors.GREEN_700)] for r in resultados], resultados)

    def _opciones_bioquimicos(self) -> list[tuple]:
        id_laboratorio = leer_id(self.laboratorio)
        return [(b.id, f"{b.nombre_completo()} · {b.matricula}") for b in self.servicios.catalogos.listar("bioquimico")
                if b.id_laboratorio == id_laboratorio]

    # --- Recepción ------------------------------------------------------------------------
    def _acciones_recepcion(self, remito: dict) -> list[ft.Control]:
        return [boton_icono(ft.Icons.MOVE_TO_INBOX, "Registrar recepción",
                            self.seguro(lambda e: self._dialogo_recepcion(remito)))]

    def _dialogo_recepcion(self, remito: dict) -> None:
        bioquimicos = self._opciones_bioquimicos()
        bioquimico = selector("Bioquímico que recibe *", bioquimicos, bioquimicos[0][0] if bioquimicos else None)
        momento = campo_fecha_hora("Fecha y hora de recepción *", fechas.ahora())
        precinto = ft.RadioGroup(value="INTACTO", content=ft.Row([
            ft.Radio(value="INTACTO", label="Intacto"), ft.Radio(value="ROTO", label="Roto / violentado")]))
        temperatura = campo_numero("Temperatura de arribo (°C)")
        observacion = campo("Motivo / observación (obligatorio si el precinto está roto)")

        def registrar(e):
            recibido = self.servicios.laboratorio.registrar_recepcion(
                remito["id_remito"], leer_id(bioquimico, True), precinto.value == "INTACTO",
                leer_decimal(temperatura), leer_texto(observacion), leer_fecha_hora(momento, True))
            self.page.pop_dialog()
            aceptadas = [m for m in recibido.muestras if m.nombre_estado() == "RECIBIDA"]
            rechazadas = [m for m in recibido.muestras if m.nombre_estado() == "RECHAZADA"]
            if recibido.nombre_estado() == "RECHAZADO":
                self.notificar.error(f"Remito {recibido.numero} RECHAZADO por precinto roto: "
                                     f"{len(rechazadas)} muestra(s) rechazada(s); no podrán procesarse.")
            elif rechazadas:
                self.notificar.info(f"Remito {recibido.numero} recibido: {len(aceptadas)} muestra(s) aceptada(s) y "
                                    f"{len(rechazadas)} rechazada(s) por temperatura o viabilidad.")
            else:
                self.notificar.exito(f"Remito {recibido.numero} recibido: {len(aceptadas)} muestra(s) aceptada(s).")
            self._cargar()
            self.page.update()

        abrir_dialogo(self.page, f"Recepción del remito {remito['numero']}", ft.Column([
            ft.Text(f"Precinto colocado en origen: {remito['precinto']}. Verifique su estado antes de abrir la "
                    "conservadora: si está roto, ninguna muestra podrá procesarse."),
            fila(bioquimico, momento), ft.Text("Estado del precinto", weight=ft.FontWeight.W_600), precinto,
            temperatura, observacion], tight=True, spacing=12),
            [boton_cancelar(self.page), ft.FilledButton("Registrar recepción", icon=ft.Icons.CHECK,
                                                        on_click=self.seguro(registrar))], ancho=620)

    # --- Resultados -----------------------------------------------------------------------------
    def _dialogo_resultado(self, analisis: dict) -> None:
        bioquimicos = self._opciones_bioquimicos()
        bioquimico = selector("Bioquímico que firma *", bioquimicos, bioquimicos[0][0] if bioquimicos else None)
        momento = campo_fecha_hora("Fecha y hora *", fechas.ahora())
        interpretacion = campo("Interpretación", multiline=True, min_lines=2, max_lines=4)
        observaciones = campo("Observaciones")
        filas = ft.Column(spacing=6)
        renglones: list[tuple] = []

        def agregar(detalle: DetalleResultado | None = None):
            controles = (campo("Parámetro", detalle.parametro if detalle else None, expand=3),
                         campo_numero("Valor", None, expand=2),
                         campo("Unidad", detalle.unidad if detalle else None, expand=2),
                         campo("Ref. mín.", numero_editable(detalle.valor_ref_min) if detalle else None, expand=2),
                         campo("Ref. máx.", numero_editable(detalle.valor_ref_max) if detalle else None, expand=2))
            renglones.append(controles)
            filas.controls.append(ft.Row(list(controles), spacing=8))

        for detalle in self.servicios.laboratorio.plantilla_resultado(analisis["codigo"]):
            agregar(detalle)
        if not renglones:
            agregar()

        def registrar(e):
            detalles = [DetalleResultado(parametro=leer_texto(p) or "", valor=leer_decimal(valor, True),
                                         unidad=leer_texto(u), valor_ref_min=leer_decimal(minimo),
                                         valor_ref_max=leer_decimal(maximo))
                        for p, valor, u, minimo, maximo in renglones if leer_texto(p) or leer_texto(valor)]
            resultado = self.servicios.laboratorio.registrar_resultado(
                analisis["id_analisis_solicitado"], leer_id(bioquimico, True), detalles, leer_texto(interpretacion),
                leer_texto(observaciones), leer_fecha_hora(momento, True))
            self.page.pop_dialog()
            fuera = resultado.valores_fuera_de_rango()
            self.notificar.exito(f"Resultado registrado. {len(fuera)} valor(es) fuera de rango." if fuera
                                 else "Resultado registrado: todos los valores dentro de referencia.")
            self._cargar()
            self.page.update()

        abrir_dialogo(self.page, f"Resultado · {analisis['analisis']} · {analisis['muestra']}", ft.Column([
            ft.Text(f"Paciente: {analisis['mascota']} ({analisis['especie']}) · Orden {analisis['orden']}"),
            fila(bioquimico, momento), ft.Text("Valores informados", weight=ft.FontWeight.W_600), filas,
            ft.TextButton("Agregar parámetro", icon=ft.Icons.ADD, on_click=lambda e: (agregar(), self.page.update())),
            interpretacion, observaciones], scroll=ft.ScrollMode.AUTO, spacing=10),
            [boton_cancelar(self.page), ft.FilledButton("Registrar resultado", icon=ft.Icons.SAVE,
                                                        on_click=self.seguro(registrar))], ancho=820, alto=560)

    def _ver_resultado(self, fila_resultado: dict) -> None:
        resultado = self.servicios.laboratorio.obtener_resultado(fila_resultado["id_resultado"])
        tabla = Tabla(["Parámetro", ("Valor", True), "Unidad", "Referencia", "Estado"], expandir=False)
        tabla.cargar([[d.parametro, ft.Text(f"{d.valor:g}", color=ft.Colors.RED_700 if d.fuera_de_rango() else None,
                                            weight=ft.FontWeight.BOLD if d.fuera_de_rango() else None),
                       d.unidad or "", d.rango_referencia(),
                       chip("Fuera de rango", ft.Colors.RED_700) if d.fuera_de_rango() else chip("Normal", ft.Colors.GREEN_700)]
                      for d in resultado.detalles])
        abrir_dialogo(self.page, f"{fila_resultado['analisis']} · {fila_resultado['mascota']}", ft.Column([
            ft.Text(f"Orden {fila_resultado['orden']} · muestra {fila_resultado['muestra']} · firmado por "
                    f"{fila_resultado['bioquimico']} el {fechas.formatear_fecha_hora(resultado.fecha_hora)}"),
            tabla.control, ft.Text(f"Interpretación: {resultado.interpretacion or '—'}"),
            ft.Text(f"Observaciones: {resultado.observaciones or '—'}")], tight=True, spacing=10),
            [boton_cancelar(self.page, "Cerrar")], ancho=720)
