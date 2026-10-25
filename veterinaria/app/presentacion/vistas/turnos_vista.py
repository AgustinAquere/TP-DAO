"""Agenda médica: turnos por veterinario y día, sin superposiciones."""
from datetime import date, datetime, timedelta

import flet as ft

from app import config
from app.dominio.excepciones import ValidacionError
from app.presentacion.componentes import (Tabla, boton_icono, campo_fecha, cargar_opciones, chip, confirmar,
                                          encabezado, leer_fecha, leer_id, seccion, selector)
from app.presentacion.vistas.base_vista import Vista
from app.utils import fechas


class TurnosVista(Vista):
    def construir(self) -> ft.Control:
        refrescar = self.seguro(lambda e: self._refrescar())
        self.veterinario = selector("Veterinario", [], width=380, on_select=self.seguro(self._cambio_veterinario))
        self.fecha = campo_fecha("Fecha", date.today(), width=150, on_submit=refrescar, on_blur=refrescar)
        self.tabla = Tabla(["Inicio", "Fin", "Mascota", "Responsable", "Teléfono", "Clínica", "Estado"],
                           acciones=self._acciones, vacio="El veterinario no tiene turnos en la fecha.")
        self.resumen = ft.Text(color=ft.Colors.ON_SURFACE_VARIANT)
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
        mover = lambda dias: self.seguro(lambda e: self._mover(dias))
        return ft.Column([
            encabezado("Agenda de turnos", f"Jornada de {config.JORNADA_INICIO:%H:%M} a {config.JORNADA_FIN:%H:%M}"),
            ft.Row([self.veterinario, ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Día anterior", on_click=mover(-1)),
                    self.fecha, ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Día siguiente", on_click=mover(1)),
                    ft.TextButton("Hoy", on_click=self.seguro(lambda e: self._ir_a(date.today()))), self.resumen]),
            ft.Row([ft.Container(formulario, width=360),
                    ft.Container(self.tabla.control, expand=True)], expand=True,
                   vertical_alignment=ft.CrossAxisAlignment.START, spacing=16),
        ], expand=True, spacing=14)

    def al_mostrar(self, **contexto) -> None:
        cargar_opciones(self.veterinario, self.opciones_veterinarios())
        if self.veterinario.value is None and self.veterinario.options:
            self.veterinario.value = self.veterinario.options[0].key
        cargar_opciones(self.mascota, self.opciones_mascotas())
        self._cambio_veterinario(None)

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

    def _ir_a(self, dia: date) -> None:
        self.fecha.value = fechas.formatear_fecha(dia)
        self._refrescar()

    def _mover(self, dias: int) -> None:
        self._ir_a((leer_fecha(self.fecha) or date.today()) + timedelta(days=dias))

    def _refrescar(self) -> None:
        id_veterinario, dia = leer_id(self.veterinario), leer_fecha(self.fecha, requerido=True)
        if id_veterinario is None:
            return
        turnos = self.servicios.turnos.listar(fecha=dia, id_veterinario=id_veterinario)
        self.tabla.cargar([[t["fecha_hora_inicio"][11:16], t["fecha_hora_fin"][11:16], t["mascota"], t["responsable"],
                            t["telefono"], t["clinica"], chip(t["estado"])] for t in turnos], turnos)
        libres = self.servicios.turnos.horarios_disponibles(id_veterinario, dia, leer_id(self.duracion) or 30)
        cargar_opciones(self.horario, [(h.isoformat(), h.strftime("%H:%M")) for h in libres])
        activos = sum(t["estado"] != "CANCELADO" for t in turnos)
        self.resumen.value = f"{activos} turnos activos · {len(libres)} horarios libres"

    def _reservar(self, e) -> None:
        if not self.horario.value:
            raise ValidacionError("Seleccione un horario disponible.")
        turno =self.servicios.turnos.reservar(leer_id(self.veterinario, True), leer_id(self.mascota, True),
                                               leer_id(self.clinica, True), datetime.fromisoformat(self.horario.value),
                                               leer_id(self.duracion) or 30)
        self.notificar.exito(f"Turno reservado para las {turno.fecha_hora_inicio:%H:%M}.")
        self.mascota.value = None
        self._refrescar()

    def _acciones(self, turno: dict) -> list[ft.Control]:
        if turno["estado"] != "RESERVADO":
            return []
        id_turno = turno["id_turno"]
        return [
            boton_icono(ft.Icons.MEDICAL_SERVICES, "Atender (registrar la atención)",
                        lambda e: self.app.navegar("atenciones", id_turno=id_turno)),
            boton_icono(ft.Icons.PERSON_OFF, "Marcar ausente", self.seguro(lambda e: self._cambiar(
                self.servicios.turnos.marcar_ausente, id_turno, "Turno marcado como ausente.")), ft.Colors.ORANGE_800),
            boton_icono(ft.Icons.EVENT_BUSY, "Cancelar turno", self.seguro(lambda e: confirmar(
                self.page, "Cancelar turno", "¿Cancelar el turno? El horario quedará disponible.",
                self.seguro(lambda: self._cambiar(self.servicios.turnos.cancelar, id_turno, "Turno cancelado.")),
                "Cancelar turno", peligroso=True)), ft.Colors.RED_700),
        ]

    def _cambiar(self, operacion, id_turno: int, mensaje: str) -> None:
        operacion(id_turno)
        self.notificar.exito(mensaje)
        self._refrescar()
        self.page.update()
