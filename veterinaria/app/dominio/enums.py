"""Enumeraciones del dominio. Sus valores coinciden con los CHECK del esquema SQLite."""
from enum import StrEnum


class TipoAtencion(StrEnum):
    CONSULTA = "CONSULTA"
    CONTROL = "CONTROL"
    URGENCIA = "URGENCIA"


class EstadoTurno(StrEnum):
    RESERVADO = "RESERVADO"
    ATENDIDO = "ATENDIDO"
    CANCELADO = "CANCELADO"
    AUSENTE = "AUSENTE"


class Sexo(StrEnum):
    MACHO = "M"
    HEMBRA = "H"


class Prioridad(StrEnum):
    NORMAL = "NORMAL"
    URGENTE = "URGENTE"


class EstadoOrden(StrEnum):
    EMITIDA = "EMITIDA"
    EN_PROCESO = "EN_PROCESO"
    COMPLETA = "COMPLETA"
    CANCELADA = "CANCELADA"


class TipoMuestra(StrEnum):
    SANGRE = "SANGRE"
    SUERO = "SUERO"
    ORINA = "ORINA"
    MATERIA_FECAL = "MATERIA_FECAL"
    TEJIDO = "TEJIDO"
    HISOPADO = "HISOPADO"


class EstadoPrecinto(StrEnum):
    INTACTO = "INTACTO"
    ROTO = "ROTO"


class TipoItem(StrEnum):
    SERVICIO_CLINICO = "SERVICIO_CLINICO"
    ANALISIS_LABORATORIO = "ANALISIS_LABORATORIO"
    VACUNA = "VACUNA"
    INSUMO = "INSUMO"
