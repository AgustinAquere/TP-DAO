"""Jerarquía Persona: Cliente (responsable de mascotas), Veterinario y Bioquímico."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from app.utils import validaciones as v


@dataclass(kw_only=True)
class Persona(ABC):
    dni: str
    nombre: str
    apellido: str
    telefono: str | None = None
    email: str | None = None
    id: int | None = None

    def nombre_completo(self) -> str:
        return f"{self.apellido}, {self.nombre}"

    @abstractmethod
    def rol(self) -> str:
        """Nombre del rol que cumple la persona en el sistema."""

    def _reglas(self) -> list[v.Regla]:
        return [
            (lambda p: v.es_dni(p.dni), "El DNI debe tener 7 u 8 dígitos numéricos."),
            (lambda p: v.texto_requerido(p.nombre), "El nombre es obligatorio."),
            (lambda p: v.texto_requerido(p.apellido), "El apellido es obligatorio."),
            (lambda p: v.es_email(p.email), "El email no tiene un formato válido."),
            (lambda p: v.es_telefono(p.telefono), "El teléfono no tiene un formato válido."),
        ]

    def validar(self) -> None:
        v.validar(self, self._reglas())

    def __str__(self) -> str:
        return self.nombre_completo()


@dataclass(kw_only=True)
class Cliente(Persona):
    direccion: str | None = None
    fecha_alta: date = field(default_factory=date.today)
    activo: bool = True
    _mascotas: list = field(default_factory=list, init=False, repr=False, compare=False)

    def rol(self) -> str:
        return "Cliente"

    def agregar_mascota(self, mascota) -> None:
        mascota.id_cliente = self.id
        self._mascotas.append(mascota)

    def mascotas(self) -> list:
        return list(self._mascotas)


@dataclass(kw_only=True)
class Veterinario(Persona):
    matricula: str
    especialidad: str | None = None
    ids_clinicas: list[int] = field(default_factory=list)

    def rol(self) -> str:
        return "Veterinario"

    def trabaja_en(self, id_clinica: int) -> bool:
        return id_clinica in self.ids_clinicas

    def _reglas(self) -> list[v.Regla]:
        return super()._reglas() + [
            (lambda p: v.texto_requerido(p.matricula), "La matrícula es obligatoria."),
            (lambda p: len(p.ids_clinicas) > 0, "El veterinario debe trabajar en al menos una clínica."),
        ]


@dataclass(kw_only=True)
class Bioquimico(Persona):
    matricula: str
    id_laboratorio: int | None = None

    def rol(self) -> str:
        return "Bioquímico"

    def _reglas(self) -> list[v.Regla]:
        return super()._reglas() + [
            (lambda p: v.texto_requerido(p.matricula), "La matrícula es obligatoria."),
            (lambda p: p.id_laboratorio is not None, "Debe indicar el laboratorio donde trabaja."),
        ]
