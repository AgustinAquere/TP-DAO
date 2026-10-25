"""Strategy de tarifas, superposición de turnos y esquema de vacunas obligatorias."""
import unittest
from datetime import date, datetime

from app.dominio.enums import TipoItem
from app.dominio.excepciones import TurnoSuperpuestoError, ValidacionError
from app.dominio.facturacion import ComprobanteAtencion, ItemComprobante
from app.dominio.mascota import Especie, Mascota
from app.dominio.tarifas import TarifaConsulta, TarifaControl, TarifaUrgencia
from app.dominio.turnos import Agenda, Turno
from app.dominio.vacunas import AplicacionVacuna, VacunaObligatoria


def comprobante_de_prueba() -> ComprobanteAtencion:
    comprobante = ComprobanteAtencion(id_atencion=1, id_cliente=1, id_clinica=1, numero="0001-00000001",
                                      fecha_emision=datetime(2026, 10, 1, 10))
    comprobante.agregar_item(ItemComprobante(tipo=TipoItem.SERVICIO_CLINICO, descripcion="Consulta",
                                             precio_unitario=10000, id_servicio=1))
    comprobante.agregar_item(ItemComprobante(tipo=TipoItem.ANALISIS_LABORATORIO, descripcion="Hemograma",
                                             precio_unitario=5000, id_tipo_analisis=1))
    comprobante.agregar_item(ItemComprobante(tipo=TipoItem.INSUMO, descripcion="Jeringas", precio_unitario=500,
                                             cantidad=2))
    return comprobante


class TestEstrategiasDeTarifa(unittest.TestCase):
    def test_misma_llamada_distintas_estrategias(self):
        comprobante = comprobante_de_prueba()
        esperado = [(TarifaConsulta(), 16000), (TarifaControl(descuento_pct=20), 14000),
                    (TarifaUrgencia(datetime(2026, 10, 1, 10), recargo_pct=30, recargo_nocturno_pct=25), 19000),
                    (TarifaUrgencia(datetime(2026, 10, 1, 23), recargo_pct=30, recargo_nocturno_pct=25), 21500)]
        for estrategia, total in esperado:
            comprobante.set_estrategia(estrategia)
            self.assertEqual(comprobante.total(), total, estrategia.nombre())
        self.assertEqual(comprobante.subtotal(), 16000)

    def test_emitir_congela_importes(self):
        comprobante = comprobante_de_prueba()
        comprobante.set_estrategia(TarifaControl(descuento_pct=20))
        comprobante.emitir()
        comprobante.items[0].precio_unitario = 99999  # cambios posteriores no alteran lo emitido
        self.assertEqual((comprobante.subtotal(), comprobante.total()), (16000, 14000))

    def test_item_debe_referenciar_su_concepto(self):
        with self.assertRaises(ValidacionError):
            ItemComprobante(tipo=TipoItem.VACUNA, descripcion="Vacuna", precio_unitario=1).validar()


class TestAgenda(unittest.TestCase):
    def setUp(self):
        self.dia = date(2026, 11, 2)
        existente = Turno(id_veterinario=1, id_mascota=1, id_clinica=1, duracion_min=30,
                          fecha_hora_inicio=datetime(2026, 11, 2, 10, 0), id=1)
        self.agenda = Agenda(1, self.dia, [existente])

    def test_superposicion(self):
        with self.assertRaises(TurnoSuperpuestoError):
            self.agenda.reservar(2, 1, datetime(2026, 11, 2, 10, 15), 30)
        turno = self.agenda.reservar(2, 1, datetime(2026, 11, 2, 10, 30), 30)  # contiguo: no se superpone
        self.assertEqual(turno.fecha_hora_fin(), datetime(2026, 11, 2, 11, 0))

    def test_cancelado_libera_el_horario(self):
        next(iter(self.agenda)).cancelar()
        self.agenda.reservar(2, 1, datetime(2026, 11, 2, 10, 0), 30)

    def test_horarios_disponibles_excluyen_ocupados(self):
        libres = self.agenda.turnos_disponibles(30)
        self.assertNotIn(datetime(2026, 11, 2, 10, 0), libres)
        self.assertIn(datetime(2026, 11, 2, 10, 30), libres)
        self.assertNotIn(datetime(2026, 11, 2, 9, 30), self.agenda.turnos_disponibles(45))  # terminaría 10:15

    def test_fuera_de_jornada(self):
        with self.assertRaises(ValidacionError):
            self.agenda.reservar(2, 1, datetime(2026, 11, 2, 19, 45), 30)


class TestEsquemaDeVacunas(unittest.TestCase):
    def setUp(self):
        self.esquema = [VacunaObligatoria(id_especie=1, id_vacuna=1, edad_minima_semanas=6, frecuencia_refuerzo_dias=365,
                                          nombre_vacuna="Séxtuple"),
                        VacunaObligatoria(id_especie=1, id_vacuna=2, edad_minima_semanas=12, nombre_vacuna="Única")]
        self.mascota = Mascota(id_cliente=1, id_especie=1, nombre="Kira", fecha_nacimiento=date(2026, 1, 1),
                               especie=Especie(nombre="Canino", esquema=self.esquema, id=1))

    def test_edad_minima(self):
        self.assertEqual(self.mascota.vacunas_pendientes(date(2026, 1, 20)), [])  # menos de 6 semanas
        pendientes = self.mascota.vacunas_pendientes(date(2026, 3, 1))
        self.assertEqual([v.nombre_vacuna for v in pendientes], ["Séxtuple"])

    def test_refuerzo_y_dosis_unica(self):
        self.mascota.aplicaciones = [AplicacionVacuna(id_vacuna=1, fecha=date(2026, 3, 1), lote="A"),
                                     AplicacionVacuna(id_vacuna=2, fecha=date(2026, 4, 1), lote="B")]
        self.assertEqual(self.mascota.vacunas_pendientes(date(2026, 12, 1)), [])
        vencidas = self.mascota.vacunas_pendientes(date(2027, 3, 1))   # refuerzo anual vencido
        self.assertEqual([v.nombre_vacuna for v in vencidas], ["Séxtuple"])

    def test_mascota_sin_responsable(self):
        with self.assertRaises(ValidacionError):
            Mascota(id_cliente=None, id_especie=1, nombre="Sin dueño", fecha_nacimiento=date(2025, 1, 1)).validar()


if __name__ == "__main__":
    unittest.main()
