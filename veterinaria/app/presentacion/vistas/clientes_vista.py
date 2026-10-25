"""Proceso 1: administrar clientes."""
import flet as ft

from app.presentacion.componentes import (Tabla, abrir_dialogo, boton_cancelar, boton_icono, campo, chip, confirmar,
                                          encabezado, fila, leer_texto)
from app.presentacion.vistas.base_vista import Vista


class ClientesVista(Vista):
    def construir(self) -> ft.Control:
        self.busqueda = campo("Buscar por DNI, nombre o apellido", prefix_icon=ft.Icons.SEARCH, expand=True,
                              on_change=self.seguro(lambda e: self.al_mostrar()))
        self.inactivos = ft.Checkbox(label="Incluir clientes dados de baja",
                                     on_change=self.seguro(lambda e: self.al_mostrar()))
        self.tabla = Tabla(["DNI", "Apellido y nombre", "Teléfono", "Email", "Dirección", ("Mascotas", True), "Estado"],
                           acciones=self._acciones, vacio="No se encontraron clientes.")
        return ft.Column([
            encabezado("Clientes", "Responsables de las mascotas atendidas en la red",
                       [ft.FilledButton("Nuevo cliente", icon=ft.Icons.PERSON_ADD,
                                        on_click=self.seguro(lambda e: self._formulario(None)))]),
            ft.Row([self.busqueda, self.inactivos]),
            self.tabla.control,
        ], expand=True, spacing=14)

    def al_mostrar(self, **contexto) -> None:
        clientes = self.servicios.clientes.buscar(self.busqueda.value or "", self.inactivos.value)
        self.tabla.cargar([[c["dni"], f"{c['apellido']}, {c['nombre']}", c["telefono"], c["email"], c["direccion"],
                            c["cantidad_mascotas"], chip("ACTIVO" if c["activo"] else "BAJA")] for c in clientes], clientes)

    def _acciones(self, cliente: dict) -> list[ft.Control]:
        acciones = [
            boton_icono(ft.Icons.EDIT, "Modificar", self.seguro(lambda e: self._formulario(cliente["id_cliente"]))),
            boton_icono(ft.Icons.PETS, "Ver mascotas",
                        lambda e: self.app.navegar("mascotas", id_cliente=cliente["id_cliente"])),
        ]
        if cliente["activo"]:
            acciones.append(boton_icono(ft.Icons.PERSON_OFF, "Dar de baja", self.seguro(lambda e: confirmar(
                self.page, "Dar de baja", f"¿Dar de baja a {cliente['apellido']}, {cliente['nombre']}? "
                                          "Seguirá figurando como responsable de sus mascotas.",
                self.seguro(lambda: self._baja(cliente["id_cliente"])), "Dar de baja", peligroso=True)),
                ft.Colors.RED_700))
        else:
            acciones.append(boton_icono(ft.Icons.PERSON, "Reactivar",
                                        self.seguro(lambda e: self._reactivar(cliente["id_cliente"]))))
        return acciones

    def _baja(self, id_cliente: int) -> None:
        self.servicios.clientes.baja(id_cliente)
        self.notificar.exito("Cliente dado de baja.")
        self.al_mostrar()
        self.page.update()

    def _reactivar(self, id_cliente: int) -> None:
        self.servicios.clientes.reactivar(id_cliente)
        self.notificar.exito("Cliente reactivado.")
        self.al_mostrar()

    def _formulario(self, id_cliente: int | None) -> None:
        cliente = self.servicios.clientes.obtener(id_cliente) if id_cliente else None
        valor = lambda atributo: getattr(cliente, atributo) if cliente else None
        campos = {
            "dni": campo("DNI *", valor("dni"), max_length=8, input_filter=ft.NumbersOnlyInputFilter()),
            "nombre": campo("Nombre *", valor("nombre")),
            "apellido": campo("Apellido *", valor("apellido")),
            "telefono": campo("Teléfono", valor("telefono")),
            "email": campo("Email", valor("email")),
            "direccion": campo("Dirección", valor("direccion")),
        }

        def guardar(e):
            obligatorios = ("dni", "nombre", "apellido")  # vacíos llegan como "" para que el dominio los valide
            datos = {clave: leer_texto(control) or ("" if clave in obligatorios else None)
                     for clave, control in campos.items()}
            if cliente:
                for clave, texto in datos.items():
                    setattr(cliente, clave, texto)
                self.servicios.clientes.modificar(cliente)
            else:
                self.servicios.clientes.alta(**datos)
            self.page.pop_dialog()
            self.notificar.exito("Cliente guardado.")
            self.al_mostrar()

        abrir_dialogo(self.page, "Modificar cliente" if cliente else "Nuevo cliente",
                      ft.Column([fila(campos["dni"], campos["telefono"]), fila(campos["nombre"], campos["apellido"]),
                                 campos["email"], campos["direccion"]], tight=True, spacing=12),
                      [boton_cancelar(self.page), ft.FilledButton("Guardar", icon=ft.Icons.SAVE,
                                                                  on_click=self.seguro(guardar))])
