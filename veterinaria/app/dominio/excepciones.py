"""Excepciones de negocio. La interfaz muestra su mensaje al usuario."""


class ErrorNegocio(Exception):
    """Base de todos los errores que representan una regla de negocio incumplida."""


class ValidacionError(ErrorNegocio):
    """Datos inválidos. Agrupa todos los mensajes para mostrarlos juntos."""

    def __init__(self, errores: list[str] | str):
        self.errores = [errores] if isinstance(errores, str) else list(errores)
        super().__init__("\n".join(self.errores))


class EntidadNoEncontradaError(ErrorNegocio):
    def __init__(self, entidad: str, identificador):
        super().__init__(f"No se encontró {entidad} con identificador {identificador}.")


class TransicionInvalidaError(ErrorNegocio):
    """Operación no permitida en el estado actual (patrón State)."""


class TurnoSuperpuestoError(ErrorNegocio):
    """El turno se superpone con otro turno del mismo veterinario."""


class EsquemaVacunasIncompletoError(ErrorNegocio):
    """La mascota tiene vacunas obligatorias pendientes al registrar la atención."""

    def __init__(self, pendientes: list):
        self.pendientes = pendientes
        nombres = ", ".join(vo.nombre_vacuna for vo in pendientes)
        super().__init__(f"La mascota tiene vacunas obligatorias pendientes: {nombres}.")


class ErrorPersistencia(ErrorNegocio):
    """Error al guardar en la base (restricciones, triggers de validación, etc.)."""
