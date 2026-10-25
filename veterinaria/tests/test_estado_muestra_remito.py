"""Patrón State (muestra y remito) e historial inmutable (Iterator)."""
import dataclasses
import unittest
from datetime import timedelta

from app.dominio.enums import EstadoPrecinto
from app.dominio.excepciones import TransicionInvalidaError, ValidacionError
from app.dominio.historial import CambioEstado, HistorialEstados, IteradorHistorial
from app.dominio.laboratorio import RecepcionLaboratorio
from tests import fabricas as f


def recepcion(horas: float = 6, intacto: bool = True, temperatura: float = 5.0) -> RecepcionLaboratorio:
    return RecepcionLaboratorio(id_remito=10, id_bioquimico=1, fecha_hora=f.INICIO + timedelta(hours=horas),
                                estado_precinto_verificado=EstadoPrecinto.INTACTO if intacto else EstadoPrecinto.ROTO,
                                temperatura_arribo_c=temperatura)


class TestCicloDeVidaMuestra(unittest.TestCase):
    def test_orden_extrae_una_muestra_por_tipo(self):
        o = f.orden(f.hemograma(), f.bioquimica(), f.bioquimica(id=3, codigo="T4", nombre="T4"))
        self.assertEqual(len(o.muestras), 2)  # sangre y suero (el suero sirve para dos análisis)
        self.assertEqual([m.nombre_estado() for m in o.muestras], ["EXTRAIDA", "EXTRAIDA"])

    def test_recorrido_completo_registra_historial(self):
        o, r = f.remito_en_transito(f.hemograma())
        r.recibir(recepcion(), responsable="Bioq")
        muestra = o.muestras[0]
        muestra.analizar(responsable="Bioq", fecha_hora=f.INICIO + timedelta(hours=8))
        estados = [c.estado_nuevo for c in muestra.historial()]
        self.assertEqual(estados, ["EXTRAIDA", "EMPAQUETADA", "EN_TRANSITO", "RECIBIDA", "ANALIZADA"])
        self.assertTrue(muestra.es_final())

    def test_transicion_invalida(self):
        muestra = f.orden(f.hemograma()).muestras[0]
        with self.assertRaises(TransicionInvalidaError):
            muestra.recibir(responsable="x")      # Extraída no puede pasar a Recibida
        with self.assertRaises(TransicionInvalidaError):
            muestra.analizar(responsable="x")

    def test_muestra_rechazada_no_se_procesa(self):
        o, r = f.remito_en_transito(f.hemograma())
        r.recibir(recepcion(intacto=False), responsable="Bioq")
        with self.assertRaises(TransicionInvalidaError):
            o.muestras[0].analizar(responsable="Bioq")


class TestHistorialInmutable(unittest.TestCase):
    def test_cambio_estado_es_inmutable(self):
        cambio = CambioEstado(f.INICIO, None, "EXTRAIDA", "Vet")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            cambio.estado_nuevo = "ANALIZADA"

    def test_historial_solo_admite_cambios_consecutivos(self):
        historial = HistorialEstados([CambioEstado(f.INICIO, None, "EXTRAIDA", "Vet")])
        with self.assertRaises(ValidacionError):
            historial.registrar(CambioEstado(f.INICIO + timedelta(hours=1), "RECIBIDA", "ANALIZADA", "x"))
        with self.assertRaises(ValidacionError):
            historial.registrar(CambioEstado(f.INICIO - timedelta(hours=1), "EXTRAIDA", "EMPAQUETADA", "x"))

    def test_iterador_explicito(self):
        historial = HistorialEstados([CambioEstado(f.INICIO, None, "EXTRAIDA", "Vet"),
                                      CambioEstado(f.INICIO, "EXTRAIDA", "EMPAQUETADA", "Vet")])
        iterador = iter(historial)
        self.assertIsInstance(iterador, IteradorHistorial)
        self.assertEqual(next(iterador).estado_nuevo, "EXTRAIDA")
        self.assertEqual(next(iterador).estado_nuevo, "EMPAQUETADA")
        with self.assertRaises(StopIteration):
            next(iterador)
        self.assertFalse(hasattr(historial, "eliminar"))


class TestCicloDeVidaRemito(unittest.TestCase):
    def test_operaciones_permitidas_por_estado(self):
        r = f.remito()
        self.assertEqual(r.operaciones_permitidas(), {"agregar_muestra", "quitar_muestra", "precintar"})
        with self.assertRaises(TransicionInvalidaError):
            r.despachar(f.tramo(), responsable="Vet")

    def test_no_se_precinta_vacio(self):
        with self.assertRaises(ValidacionError):
            f.remito().precintar("PS-1", responsable="Vet")

    def test_conservadora_controla_capacidad_y_temperatura(self):
        o = f.orden()
        with self.assertRaises(ValidacionError):
            f.remito(temp_min=15, temp_max=25).agregar_muestra(o.muestras[0])
        chica = f.remito(capacidad=1)
        chica.agregar_muestra(o.muestras[0])
        with self.assertRaises(ValidacionError):
            chica.agregar_muestra(o.muestras[1])

    def test_precinto_roto_rechaza_todas_las_muestras(self):
        o, r = f.remito_en_transito()
        r.recibir(recepcion(intacto=False), responsable="Bioq")
        self.assertEqual(r.nombre_estado(), "RECHAZADO")
        self.assertFalse(r.precinto.esta_intacto())
        self.assertTrue(all(m.nombre_estado() == "RECHAZADA" for m in o.muestras))
        self.assertFalse(r.recepcion.aceptada)

    def test_precinto_intacto_evalua_temperatura_y_viabilidad(self):
        o, r = f.remito_en_transito()
        r.recibir(recepcion(horas=30), responsable="Bioq")   # 30 h: vence el hemograma (24 h), no la bioquímica (48 h)
        self.assertEqual(r.nombre_estado(), "RECIBIDO")
        self.assertEqual([m.nombre_estado() for m in o.muestras], ["RECHAZADA", "RECIBIDA"])
        o, r = f.remito_en_transito()
        r.recibir(recepcion(temperatura=12), responsable="Bioq")
        self.assertTrue(all(m.nombre_estado() == "RECHAZADA" for m in o.muestras))

    def test_cadena_de_custodia_con_varios_tramos(self):
        _, r = f.remito_en_transito()
        with self.assertRaises(ValidacionError):  # el tramo actual sigue abierto
            r.registrar_tramo(f.tramo(horas=3))
        r.cerrar_tramo(fecha_hora_llegada=f.INICIO + timedelta(hours=3), recibido_por="Centro logístico")
        r.registrar_tramo(f.tramo(horas=3.5))
        r.recibir(recepcion(horas=5), responsable="Bioq")
        self.assertEqual([t.nro_orden for t in r.tramos], [1, 2])
        self.assertEqual(r.tiempo_transito(), timedelta(hours=3))


if __name__ == "__main__":
    unittest.main()
