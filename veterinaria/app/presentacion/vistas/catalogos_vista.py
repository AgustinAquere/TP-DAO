"""ABM genérico de las tablas de referencia, definido de forma declarativa por catálogo."""
import dataclasses
from collections.abc import Callable
from dataclasses import dataclass, field

import flet as ft

from app.dominio.derivacion import TipoAnalisis
from app.dominio.enums import TipoMuestra
from app.dominio.envio import Conservadora
from app.dominio.facturacion import ServicioClinico
from app.dominio.mascota import Especie
from app.dominio.organizaciones import Clinica, LaboratorioCentral, Transportista
from app.dominio.personas import Bioquimico, Veterinario
from app.dominio.vacunas import Vacuna, VacunaObligatoria
from app.presentacion.componentes import (Tabla, abrir_dialogo, boton_cancelar, boton_icono, campo, campo_numero,
                                          confirmar, encabezado, leer_decimal, leer_entero, leer_id, leer_texto,
                                          selector)
from app.presentacion.vistas.base_vista import Vista
from app.utils import formato


def _leer_seleccion(control: ft.Dropdown, requerido: bool):
    """Las claves numéricas son identificadores; las demás, valores de una enumeración."""
    if not control.value:
        return leer_id(control, requerido)
    return int(control.value) if control.value.isdigit() else control.value


@dataclass
class Campo:
    atributo: str
    etiqueta: str
    tipo: str = "texto"            # texto | entero | decimal | booleano | seleccion | multiseleccion
    requerido: bool = False
    opciones: Callable[[], list[tuple]] | None = None


@dataclass
class Catalogo:
    entidad: str                   # clave del DAO en CatalogoService
    titulo: str
    clase: type
    campos: list[Campo]
    columnas: list[tuple[str, Callable]] = field(default_factory=list)


