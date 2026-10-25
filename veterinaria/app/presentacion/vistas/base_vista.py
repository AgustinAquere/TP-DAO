"""Clase base de las vistas: acceso a la página, a los servicios y manejo uniforme de errores."""
from abc import ABC, abstractmethod
from collections.abc import Callable

import flet as ft

from app.presentacion.componentes import manejar_errores


class Vista(ABC):
    def __init__(self, app):
        self.app = app
        self.page: ft.Page = app.page
        self.servicios = app.servicios
        self.notificar = app.notificador
        self._control: ft.Control | None = None

    @property
    def control(self) -> ft.Control:
        if self._control is None:
            self._control = self.construir()
        return self._control

    @abstractmethod
    def construir(self) -> ft.Control:
        """Arma los controles de la vista (se invoca una sola vez)."""

    def al_mostrar(self, **contexto) -> None:
        """Se invoca cada vez que se navega a la vista: refresca los datos."""

    def seguro(self, funcion: Callable) -> Callable:
        """Manejador de eventos que muestra los errores de negocio en lugar de propagarlos."""
        return manejar_errores(self.notificar, funcion)

    # Opciones frecuentes para los selectores (pares clave, texto)
    def opciones_clinicas(self) -> list[tuple]:
        return [(c.id, c.nombre) for c in self.servicios.catalogos.listar("clinica")]

    def opciones_veterinarios(self) -> list[tuple]:
        return [(v.id, f"{v.nombre_completo()} · {v.especialidad or 'General'}")
                for v in self.servicios.catalogos.listar("veterinario")]

    def opciones_mascotas(self) -> list[tuple]:
        return [(m["id_mascota"], f"{m['nombre']} ({m['especie']}) · {m['responsable']}")
                for m in self.servicios.mascotas.listar()]

    def opciones_laboratorios(self) -> list[tuple]:
        return [(l.id, l.nombre) for l in self.servicios.catalogos.listar("laboratorio")]
