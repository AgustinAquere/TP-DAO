"""Procesos 4 y 5: empaquetar muestras (remito biológico + precinto sanitario) y registrar la cadena de envío."""
import flet as ft

from app.presentacion.componentes import (Tabla, abrir_dialogo, boton_cancelar, boton_icono, campo, campo_fecha_hora,
                                          campo_numero, cargar_opciones, chip, confirmar, encabezado, fila,
                                          leer_decimal, leer_fecha_hora, leer_id, leer_texto, seccion, selector)
from app.presentacion.vistas.base_vista import Vista
from app.utils import fechas, formato

ESTADOS_REMITO = [("", "Todos"), ("EN_PREPARACION", "En preparación"), ("PRECINTADO", "Precintado"),
                  ("EN_TRANSITO", "En tránsito"), ("RECIBIDO", "Recibido"), ("RECHAZADO", "Rechazado")]


def _rango(m: dict) -> str:
    if m["temp_min_requerida"] is None:
        return "—"
    return f"{m['temp_min_requerida']:g} a {m['temp_max_requerida']:g} °C"


class EnviosVista(Vista):
    def construir(self) -> ft.Control:
        self.pestanias = ft.Tabs(length=2, selected_index=0, expand=True, content=ft.Column([
            ft.TabBar(tabs=[ft.Tab(label="Armar remito", icon=ft.Icons.INVENTORY_2),
                            ft.Tab(label="Remitos y cadena de envío", icon=ft.Icons.LOCAL_SHIPPING)]),
            ft.TabBarView(controls=[self._construir_armado(), self._construir_remitos()], expand=True),
        ], expand=True))
        return ft.Column([encabezado("Empaquetado y envío de muestras",
                                     "Conservadoras isotérmicas, remito biológico, precinto sanitario y tramos de envío"),
                          self.pestanias], expand=True, spacing=10)

    def al_mostrar(self, **contexto) -> None:
        clinicas = self.opciones_clinicas()
        cargar_opciones(self.clinica, clinicas)
        if self.clinica.value is None and clinicas:
            self.clinica.value = str(clinicas[0][0])
        cargar_opciones(self.filtro_clinica, [("", "Todas")] + clinicas)
        self._cargar_pendientes()
        self._cargar_remitos()

    # --- Armado del remito -----------------------------------------------------------------
    def _construir_armado(self) -> ft.Control:
        self.clinica = selector("Clínica de origen", [], width=320,
                                on_select=self.seguro(lambda e: self._cargar_pendientes()))
        self.conservadora = selector("Conservadora isotérmica", [], width=380)
        self.seleccion = ft.Text(color=ft.Colors.ON_SURFACE_VARIANT)
        self.pendientes = Tabla(["Código", "Tipo", "Análisis", "Conservación", ("Viabilidad restante", True), "Orden",
                                 "Prioridad", "Laboratorio", "Mascota"], seleccionable=True,
                                al_seleccionar=lambda dato, marcado: self._actualizar_seleccion(),
                                vacio="No hay muestras extraídas pendientes de empaquetar en la clínica.")
        return ft.Container(ft.Column([
            ft.Row([self.clinica, self.conservadora,
                    ft.FilledButton("Crear remito con las seleccionadas", icon=ft.Icons.INVENTORY,
                                    on_click=self.seguro(self._crear_remito))], wrap=True),
            ft.Text("Marque las muestras a empaquetar. Deben derivarse al mismo laboratorio y la conservadora debe "
                    "mantener una temperatura dentro del rango requerido por cada muestra.", size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT),
            self.seleccion, self.pendientes.control], expand=True, spacing=10), padding=ft.Padding.only(top=12))

    def _cargar_pendientes(self) -> None:
        muestras = self.servicios.derivaciones.muestras_pendientes(leer_id(self.clinica))
        restante = lambda m: "—" if m["horas_restantes"] is None else (
            "Vencida" if m["horas_restantes"] < 0 else f"{formato.numero(m['horas_restantes'])} h")
        self.pendientes.cargar([[m["codigo"], formato.etiqueta(m["tipo"]), m["analisis"], _rango(m), restante(m),
                                 m["orden"], chip(m["prioridad"]), m["laboratorio"], m["mascota"]] for m in muestras],
                               muestras)
        cargar_opciones(self.conservadora, [(c.id, str(c)) for c in self.servicios.derivaciones.conservadoras_disponibles()])
        self._actualizar_seleccion()

    def _actualizar_seleccion(self) -> None:
        cantidad = len(self.pendientes.seleccionados())
        self.seleccion.value = f"{cantidad} muestra(s) seleccionada(s)"

    def _crear_remito(self, e) -> None:
        muestras = self.pendientes.seleccionados()
        remito = self.servicios.derivaciones.armar_remito([m["id_muestra"] for m in muestras],
                                                          leer_id(self.conservadora, True), leer_id(self.clinica, True))
        self.notificar.exito(f"Remito {remito.numero} creado con {len(remito.muestras)} muestra(s). "
                             "Continúe precintándolo en la pestaña de remitos.")
        self._cargar_pendientes()
        self._cargar_remitos()

    # --- Remitos y cadena de custodia -----------------------------------------------------------
    def _construir_remitos(self) -> ft.Control:
        recargar = self.seguro(lambda e: self._cargar_remitos())
        self.filtro_estado = selector("Estado", ESTADOS_REMITO, "", width=220, on_select=recargar)
        self.filtro_clinica = selector("Clínica de origen", [], "", width=300, on_select=recargar)
        self.remitos = Tabla(["Número", "Estado", "Emisión", "Origen", "Destino", "Conservadora", ("Muestras", True),
                              "Precinto", "Tramos", "Último transportista"], acciones=self._acciones,
                             vacio="No hay remitos con los filtros seleccionados.")
        return ft.Container(ft.Column([ft.Row([self.filtro_estado, self.filtro_clinica]), self.remitos.control],
                                      expand=True, spacing=10), padding=ft.Padding.only(top=12))

    def _cargar_remitos(self) -> None:
        remitos = self.servicios.derivaciones.listar_remitos(self.filtro_estado.value or None, None,
                                                             int(self.filtro_clinica.value) if self.filtro_clinica.value else None)
        self.remitos.cargar([[r["numero"], chip(r["estado"]),
                              fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(r["fecha_hora_emision"])),
                              r["clinica"], r["laboratorio"], r["conservadora"], r["cantidad_muestras"],
                              ft.Row([ft.Text(r["precinto"] or "—"), chip(r["estado_precinto"])] if r["precinto"]
                                     else [ft.Text("—")]),
                              r["cantidad_tramos"], r["transportista"] or "—"] for r in remitos], remitos)

    def _acciones(self, remito: dict) -> list[ft.Control]:
        """Las acciones disponibles las decide el estado del remito (patrón State)."""
        operaciones = self.servicios.derivaciones.operaciones_permitidas(remito["estado"])
        acciones = [boton_icono(ft.Icons.VISIBILITY, "Ver detalle y cadena de custodia",
                                self.seguro(lambda e: self._detalle(remito["id_remito"])))]
        disponibles = [
            ("precintar", ft.Icons.LOCK, "Precintar", lambda e: self._dialogo_precintar(remito)),
            ("despachar", ft.Icons.LOCAL_SHIPPING, "Despachar", lambda e: self._dialogo_despachar(remito)),
            ("cerrar_tramo", ft.Icons.WHERE_TO_VOTE, "Registrar llegada del tramo actual",
             lambda e: self._dialogo_cerrar_tramo(remito)),
            ("registrar_tramo", ft.Icons.ALT_ROUTE, "Registrar nuevo tramo (cambio de transportista)",
             lambda e: self._dialogo_nuevo_tramo(remito)),
            ("quitar_muestra", ft.Icons.DELETE_OUTLINE, "Anular remito", lambda e: confirmar(
                self.page, "Anular remito", f"¿Anular el remito {remito['numero']}? Sus muestras vuelven a quedar "
                                            "pendientes de empaquetar.", self.seguro(lambda: self._anular(remito)),
                "Anular", peligroso=True)),
        ]
        acciones += [boton_icono(icono, ayuda, self.seguro(accion)) for operacion, icono, ayuda, accion in disponibles
                     if operacion in operaciones]
        return acciones

    def _despues(self, mensaje: str) -> None:
        self.page.pop_dialog()
        self.notificar.exito(mensaje)
        self._cargar_remitos()
        self.page.update()

    def _anular(self, remito: dict) -> None:
        self.servicios.derivaciones.anular_remito(remito["id_remito"])
        self.notificar.exito(f"Remito {remito['numero']} anulado.")
        self._cargar_remitos()
        self._cargar_pendientes()
        self.page.update()

    def _dialogo_precintar(self, remito: dict) -> None:
        numero = campo("N.º de precinto (vacío = automático)")
        responsable = campo("Responsable del empaquetado *")
        momento = campo_fecha_hora("Fecha y hora de colocación *", fechas.ahora())

        def precintar(e):
            precinto = self.servicios.derivaciones.precintar(remito["id_remito"], leer_texto(responsable, True),
                                                             leer_texto(numero), leer_fecha_hora(momento, True))
            self._despues(f"Remito precintado con el precinto {precinto.numero}. Muestras empaquetadas.")

        abrir_dialogo(self.page, f"Precintar remito {remito['numero']}",
                      ft.Column([ft.Text("Al precintar, todas las muestras pasan al estado «Empaquetada»."),
                                 numero, fila(responsable, momento)], tight=True, spacing=12),
                      [boton_cancelar(self.page), ft.FilledButton("Precintar", icon=ft.Icons.LOCK,
                                                                  on_click=self.seguro(precintar))])

    def _opciones_transportistas(self) -> list[tuple]:
        return [(t.id, f"{t.razon_social} · {t.patente_vehiculo or ''}") for t in self.servicios.catalogos.listar("transportista")]

    def _dialogo_despachar(self, remito: dict) -> None:
        transportista = selector("Transportista *", self._opciones_transportistas())
        entregado = campo("Entregado por *")
        temperatura = campo_numero("Temperatura de salida (°C)")
        salida = campo_fecha_hora("Fecha y hora de salida *", fechas.ahora())
        destino = campo("Destino del tramo", remito["laboratorio"])

        def despachar(e):
            self.servicios.derivaciones.despachar(remito["id_remito"], leer_id(transportista, True),
                                                  leer_texto(entregado, True), leer_decimal(temperatura),
                                                  leer_fecha_hora(salida, True), leer_texto(destino))
            self._despues("Remito despachado: el primer tramo de la cadena de custodia quedó registrado.")

        abrir_dialogo(self.page, f"Despachar remito {remito['numero']}",
                      ft.Column([transportista, fila(entregado, temperatura), fila(salida, destino)], tight=True,
                                spacing=12),
                      [boton_cancelar(self.page), ft.FilledButton("Despachar", icon=ft.Icons.LOCAL_SHIPPING,
                                                                  on_click=self.seguro(despachar))])

    def _dialogo_cerrar_tramo(self, remito: dict) -> None:
        llegada = campo_fecha_hora("Fecha y hora de llegada *", fechas.ahora())
        recibido = campo("Recibido por *")
        temperatura = campo_numero("Temperatura de llegada (°C)")
        observaciones = campo("Observaciones")

        def cerrar(e):
            self.servicios.derivaciones.cerrar_tramo(remito["id_remito"], leer_fecha_hora(llegada, True),
                                                     leer_texto(recibido, True), leer_decimal(temperatura),
                                                     leer_texto(observaciones))
            self._despues("Llegada del tramo registrada.")

        abrir_dialogo(self.page, f"Llegada del tramo actual · {remito['numero']}",
                      ft.Column([fila(llegada, temperatura), recibido, observaciones], tight=True, spacing=12),
                      [boton_cancelar(self.page), ft.FilledButton("Registrar llegada", on_click=self.seguro(cerrar))])

    def _dialogo_nuevo_tramo(self, remito: dict) -> None:
        actual = self.servicios.derivaciones.obtener_remito(remito["id_remito"]).tramo_actual()
        transportista = selector("Transportista *", self._opciones_transportistas())
        origen, destino = campo("Origen *", actual.destino), campo("Destino *", remito["laboratorio"])
        salida = campo_fecha_hora("Fecha y hora de salida *", fechas.ahora())
        entregado = campo("Entregado por *", actual.recibido_por)
        temperatura = campo_numero("Temperatura de salida (°C)")

        def registrar(e):
            self.servicios.derivaciones.registrar_tramo(remito["id_remito"], leer_id(transportista, True),
                                                        leer_texto(origen, True), leer_texto(destino, True),
                                                        leer_fecha_hora(salida, True), leer_texto(entregado, True),
                                                        leer_decimal(temperatura))
            self._despues("Nuevo tramo registrado en la cadena de custodia.")

        abrir_dialogo(self.page, f"Nuevo tramo · {remito['numero']}",
                      ft.Column([transportista, fila(origen, destino), fila(salida, temperatura), entregado],
                                tight=True, spacing=12),
                      [boton_cancelar(self.page), ft.FilledButton("Registrar tramo", on_click=self.seguro(registrar))])

    def _detalle(self, id_remito: int) -> None:
        remito = self.servicios.derivaciones.obtener_remito(id_remito)
        muestras = Tabla(["Código", "Tipo", "Análisis", "Conservación", "Estado"], expandir=False)
        muestras.cargar([[m["codigo"], formato.etiqueta(m["tipo"]), m["analisis"], _rango(m), chip(m["estado"])]
                         for m in self.servicios.derivaciones.muestras_de_remito(id_remito)])
        tramos = Tabla(["N.º", "Transportista", "Origen » destino", "Salida", "Llegada", "T° salida", "T° llegada",
                        "Entregó", "Recibió"], vacio="Todavía no fue despachado.", expandir=False)
        temperatura = lambda t: "—" if t is None else f"{t:g} °C"
        tramos.cargar([[t.nro_orden, t.nombre_transportista, f"{t.origen} » {t.destino}",
                        fechas.formatear_fecha_hora(t.fecha_hora_salida),
                        fechas.formatear_fecha_hora(t.fecha_hora_llegada) or "En curso",
                        temperatura(t.temperatura_salida_c), temperatura(t.temperatura_llegada_c), t.entregado_por,
                        t.recibido_por or "—"] for t in remito.tramos])
        precinto = remito.precinto
        datos = [ft.Row([chip(remito.nombre_estado()), ft.Text(f"{remito.nombre_clinica} » {remito.nombre_laboratorio}"),
                         ft.Text(f"Conservadora {remito.conservadora}")], wrap=True),
                 ft.Text(f"Precinto: {precinto.numero} ({formato.etiqueta(precinto.estado)}), colocado el "
                         f"{fechas.formatear_fecha_hora(precinto.fecha_hora_colocacion)}" if precinto
                         else "Precinto: todavía no se colocó.")]
        if remito.recepcion:
            r = remito.recepcion
            datos.append(ft.Text(f"Recepción: {fechas.formatear_fecha_hora(r.fecha_hora)} · precinto "
                                 f"{formato.etiqueta(r.estado_precinto_verificado).lower()} · "
                                 f"{'aceptado' if r.aceptada else 'RECHAZADO: ' + (r.motivo_rechazo or '')}"))
        if remito.tiempo_transito():
            datos.append(ft.Text(f"Tiempo total de tránsito: "
                                 f"{formato.numero(remito.tiempo_transito().total_seconds() / 3600)} h"))
        contenido = ft.Column([*datos, seccion("Muestras", ft.Icons.SCIENCE, muestras.control),
                               seccion("Cadena de custodia", ft.Icons.ROUTE, tramos.control)],
                              scroll=ft.ScrollMode.AUTO, spacing=12)
        abrir_dialogo(self.page, f"Remito biológico {remito.numero}", contenido,
                      [boton_cancelar(self.page, "Cerrar")], ancho=980, alto=600)