class CatalogosVista(Vista):
    def construir(self) -> ft.Control:
        nombres = lambda entidad, texto: (lambda: [(o.id, texto(o)) for o in self.servicios.catalogos.listar(entidad)])
        clinicas = nombres("clinica", lambda c: c.nombre)
        persona = [Campo("dni", "DNI", requerido=True), Campo("nombre", "Nombre", requerido=True),
                   Campo("apellido", "Apellido", requerido=True), Campo("telefono", "Teléfono"), Campo("email", "Email")]
        self.catalogos = [
            Catalogo("veterinario", "Veterinarios", Veterinario,
                     persona + [Campo("matricula", "Matrícula", requerido=True), Campo("especialidad", "Especialidad"),
                                Campo("ids_clinicas", "Clínicas donde atiende", "multiseleccion", True, clinicas)],
                     [("Apellido y nombre", lambda v: v.nombre_completo()), ("Matrícula", lambda v: v.matricula),
                      ("Especialidad", lambda v: v.especialidad), ("Teléfono", lambda v: v.telefono),
                      ("Clínicas", lambda v: ", ".join(t for i, t in clinicas() if i in v.ids_clinicas))]),
            Catalogo("clinica", "Clínicas", Clinica,
                     [Campo("nombre", "Nombre", requerido=True), Campo("direccion", "Dirección", requerido=True),
                      Campo("telefono", "Teléfono"), Campo("cuit", "CUIT", requerido=True)],
                     [("Nombre", lambda c: c.nombre), ("Dirección", lambda c: c.direccion), ("CUIT", lambda c: c.cuit),
                      ("Teléfono", lambda c: c.telefono)]),
            Catalogo("laboratorio", "Laboratorios", LaboratorioCentral,
                     [Campo("nombre", "Nombre", requerido=True), Campo("direccion", "Dirección", requerido=True),
                      Campo("telefono", "Teléfono")],
                     [("Nombre", lambda l: l.nombre), ("Dirección", lambda l: l.direccion), ("Teléfono", lambda l: l.telefono)]),
            Catalogo("bioquimico", "Bioquímicos", Bioquimico,
                     persona + [Campo("matricula", "Matrícula", requerido=True),
                                Campo("id_laboratorio", "Laboratorio", "seleccion", True,
                                      nombres("laboratorio", lambda l: l.nombre))],
                     [("Apellido y nombre", lambda b: b.nombre_completo()), ("Matrícula", lambda b: b.matricula),
                      ("Email", lambda b: b.email)]),
            Catalogo("conservadora", "Conservadoras (stock)", Conservadora,
                     [Campo("codigo", "Código", requerido=True), Campo("capacidad", "Capacidad (muestras)", "entero", True),
                      Campo("temp_min_c", "Temperatura mínima (°C)", "decimal", True),
                      Campo("temp_max_c", "Temperatura máxima (°C)", "decimal", True),
                      Campo("disponible", "Disponible", "booleano")],
                     [("Código", lambda c: c.codigo), ("Capacidad", lambda c: c.capacidad),
                      ("Rango", lambda c: f"{c.temp_min_c:g} a {c.temp_max_c:g} °C"),
                      ("Disponible", lambda c: "Sí" if c.disponible else "En uso")]),
            Catalogo("transportista", "Transportistas", Transportista,
                     [Campo("razon_social", "Razón social", requerido=True), Campo("cuit", "CUIT", requerido=True),
                      Campo("telefono", "Teléfono"), Campo("patente_vehiculo", "Patente del vehículo")],
                     [("Razón social", lambda t: t.razon_social), ("CUIT", lambda t: t.cuit),
                      ("Teléfono", lambda t: t.telefono), ("Patente", lambda t: t.patente_vehiculo)]),
            Catalogo("tipo_analisis", "Tipos de análisis", TipoAnalisis,
                     [Campo("codigo", "Código", requerido=True), Campo("nombre", "Nombre", requerido=True),
                      Campo("tipo_muestra_requerida", "Muestra requerida", "seleccion", True,
                            lambda: [(t.value, formato.etiqueta(t)) for t in TipoMuestra]),
                      Campo("temp_min_c", "Temperatura mínima (°C)", "decimal", True),
                      Campo("temp_max_c", "Temperatura máxima (°C)", "decimal", True),
                      Campo("horas_max_viabilidad", "Viabilidad máxima (horas)", "entero", True),
                      Campo("precio", "Precio", "decimal", True)],
                     [("Código", lambda t: t.codigo), ("Nombre", lambda t: t.nombre),
                      ("Muestra", lambda t: formato.etiqueta(t.tipo_muestra_requerida)),
                      ("Conservación", lambda t: f"{t.temp_min_c:g} a {t.temp_max_c:g} °C"),
                      ("Viabilidad", lambda t: f"{t.horas_max_viabilidad} h"), ("Precio", lambda t: formato.moneda(t.precio))]),
            Catalogo("servicio", "Servicios clínicos", ServicioClinico,
                     [Campo("codigo", "Código", requerido=True), Campo("nombre", "Nombre", requerido=True),
                      Campo("precio_base", "Precio", "decimal", True)],
                     [("Código", lambda s: s.codigo), ("Nombre", lambda s: s.nombre),
                      ("Precio", lambda s: formato.moneda(s.precio_base))]),
            Catalogo("vacuna", "Vacunas", Vacuna,
                     [Campo("nombre", "Nombre", requerido=True), Campo("laboratorio_fabricante", "Laboratorio fabricante")],
                     [("Nombre", lambda v: v.nombre), ("Fabricante", lambda v: v.laboratorio_fabricante)]),
            Catalogo("esquema", "Esquema de vacunación obligatorio", VacunaObligatoria,
                     [Campo("id_especie", "Especie", "seleccion", True, nombres("especie", lambda e: e.nombre)),
                      Campo("id_vacuna", "Vacuna", "seleccion", True, nombres("vacuna", lambda v: v.nombre)),
                      Campo("edad_minima_semanas", "Edad mínima (semanas)", "entero", True),
                      Campo("frecuencia_refuerzo_dias", "Refuerzo cada (días, vacío = dosis única)", "entero")],
                     [("Especie", lambda vo: dict(nombres("especie", lambda e: e.nombre)()).get(vo.id_especie)),
                      ("Vacuna", lambda vo: vo.nombre_vacuna), ("Edad mínima", lambda vo: f"{vo.edad_minima_semanas} semanas"),
                      ("Refuerzo", lambda vo: f"cada {vo.frecuencia_refuerzo_dias} días" if vo.frecuencia_refuerzo_dias
                       else "Dosis única")]),
            Catalogo("especie", "Especies", Especie, [Campo("nombre", "Nombre", requerido=True)],
                     [("Nombre", lambda e: e.nombre), ("Vacunas obligatorias", lambda e: len(e.esquema))]),
        ]
        self._actual = self.catalogos[0]
        self.selector = selector("Catálogo", [(c.entidad, c.titulo) for c in self.catalogos], self._actual.entidad,
                                 width=360, on_select=self.seguro(self._cambiar))
        self.contenedor = ft.Container(expand=True)
        return ft.Column([
            encabezado("Catálogos", "Datos de referencia de la red: profesionales, clínicas, laboratorio y servicios",
                       [ft.FilledButton("Nuevo", icon=ft.Icons.ADD, on_click=self.seguro(lambda e: self._formulario(None)))]),
            self.selector, self.contenedor], expand=True, spacing=12)

    def al_mostrar(self, **contexto) -> None:
        self.tabla = Tabla([titulo for titulo, _ in self._actual.columnas], acciones=self._acciones)
        objetos = self.servicios.catalogos.listar(self._actual.entidad)
        self.tabla.cargar([[mostrar(o) for _, mostrar in self._actual.columnas] for o in objetos], objetos)
        self.contenedor.content = self.tabla.control

    def _cambiar(self, e) -> None:
        self._actual = next(c for c in self.catalogos if c.entidad == self.selector.value)
        self.al_mostrar()

    def _acciones(self, objeto) -> list[ft.Control]:
        return [boton_icono(ft.Icons.EDIT, "Modificar", self.seguro(lambda e: self._formulario(objeto))),
                boton_icono(ft.Icons.DELETE_OUTLINE, "Eliminar", self.seguro(lambda e: confirmar(
                    self.page, "Eliminar", "¿Eliminar el registro? Solo es posible si no está en uso.",
                    self.seguro(lambda: self._eliminar(objeto)), "Eliminar", peligroso=True)), ft.Colors.RED_700)]

    def _eliminar(self, objeto) -> None:
        self.servicios.catalogos.eliminar(self._actual.entidad, objeto.id)
        self.notificar.exito("Registro eliminado.")
        self.al_mostrar()
        self.page.update()

    def _crear_control(self, definicion: Campo, valor) -> ft.Control:
        etiqueta = definicion.etiqueta + (" *" if definicion.requerido else "")
        if definicion.tipo == "booleano":
            return ft.Checkbox(label=etiqueta, value=True if valor is None else bool(valor))
        if definicion.tipo == "seleccion":
            return selector(etiqueta, definicion.opciones(), getattr(valor, "value", valor))
        if definicion.tipo == "multiseleccion":
            elegidos = set(valor or [])
            return ft.Column([ft.Text(etiqueta, weight=ft.FontWeight.W_600)] +
                             [ft.Checkbox(label=texto, value=clave in elegidos, data=clave)
                              for clave, texto in definicion.opciones()], spacing=0)
        if definicion.tipo in ("entero", "decimal"):
            return campo_numero(etiqueta, valor)
        return campo(etiqueta, valor)

    @staticmethod
    def _leer(definicion: Campo, control: ft.Control):
        lectores = {
            "texto": lambda c: leer_texto(c) or ("" if definicion.requerido else None),
            "entero": lambda c: leer_entero(c, definicion.requerido),
            "decimal": lambda c: leer_decimal(c, definicion.requerido),
            "booleano": lambda c: bool(c.value),
            "seleccion": lambda c: _leer_seleccion(c, definicion.requerido),
            "multiseleccion": lambda c: [check.data for check in c.controls[1:] if check.value],
        }
        return lectores[definicion.tipo](control)

    def _formulario(self, objeto) -> None:
        catalogo = self._actual
        controles = {d.atributo: self._crear_control(d, getattr(objeto, d.atributo, None) if objeto else None)
                     for d in catalogo.campos}

        def guardar(e):
            valores = {d.atributo: self._leer(d, controles[d.atributo]) for d in catalogo.campos}
            if "tipo_muestra_requerida" in valores and valores["tipo_muestra_requerida"]:
                valores["tipo_muestra_requerida"] = TipoMuestra(valores["tipo_muestra_requerida"])
            nuevo = dataclasses.replace(objeto, **valores) if objeto else catalogo.clase(**valores)
            self.servicios.catalogos.guardar(catalogo.entidad, nuevo)
            self.page.pop_dialog()
            self.notificar.exito(f"{catalogo.titulo}: registro guardado.")
            self.al_mostrar()
            self.page.update()

        abrir_dialogo(self.page, f"{'Modificar' if objeto else 'Nuevo'} · {catalogo.titulo}",
                      ft.Column(list(controles.values()), tight=True, spacing=12, scroll=ft.ScrollMode.AUTO),
                      [boton_cancelar(self.page), ft.FilledButton("Guardar", icon=ft.Icons.SAVE,
                                                                  on_click=self.seguro(guardar))])
