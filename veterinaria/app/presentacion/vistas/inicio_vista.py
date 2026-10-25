"""Tablero de inicio: indicadores del día y estado del circuito de muestras."""
from datetime import date

import flet as ft

from app.presentacion.componentes import Tabla, chip, encabezado, seccion, tarjeta_indicador
from app.presentacion.vistas.base_vista import Vista
from app.utils import fechas, formato


class InicioVista(Vista):
    def construir(self) -> ft.Control:
        self.indicadores = ft.ResponsiveRow(spacing=12, run_spacing=12)
        self.turnos = Tabla(["Hora", "Mascota", "Responsable", "Veterinario", "Clínica", "Estado"],
                            vacio="No hay turnos para hoy.")
        self.remitos = Tabla(["Remito", "Estado", "Origen", "Destino", "Muestras", "Transportista"],
                             vacio="No hay envíos en curso.")
        return ft.Column([
            encabezado("Panel general", fechas.formatear_fecha(date.today()),
                       [ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar", on_click=self.seguro(lambda e: self.al_mostrar()))]),
            self.indicadores,
            ft.ResponsiveRow([
                ft.Container(seccion("Turnos de hoy", ft.Icons.CALENDAR_TODAY, ft.Container(self.turnos.control, height=300)),
                             col={"md": 12, "xl": 6}),
                ft.Container(seccion("Envíos de muestras en curso", ft.Icons.LOCAL_SHIPPING,
                                     ft.Container(self.remitos.control, height=300)), col={"md": 12, "xl": 6}),
            ], spacing=12, run_spacing=12),
        ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    def al_mostrar(self, **contexto) -> None:
        datos = self.servicios.reportes.tablero()
        ir = lambda clave: (lambda e: self.app.navegar(clave))
        tarjetas = [
            ("Clientes activos", formato.numero(datos["clientes"], 0), ft.Icons.PEOPLE, ft.Colors.TEAL_700, "clientes"),
            ("Mascotas registradas", formato.numero(datos["mascotas"], 0), ft.Icons.PETS, ft.Colors.BROWN_400, "mascotas"),
            ("Turnos pendientes hoy", formato.numero(datos["turnos_hoy"], 0), ft.Icons.EVENT, ft.Colors.BLUE_700, "turnos"),
            ("Atenciones del mes", formato.numero(datos["atenciones_mes"], 0), ft.Icons.MEDICAL_SERVICES,
             ft.Colors.INDIGO_500, "atenciones"),
            ("Vacunas obligatorias pendientes", formato.numero(datos["vacunas_pendientes"], 0), ft.Icons.VACCINES,
             ft.Colors.ORANGE_800, "reportes"),
            ("Muestras por empaquetar", formato.numero(datos["muestras_por_empaquetar"], 0), ft.Icons.INVENTORY_2,
             ft.Colors.BLUE_GREY_600, "envios"),
            ("Remitos en tránsito", formato.numero(datos["remitos_en_transito"], 0), ft.Icons.LOCAL_SHIPPING,
             ft.Colors.AMBER_800, "laboratorio"),
            ("Análisis pendientes de resultado", formato.numero(datos["analisis_pendientes"], 0), ft.Icons.BIOTECH,
             ft.Colors.PURPLE_500, "laboratorio"),
            ("Atenciones sin facturar", formato.numero(datos["atenciones_sin_facturar"], 0), ft.Icons.RECEIPT_LONG,
             ft.Colors.RED_400, "facturacion"),
            ("Facturado en el mes", formato.moneda(datos["facturado_mes"]), ft.Icons.PAYMENTS, ft.Colors.GREEN_700,
             "facturacion"),
        ]
        self.indicadores.controls = [
            ft.Container(tarjeta_indicador(titulo, valor, icono, color, ir(destino)), col={"sm": 6, "md": 4, "xl": 2.4})
            for titulo, valor, icono, color, destino in tarjetas]
        turnos = self.servicios.turnos.listar(fecha=date.today())
        self.turnos.cargar([[t["fecha_hora_inicio"][11:16], t["mascota"], t["responsable"], t["veterinario"],
                             t["clinica"], chip(t["estado"])] for t in turnos])
        remitos = [r for r in self.servicios.derivaciones.listar_remitos() if r["estado"] not in ("RECIBIDO", "RECHAZADO")]
        self.remitos.cargar([[r["numero"], chip(r["estado"]), r["clinica"], r["laboratorio"], r["cantidad_muestras"],
                              r["transportista"] or "—"] for r in remitos])
