"""Proceso 2: administrar mascotas y sus historias clínicas."""
import flet as ft

from app.dominio.enums import Sexo
from app.presentacion.componentes import (COLOR_PRIMARIO, Tabla, abrir_dialogo, boton_cancelar, boton_icono, campo,
                                          campo_fecha, campo_numero, chip, confirmar, encabezado, fila, leer_decimal,
                                          leer_fecha, leer_id, leer_texto, selector)
from app.presentacion.vistas.base_vista import Vista
from app.utils import fechas, formato

SEXOS = [(Sexo.MACHO.value, "Macho"), (Sexo.HEMBRA.value, "Hembra")]


class MascotasVista(Vista):
    def construir(self) -> ft.Control:
        self.busqueda = campo("Buscar por nombre, responsable, DNI o microchip", prefix_icon=ft.Icons.SEARCH,
                              expand=True, on_change=self.seguro(lambda e: self.al_mostrar()))
        self.filtro_cliente = selector("Responsable", [], width=360, filtrable=True,
                                       on_select=self.seguro(lambda e: self.al_mostrar()))
        self.tabla = Tabla(["Nombre", "Especie", "Raza", "Sexo", "Edad", ("Peso (kg)", True), "Responsable",
                            "Historia clínica"], acciones=self._acciones, vacio="No se encontraron mascotas.")
        return ft.Column([
            encabezado("Mascotas", "Cada mascota tiene un responsable y una historia clínica",
                       [ft.FilledButton("Nueva mascota", icon=ft.Icons.ADD,
                                        on_click=self.seguro(lambda e: self._formulario(None)))]),
            ft.Row([self.busqueda, self.filtro_cliente,
                    ft.IconButton(ft.Icons.FILTER_ALT_OFF, tooltip="Quitar filtros",
                                  on_click=self.seguro(lambda e: self._limpiar_filtros()))]),
            self.tabla.control,
        ], expand=True, spacing=14)

    def _opciones_clientes(self) -> list[tuple]:
        return [(c.id, f"{c.nombre_completo()} · DNI {c.dni}") for c in self.servicios.clientes.listar_activos()]

    def _limpiar_filtros(self) -> None:
        self.busqueda.value, self.filtro_cliente.value = "", None
        self.al_mostrar()

    def al_mostrar(self, id_cliente: int | None = None, **contexto) -> None:
        self.filtro_cliente.options = [ft.DropdownOption(key=str(k), text=t) for k, t in self._opciones_clientes()]
        if id_cliente:
            self.busqueda.value, self.filtro_cliente.value = "", str(id_cliente)
        mascotas = self.servicios.mascotas.listar(self.busqueda.value or "", leer_id(self.filtro_cliente))
        nacimiento = lambda m: fechas.fecha_desde_sql(m["fecha_nacimiento"])
        self.tabla.cargar([[m["nombre"], m["especie"], m["raza"], "Macho" if m["sexo"] == "M" else "Hembra",
                            fechas.edad_legible(nacimiento(m)), formato.numero(m["peso_kg"]), m["responsable"],
                            m["numero_historia"]] for m in mascotas], mascotas)

    def _acciones(self, mascota: dict) -> list[ft.Control]:
        return [
            boton_icono(ft.Icons.FOLDER_SHARED, "Historia clínica",
                        self.seguro(lambda e: self._historia(mascota["id_mascota"]))),
            boton_icono(ft.Icons.EDIT, "Modificar", self.seguro(lambda e: self._formulario(mascota["id_mascota"]))),
            boton_icono(ft.Icons.DELETE_OUTLINE, "Eliminar", self.seguro(lambda e: confirmar(
                self.page, "Eliminar mascota", f"¿Eliminar a {mascota['nombre']}? Solo es posible si no tiene "
                                               "atenciones ni turnos registrados.",
                self.seguro(lambda: self._eliminar(mascota["id_mascota"])), "Eliminar", peligroso=True)),
                ft.Colors.RED_700),
        ]

    def _eliminar(self, id_mascota: int) -> None:
        self.servicios.mascotas.eliminar(id_mascota)
        self.notificar.exito("Mascota eliminada.")
        self.al_mostrar()
        self.page.update()

    # --- Alta y modificación -------------------------------------------------------------
    def _formulario(self, id_mascota: int | None) -> None:
        mascota = self.servicios.mascotas.obtener(id_mascota) if id_mascota else None
        valor = lambda atributo: getattr(mascota, atributo) if mascota else None
        responsable = selector("Responsable *", self._opciones_clientes(),
                               valor("id_cliente") or leer_id(self.filtro_cliente), filtrable=True)
        especie = selector("Especie *", [(e.id, e.nombre) for e in self.servicios.mascotas.especies()],
                           valor("id_especie"))
        nombre, raza = campo("Nombre *", valor("nombre")), campo("Raza", valor("raza"))
        sexo = selector("Sexo", SEXOS, getattr(valor("sexo"), "value", None))
        nacimiento = campo_fecha("Fecha de nacimiento *", valor("fecha_nacimiento"))
        peso = campo_numero("Peso (kg)", valor("peso_kg"))
        microchip = campo("Microchip", valor("microchip"))

        def guardar(e):
            datos = dict(id_especie=leer_id(especie), nombre=leer_texto(nombre) or "", raza=leer_texto(raza),
                         sexo=Sexo(sexo.value) if sexo.value else None, fecha_nacimiento=leer_fecha(nacimiento),
                         peso_kg=leer_decimal(peso), microchip=leer_texto(microchip))
            if mascota:
                mascota.id_cliente = leer_id(responsable)
                for clave, dato in datos.items():
                    setattr(mascota, clave, dato)
                self.servicios.mascotas.modificar(mascota)
            else:
                self.servicios.mascotas.alta(leer_id(responsable), **datos)
            self.page.pop_dialog()
            self.notificar.exito("Mascota guardada." if mascota else "Mascota registrada y historia clínica abierta.")
            self.al_mostrar()

        abrir_dialogo(self.page, "Modificar mascota" if mascota else "Nueva mascota",
                      ft.Column([responsable, fila(nombre, especie), fila(raza, sexo), fila(nacimiento, peso),
                                 microchip], tight=True, spacing=12),
                      [boton_cancelar(self.page), ft.FilledButton("Guardar", icon=ft.Icons.SAVE,
                                                                  on_click=self.seguro(guardar))], ancho=600)

    # --- Historia clínica --------------------------------------------------------------------
    def _historia(self, id_mascota: int) -> None:
        mascota = self.servicios.mascotas.obtener(id_mascota)
        historia = self.servicios.mascotas.historia_clinica(id_mascota)
        resumen = next(m for m in self.servicios.mascotas.listar() if m["id_mascota"] == id_mascota)
        pendientes = self.servicios.mascotas.vacunas_pendientes(id_mascota)
        alergias = campo("Alergias", historia.alergias, multiline=True, min_lines=1, max_lines=3)
        observaciones = campo("Observaciones generales", historia.observaciones_generales, multiline=True,
                              min_lines=1, max_lines=3)

        def guardar(e):
            self.servicios.mascotas.actualizar_historia(id_mascota, leer_texto(observaciones), leer_texto(alergias))
            self.notificar.exito("Historia clínica actualizada.")

        datos = ft.Row([
            _dato("Historia clínica", f"{historia.numero} (desde {fechas.formatear_fecha(historia.fecha_apertura)})"),
            _dato("Responsable", f"{resumen['responsable']} · {resumen['telefono_responsable'] or 's/tel.'}"),
            _dato("Paciente", f"{mascota.especie.nombre} · {mascota.raza or 'sin raza'} · {mascota.edad_legible()}"),
            _dato("Peso", f"{formato.numero(mascota.peso_kg)} kg"),
        ], wrap=True, spacing=28)
        vacunas = ft.Row([chip(f"Pendiente: {p['vacuna']}", ft.Colors.ORANGE_800) for p in pendientes]
                         or [chip("Esquema obligatorio al día", ft.Colors.GREEN_700)], wrap=True)
        aplicadas = ", ".join(f"{a.nombre_vacuna} ({fechas.formatear_fecha(a.fecha)})" for a in mascota.aplicaciones)
        atenciones = [_tarjeta_atencion(a) for a in historia] or [ft.Text("Sin atenciones registradas.", italic=True)]
        contenido = ft.Column([
            datos, ft.Divider(),
            ft.Text("Esquema de vacunación", weight=ft.FontWeight.BOLD), vacunas,
            ft.Text(f"Aplicadas: {aplicadas or 'ninguna registrada'}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            fila(alergias, observaciones), ft.Divider(),
            ft.Text(f"Atenciones ({len(historia)})", weight=ft.FontWeight.BOLD), *atenciones,
        ], scroll=ft.ScrollMode.AUTO, spacing=10)
        abrir_dialogo(self.page, f"Historia clínica de {mascota.nombre}", contenido,
                      [ft.TextButton("Guardar observaciones", icon=ft.Icons.SAVE, on_click=self.seguro(guardar)),
                       boton_cancelar(self.page, "Cerrar")], ancho=900, alto=620)


def _dato(titulo: str, valor: str) -> ft.Column:
    return ft.Column([ft.Text(titulo, size=11, color=ft.Colors.ON_SURFACE_VARIANT), ft.Text(valor, size=14)], spacing=0)


def _tarjeta_atencion(atencion) -> ft.ExpansionTile:
    detalle = [ft.Text(f"Anamnesis: {atencion.anamnesis or '—'}", size=13)]
    detalle += [ft.Text(f"• Tratamiento: {t.descripcion} — {t.medicamento or ''} {t.dosis or ''} {t.frecuencia or ''} "
                        f"({fechas.formatear_fecha(t.fecha_inicio)} al {fechas.formatear_fecha(t.fecha_fin) or 'continúa'})",
                        size=13) for t in atencion.tratamientos]
    detalle += [ft.Text(f"• Vacuna: {a.nombre_vacuna}, lote {a.lote}"
                        + (f", próxima dosis {fechas.formatear_fecha(a.fecha_proxima_dosis)}" if a.fecha_proxima_dosis
                           else ""), size=13) for a in atencion.aplicaciones]
    detalle += [ft.Row([ft.Text(f"• Orden {o.numero}: {', '.join(a.tipo_analisis.nombre for a in o.analisis)}",
                                size=13), chip(o.estado.value)]) for o in atencion.ordenes]
    return ft.ExpansionTile(
        title=ft.Text(f"{fechas.formatear_fecha_hora(atencion.fecha_hora)} · {formato.etiqueta(atencion.tipo)} · "
                      f"{atencion.motivo}", size=14, weight=ft.FontWeight.W_600),
        subtitle=ft.Text(f"Diagnóstico: {atencion.diagnostico or '—'}", size=12),
        leading=ft.Icon(ft.Icons.MEDICAL_SERVICES, color=COLOR_PRIMARIO),
        controls=[ft.Container(ft.Column(detalle, spacing=4), padding=ft.Padding.only(left=16, bottom=10))])
