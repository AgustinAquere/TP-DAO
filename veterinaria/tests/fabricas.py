"""Objetos de prueba reutilizados por los tests de dominio."""
from datetime import datetime, timedelta

from app.dominio.derivacion import OrdenDerivacion, TipoAnalisis
from app.dominio.enums import TipoMuestra
from app.dominio.envio import Conservadora, TramoEnvio
from app.dominio.remito import RemitoBiologico

INICIO = datetime(2026, 10, 20, 10, 0)


def hemograma(**cambios) -> TipoAnalisis:
    datos = dict(codigo="HEMO", nombre="Hemograma", tipo_muestra_requerida=TipoMuestra.SANGRE, temp_min_c=2,
                 temp_max_c=8, horas_max_viabilidad=24, precio=1000, id=1)
    return TipoAnalisis(**(datos | cambios))


def bioquimica(**cambios) -> TipoAnalisis:
    datos = dict(codigo="BIOQ", nombre="Bioquímica", tipo_muestra_requerida=TipoMuestra.SUERO, temp_min_c=2,
                 temp_max_c=8, horas_max_viabilidad=48, precio=2000, id=2)
    return TipoAnalisis(**(datos | cambios))


def orden(*tipos: TipoAnalisis) -> OrdenDerivacion:
    return OrdenDerivacion.emitir(id_atencion=1, id_laboratorio=1, numero="OD-1", fecha_emision=INICIO,
                                  tipos_analisis=list(tipos or (hemograma(), bioquimica())), id_veterinario=1,
                                  responsable="Vet")


def remito(capacidad: int = 4, temp_min: float = 2, temp_max: float = 8) -> RemitoBiologico:
    r = RemitoBiologico(id_conservadora=1, id_clinica_origen=1, id_laboratorio_destino=1, numero="RB-1",
                        fecha_hora_emision=INICIO, id=10)
    r.conservadora = Conservadora(codigo="C1", capacidad=capacidad, temp_min_c=temp_min, temp_max_c=temp_max)
    r.nombre_clinica, r.nombre_laboratorio = "Clínica", "Laboratorio"
    return r


def tramo(horas: float = 2) -> TramoEnvio:
    return TramoEnvio(id_transportista=1, origen="Clínica", destino="Laboratorio",
                      fecha_hora_salida=INICIO + timedelta(hours=horas), entregado_por="Vet")


def remito_en_transito(*tipos: TipoAnalisis):
    """Remito con las muestras de una orden, ya precintado y despachado."""
    o, r = orden(*tipos), remito()
    for muestra in o.muestras:
        r.agregar_muestra(muestra)
    r.precintar("PS-1", responsable="Vet", fecha_hora=INICIO + timedelta(hours=1))
    r.despachar(tramo(), responsable="Vet")
    return o, r
