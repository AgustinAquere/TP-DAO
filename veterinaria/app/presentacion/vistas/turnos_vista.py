"""Agenda médica: el día en tabla, o la semana en un cronograma, sin superposiciones."""
from datetime import date, datetime, timedelta

import flet as ft

from app import config
from app.dominio.excepciones import ValidacionError
from app.presentacion.componentes import (COLOR_PRIMARIO, Tabla, boton_icono, campo_fecha, cargar_opciones, chip,
                                          confirmar, encabezado, leer_fecha, leer_id, seccion, selector)
from app.presentacion.cronograma import cronograma
from app.presentacion.vistas.base_vista import Vista
from app.utils import fechas, formato

DIAS_PANEL = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


class TurnosVista(Vista):
    def construir(self) -> ft.Control:
        refrescar = self.seguro(lambda e: self._refrescar())
        self._turno_abierto: int | None = None
        self._bloques: dict[int, ft.Container] = {}
        self.veterinario = selector("Veterinario", [], width=380, on_select=self.seguro(self._cambio_veterinario))
        self.fecha = campo_fecha("Fecha", date.today(), width=170, al_cambiar=refrescar, on_submit=refrescar,
                                 on_blur=refrescar)
        self.tabla = Tabla(["Inicio", "Fin", "Mascota", "Responsable", "Teléfono", "Clínica", "Estado"],
                           acciones=self._acciones, vacio="El veterinario no tiene turnos en la fecha.")
        self.resumen = ft.Text(color=ft.Colors.ON_SURFACE_VARIANT)
        self.vista = ft.SegmentedButton(
            segments=[
                ft.Segment(value="dia", label="Día (Tabla)", icon=ft.Icons.CALENDAR_VIEW_DAY),
                ft.Segment(value="semana", label="Semana (Cronograma)", icon=ft.Icons.CALENDAR_VIEW_WEEK),
            ],
            selected=["dia"], show_selected_icon=False, on_change=self.seguro(self._cambio_vista),
            style=ft.ButtonStyle(
                bgcolor={ft.ControlState.SELECTED: COLOR_PRIMARIO, ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT},
                color={ft.ControlState.SELECTED: ft.Colors.WHITE, ft.ControlState.DEFAULT: ft.Colors.ON_SURFACE},
                side={ft.ControlState.DEFAULT: ft.BorderSide(style=ft.BorderStyle.NONE)},
                shape=ft.RoundedRectangleBorder(radius=20),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8)))
        ancho = 326
        self.mascota = selector("Mascota *", [], filtrable=True, width=ancho)
        self.clinica = selector("Clínica *", [], width=ancho)
        self.duracion = selector("Duración", [(d, f"{d} minutos") for d in config.DURACIONES_TURNO_MIN], 30,
                                 on_select=refrescar, width=ancho)
        self.horario = selector("Horario disponible *", [], width=ancho)
        formulario = seccion("Reservar turno", ft.Icons.EVENT_AVAILABLE, self.mascota, self.clinica, self.duracion,
                             self.horario,
                             ft.FilledButton("Reservar turno", icon=ft.Icons.CHECK, on_click=self.seguro(self._reservar)),
                             ft.Text("Los horarios ofrecidos ya excluyen los turnos del veterinario: el sistema no "
                                     "permite superposiciones.", size=12, color=ft.Colors.ON_SURFACE_VARIANT))
        self.anterior = ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Día anterior",
                                      on_click=self.seguro(lambda e: self._mover(-1)))
        self.siguiente = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Día siguiente",
                                       on_click=self.seguro(lambda e: self._mover(1)))
        self.grilla = ft.Container(expand=True)
        self.panel = ft.Container(width=300, visible=False, padding=16, border_radius=12,
                                  border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), bgcolor=ft.Colors.SURFACE)
        self.area_dia = ft.Container(self.tabla.control, expand=True)
        self.area_semana = ft.Row([self.grilla, self.panel], expand=True, spacing=12,
                                  vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.zona = ft.Container(self.area_dia, expand=True)
        return ft.Column([
            encabezado("Agenda de turnos", f"Jornada de {config.JORNADA_INICIO:%H:%M} a {config.JORNADA_FIN:%H:%M}"),
            ft.Row([self.veterinario,
                    ft.Container(self.vista, bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                                 border_radius=24, padding=3)],
                   spacing=28, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([
                ft.Container(formulario, width=360),
                ft.Column([
                    ft.Row([self.anterior, self.fecha, self.siguiente,
                            ft.TextButton("Hoy", on_click=self.seguro(lambda e: self._ir_a(date.today()))),
                            self.resumen], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.zona,
                ], expand=True, spacing=8),
            ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START, spacing=16),
        ], expand=True, spacing=14)

    def al_mostrar(self, **contexto) -> None:
        cargar_opciones(self.veterinario, self.opciones_veterinarios())
        if self.veterinario.value is None and self.veterinario.options:
            self.veterinario.value = self.veterinario.options[0].key
        cargar_opciones(self.mascota, self.opciones_mascotas())
        self._cambio_veterinario(None)

    def _es_semana(self) -> bool:
        return "semana" in self.vista.selected

    def _veterinario(self):
        id_veterinario = leer_id(self.veterinario)
        return next((v for v in self.servicios.catalogos.listar("veterinario") if v.id == id_veterinario), None)

    def _cambio_veterinario(self, e) -> None:
        veterinario = self._veterinario()
        clinicas = dict(self.opciones_clinicas())
        cargar_opciones(self.clinica, [(i, clinicas[i]) for i in veterinario.ids_clinicas] if veterinario else [])
        if self.clinica.value is None and self.clinica.options:
            self.clinica.value = self.clinica.options[0].key
        self._refrescar()

    def _cambio_vista(self, e) -> None:
        self._aplicar_modo()
        self._refrescar()

    def _aplicar_modo(self) -> None:
        semana = self._es_semana()
        self.zona.content = self.area_semana if semana else self.area_dia
        self.anterior.tooltip = "Semana anterior" if semana else "Día anterior"
        self.siguiente.tooltip = "Semana siguiente" if semana else "Día siguiente"
        if not semana:
            self.panel.visible = False

    def _ir_a(self, dia: date) -> None:
        self.fecha.value = fechas.formatear_fecha(dia)
        self._refrescar()

    def _mover(self, dias: int) -> None:
        self._ir_a((leer_fecha(self.fecha) or date.today()) + timedelta(days=dias * (7 if self._es_semana() else 1)))

    def _refrescar(self) -> None:
        id_veterinario, dia = leer_id(self.veterinario), leer_fecha(self.fecha, requerido=True)
        if id_veterinario is None:
            return
        duracion = leer_id(self.duracion) or 30
        if self._es_semana():
            lunes = dia - timedelta(days=dia.weekday())
            domingo = lunes + timedelta(days=6)
            turnos = self.servicios.turnos.listar(id_veterinario=id_veterinario, desde=lunes, hasta=domingo)
            huecos = {lunes + timedelta(days=i): self.servicios.turnos.horarios_disponibles(
                id_veterinario, lunes + timedelta(days=i), duracion) for i in range(7)}
            cargar_opciones(self.horario, [(h.isoformat(), h.strftime("%H:%M")) for h in huecos[dia]])
            self._bloques = {}
            self.grilla.content = cronograma(
                lunes, turnos, huecos, dia, self.horario.value, self._turno_abierto, self._bloques,
                self.seguro(lambda d: self._ir_a(d)), self.seguro(self._elegir_hueco), self.seguro(self._abrir_turno))
            activos = sum(t["estado"] != "CANCELADO" for t in turnos)
            self.resumen.value = (f"Semana del {fechas.formatear_fecha(lunes)} al {fechas.formatear_fecha(domingo)}"
                                  f" · {activos} turnos activos")
            self._restaurar_panel(turnos)
        else:
            turnos = self.servicios.turnos.listar(fecha=dia, id_veterinario=id_veterinario)
            self.tabla.cargar([[t["fecha_hora_inicio"][11:16], t["fecha_hora_fin"][11:16], t["mascota"],
                                t["responsable"], t["telefono"], t["clinica"], chip(t["estado"])] for t in turnos],
                              turnos)
            libres = self.servicios.turnos.horarios_disponibles(id_veterinario, dia, duracion)
            cargar_opciones(self.horario, [(h.isoformat(), h.strftime("%H:%M")) for h in libres])
            activos = sum(t["estado"] != "CANCELADO" for t in turnos)
            self.resumen.value = f"{activos} turnos activos · {len(libres)} horarios libres"

    def _elegir_hueco(self, inicio: datetime) -> None:
        self._turno_abierto = None
        self.fecha.value = fechas.formatear_fecha(inicio.date())
        self.horario.value = inicio.isoformat()
        self._refrescar()

    def _reservar(self, e) -> None:
        if not self.horario.value:
            raise ValidacionError("Seleccione un horario disponible.")
        turno = self.servicios.turnos.reservar(leer_id(self.veterinario, True), leer_id(self.mascota, True),
                                                leer_id(self.clinica, True), datetime.fromisoformat(self.horario.value),
                                                leer_id(self.duracion) or 30)
        self.notificar.exito(f"Turno reservado para las {turno.fecha_hora_inicio:%H:%M}.")
        self.mascota.value = None
        self._refrescar()

    def _acciones(self, turno: dict) -> list[ft.Control]:
        id_turno, estado = turno["id_turno"], turno["estado"]
        if estado == "RESERVADO":
            return [
                boton_icono(ft.Icons.MEDICAL_SERVICES, "Atender (registrar la atención)",
                            lambda e: self.app.navegar("atenciones", id_turno=id_turno)),
                boton_icono(ft.Icons.PERSON_OFF, "Marcar ausente",
                            self.seguro(lambda e: self._confirmar_ausencia(id_turno)), ft.Colors.ORANGE_800),
                boton_icono(ft.Icons.EVENT_BUSY, "Cancelar turno",
                            self.seguro(lambda e: self._confirmar_cancelacion(id_turno)), ft.Colors.RED_700),
            ]
        if estado == "AUSENTE":
            return [boton_icono(ft.Icons.UNDO, "Deshacer ausencia",
                                self.seguro(lambda e: self._confirmar_reactivacion(id_turno, cancelado=False)),
                                ft.Colors.GREEN_800)]
        if estado == "CANCELADO":
            return [boton_icono(ft.Icons.EVENT_AVAILABLE, "Volver a reservar",
                                self.seguro(lambda e: self._confirmar_reactivacion(id_turno, cancelado=True)),
                                ft.Colors.GREEN_800)]
        return []

    def _abrir_turno(self, turno: dict) -> None:
        self._turno_abierto = turno["id_turno"]
        for id_turno, bloque in self._bloques.items():
            bloque.border = ft.Border.all(2 if id_turno == turno["id_turno"] else 1,
                                           bloque.data if id_turno == turno["id_turno"]
                                           else ft.Colors.with_opacity(0.35, bloque.data))
        self._pintar_panel(turno)

    def _restaurar_panel(self, turnos: list[dict]) -> None:
        turno = next((t for t in turnos if t["id_turno"] == self._turno_abierto), None)
        if turno:
            self._pintar_panel(turno)
        else:
            self._cerrar_panel()

    def _cerrar_panel(self) -> None:
        self._turno_abierto = None
        for bloque in self._bloques.values():
            bloque.border = ft.Border.all(1, ft.Colors.with_opacity(0.35, bloque.data))
        self.panel.visible = False
        self.panel.content = None

    def _pintar_panel(self, turno: dict) -> None:
        inicio = fechas.fecha_hora_desde_sql(turno["fecha_hora_inicio"])
        hora = f"{DIAS_PANEL[inicio.weekday()]} {inicio:%d/%m} · {inicio:%H:%M}–{turno['fecha_hora_fin'][11:16]}"
        acciones = self._acciones_panel(turno)
        self.panel.content = ft.Column([
            ft.Row([ft.Text("Turno", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.CLOSE, tooltip="Cerrar", icon_size=18,
                                  on_click=self.seguro(lambda e: self._cerrar_panel()))]),
            ft.Text(turno["mascota"], size=20, weight=ft.FontWeight.W_600),
            chip(turno["estado"]),
            _dato("Horario", hora),
            _dato("Responsable", turno["responsable"]),
            _dato("Teléfono", turno["telefono"]),
            _dato("Clínica", turno["clinica"]),
            ft.Divider(height=8),
            *acciones,
        ], spacing=10, scroll=ft.ScrollMode.AUTO)
        self.panel.visible = True

    def _acciones_panel(self, turno: dict) -> list[ft.Control]:
        id_turno, estado = turno["id_turno"], turno["estado"]
        if estado == "RESERVADO":
            return [
                ft.FilledButton("Atender", icon=ft.Icons.MEDICAL_SERVICES,
                                on_click=lambda e: self.app.navegar("atenciones", id_turno=id_turno)),
                ft.OutlinedButton("Marcar ausente", icon=ft.Icons.PERSON_OFF,
                                  style=ft.ButtonStyle(color=ft.Colors.ORANGE_800,
                                                       side=ft.BorderSide(1, ft.Colors.ORANGE_800)),
                                  on_click=self.seguro(lambda e: self._confirmar_ausencia(id_turno))),
                ft.TextButton("Cancelar turno", icon=ft.Icons.EVENT_BUSY, style=ft.ButtonStyle(color=ft.Colors.RED_700),
                              on_click=self.seguro(lambda e: self._confirmar_cancelacion(id_turno))),
            ]
        if estado == "AUSENTE":
            return [ft.OutlinedButton("Deshacer ausencia", icon=ft.Icons.UNDO,
                                      on_click=self.seguro(lambda e: self._confirmar_reactivacion(id_turno, False)))]
        if estado == "CANCELADO":
            return [ft.OutlinedButton("Volver a reservar", icon=ft.Icons.EVENT_AVAILABLE,
                                      on_click=self.seguro(lambda e: self._confirmar_reactivacion(id_turno, True)))]
        return [ft.Text(f"El turno está {formato.etiqueta(estado).lower()}.",
                        size=13, color=ft.Colors.ON_SURFACE_VARIANT)]

    def _confirmar_ausencia(self, id_turno: int) -> None:
        confirmar(self.page, "Marcar ausente",
                  "¿Marcar el turno como ausente? El horario sigue ocupado y la ausencia se puede deshacer.",
                  self.seguro(lambda: self._cambiar(self.servicios.turnos.marcar_ausente, id_turno,
                                                    "Turno marcado como ausente.")),
                  "Marcar ausente")

    def _confirmar_cancelacion(self, id_turno: int) -> None:
        confirmar(self.page, "Cancelar turno", "¿Cancelar el turno? El horario quedará disponible.",
                  self.seguro(lambda: self._cambiar(self.servicios.turnos.cancelar, id_turno, "Turno cancelado.")),
                  "Cancelar turno", peligroso=True)

    def _confirmar_reactivacion(self, id_turno: int, cancelado: bool) -> None:
        if cancelado:
            titulo, mensaje, boton = ("Volver a reservar",
                                      "¿Volver a reservar el turno? Solo es posible si el horario sigue libre.",
                                      "Reservar de nuevo")
        else:
            titulo, mensaje, boton = ("Deshacer ausencia",
                                      "¿Deshacer la ausencia y dejar el turno reservado?",
                                      "Deshacer ausencia")
        confirmar(self.page, titulo, mensaje,
                  self.seguro(lambda: self._cambiar(self.servicios.turnos.reactivar, id_turno,
                                                    "El turno volvió a estar reservado.")),
                  boton)

    def _cambiar(self, operacion, id_turno: int, mensaje: str) -> None:
        operacion(id_turno)
        self.notificar.exito(mensaje)
        self._refrescar()
        self.page.update()


def _dato(titulo: str, valor: str | None) -> ft.Column:
    return ft.Column([ft.Text(titulo, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                      ft.Text(valor or "—", size=14)], spacing=0)
