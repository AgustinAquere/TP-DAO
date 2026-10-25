"""Clínicas de la red, laboratorio central y empresas de transporte."""
from dataclasses import dataclass

from app.utils import validaciones as v


@dataclass(kw_only=True)
class Clinica:
    nombre: str
    direccion: str
    cuit: str
    telefono: str | None = None
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda c: v.texto_requerido(c.nombre), "El nombre es obligatorio."),
            (lambda c: v.texto_requerido(c.direccion), "La dirección es obligatoria."),
            (lambda c: v.es_cuit(c.cuit), "El CUIT debe tener el formato 30-12345678-9."),
        ])

    def __str__(self) -> str:
        return self.nombre


@dataclass(kw_only=True)
class LaboratorioCentral:
    nombre: str
    direccion: str
    telefono: str | None = None
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda l: v.texto_requerido(l.nombre), "El nombre es obligatorio."),
            (lambda l: v.texto_requerido(l.direccion), "La dirección es obligatoria."),
        ])

    def __str__(self) -> str:
        return self.nombre


@dataclass(kw_only=True)
class Transportista:
    razon_social: str
    cuit: str
    telefono: str | None = None
    patente_vehiculo: str | None = None
    id: int | None = None

    def validar(self) -> None:
        v.validar(self, [
            (lambda t: v.texto_requerido(t.razon_social), "La razón social es obligatoria."),
            (lambda t: v.es_cuit(t.cuit), "El CUIT debe tener el formato 30-12345678-9."),
        ])

    def __str__(self) -> str:
        return self.razon_social
