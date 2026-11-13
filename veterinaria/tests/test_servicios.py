"""Servicios y base de datos (SQLite en memoria con el esquema del DER y los datos de ejemplo)."""
import unittest
from datetime import date, datetime, timedelta

from app.dominio.enums import EstadoTurno, TipoAtencion
from app.dominio.excepciones import (ErrorPersistencia, EsquemaVacunasIncompletoError, TransicionInvalidaError,
                                     TurnoSuperpuestoError, ValidacionError)
from app.persistencia.conexion import ConexionBD
from app.persistencia.inicializador import crear_esquema
from app.persistencia.semilla import cargar_datos_de_ejemplo
from app.servicios.atencion_service import SolicitudDerivacion
from app.servicios.contenedor import Servicios
from app.utils import fechas


class BaseDeDatosDePrueba(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ConexionBD.reiniciar()
        cls.bd = ConexionBD(":memory:")
        crear_esquema(cls.bd)
        cls.s = Servicios(cls.bd)
        cargar_datos_de_ejemplo(cls.s)

    @classmethod
    def tearDownClass(cls):
        ConexionBD.reiniciar()

    def id_de(self, sql: str, parametros: tuple = ()) -> int:
        return self.bd.valor(sql, parametros)


class TestSingleton(BaseDeDatosDePrueba):
    def test_unica_instancia(self):
        self.assertIs(ConexionBD(), ConexionBD.obtener_instancia())
        self.assertIs(ConexionBD("otra.db"), self.bd)


class TestValidacionesDeNegocio(BaseDeDatosDePrueba):
    def test_mascota_requiere_responsable(self):
        with self.assertRaises(ValidacionError):
            self.s.mascotas.alta(None, id_especie=1, nombre="Firulais", fecha_nacimiento=date(2024, 1, 1))
        with self.assertRaises(ErrorPersistencia):  # la base también lo exige (NOT NULL + FK)
            self.bd.ejecutar("INSERT INTO mascota (id_cliente, id_especie, nombre) VALUES (NULL, 1, 'X')")

    def test_alta_de_mascota_abre_historia_clinica(self):
        id_cliente = self.id_de("SELECT MIN(id_cliente) FROM cliente")
        mascota = self.s.mascotas.alta(id_cliente, id_especie=1, nombre="Nueva", fecha_nacimiento=date(2025, 5, 1))
        self.assertTrue(self.s.mascotas.historia_clinica(mascota.id).numero.startswith("HC-"))

    def test_turnos_sin_superposicion(self):
        id_vet = self.id_de("SELECT MIN(id_veterinario) FROM veterinario")
        id_clinica = self.id_de("SELECT MIN(id_clinica) FROM veterinario_clinica WHERE id_veterinario = ?", (id_vet,))
        id_mascota = self.id_de("SELECT MIN(id_mascota) FROM mascota")
        inicio = datetime.combine(date.today() + timedelta(days=30), datetime.min.time()).replace(hour=10)
        self.s.turnos.reservar(id_vet, id_mascota, id_clinica, inicio, 30)
        with self.assertRaises(TurnoSuperpuestoError):
            self.s.turnos.reservar(id_vet, id_mascota, id_clinica, inicio + timedelta(minutes=15), 30)
        with self.assertRaises(ErrorPersistencia):  # trigger de la base
            self.bd.ejecutar("INSERT INTO turno (id_veterinario, id_mascota, id_clinica, fecha_hora_inicio, duracion_min)"
                             " VALUES (?, ?, ?, ?, 30)", (id_vet, id_mascota, id_clinica,
                                                          fechas.a_sql(inicio + timedelta(minutes=10))))

    def test_listar_turnos_por_rango_de_fechas(self):
        id_vet = self.id_de("SELECT MIN(id_veterinario) FROM veterinario")
        id_clinica = self.id_de("SELECT MIN(id_clinica) FROM veterinario_clinica WHERE id_veterinario = ?", (id_vet,))
        id_mascota = self.id_de("SELECT MIN(id_mascota) FROM mascota")
        lunes = date.today() + timedelta(days=80)
        lunes -= timedelta(days=lunes.weekday())
        manana = datetime.combine(lunes, datetime.min.time()).replace(hour=9)
        miercoles = manana + timedelta(days=2)
        self.s.turnos.reservar(id_vet, id_mascota, id_clinica, manana, 30)
        self.s.turnos.reservar(id_vet, id_mascota, id_clinica, miercoles, 60)
        semana = self.s.turnos.listar(id_veterinario=id_vet, desde=lunes, hasta=lunes + timedelta(days=6))
        inicios = {t["fecha_hora_inicio"] for t in semana}
        self.assertIn(fechas.a_sql(manana), inicios)
        self.assertIn(fechas.a_sql(miercoles), inicios)
        del_lunes = {t["fecha_hora_inicio"] for t in self.s.turnos.listar(fecha=lunes, id_veterinario=id_vet)}
        self.assertIn(fechas.a_sql(manana), del_lunes)
        self.assertNotIn(fechas.a_sql(miercoles), del_lunes)

    def test_ausente_y_cancelado_vuelven_a_reservado(self):
        id_vet = self.id_de("SELECT MIN(id_veterinario) FROM veterinario")
        id_clinica = self.id_de("SELECT MIN(id_clinica) FROM veterinario_clinica WHERE id_veterinario = ?", (id_vet,))
        id_mascota = self.id_de("SELECT MIN(id_mascota) FROM mascota")
        dia = date.today() + timedelta(days=50)
        ausente = self.s.turnos.reservar(id_vet, id_mascota, id_clinica, datetime.combine(dia, datetime.min.time()).replace(hour=9), 30)
        cancelado = self.s.turnos.reservar(id_vet, id_mascota, id_clinica, datetime.combine(dia, datetime.min.time()).replace(hour=11), 30)
        self.s.turnos.marcar_ausente(ausente.id)
        self.s.turnos.cancelar(cancelado.id)
        self.s.turnos.reactivar(ausente.id)
        self.s.turnos.reactivar(cancelado.id)
        estados = {t["id_turno"]: t["estado"] for t in self.s.turnos.listar(fecha=dia, id_veterinario=id_vet)}
        self.assertEqual(estados[ausente.id], EstadoTurno.RESERVADO)
        self.assertEqual(estados[cancelado.id], EstadoTurno.RESERVADO)

    def test_cancelado_no_vuelve_si_el_horario_fue_tomado(self):
        id_vet = self.id_de("SELECT MIN(id_veterinario) FROM veterinario")
        id_clinica = self.id_de("SELECT MIN(id_clinica) FROM veterinario_clinica WHERE id_veterinario = ?", (id_vet,))
        id_mascota = self.id_de("SELECT MIN(id_mascota) FROM mascota")
        inicio = datetime.combine(date.today() + timedelta(days=60), datetime.min.time()).replace(hour=15)
        primero = self.s.turnos.reservar(id_vet, id_mascota, id_clinica, inicio, 30)
        self.s.turnos.cancelar(primero.id)
        self.s.turnos.reservar(id_vet, id_mascota, id_clinica, inicio, 30)
        with self.assertRaises(TurnoSuperpuestoError):
            self.s.turnos.reactivar(primero.id)

    def test_control_de_esquema_de_vacunas(self):
        id_cliente = self.id_de("SELECT MIN(id_cliente) FROM cliente")
        cachorro = self.s.mascotas.alta(id_cliente, id_especie=self.id_de("SELECT id_especie FROM especie WHERE nombre='Canino'"),
                                        nombre="Cachorro", fecha_nacimiento=date.today() - timedelta(weeks=14))
        veterinario = self.s.catalogos.listar("veterinario")[0]
        datos = dict(id_mascota=cachorro.id, id_veterinario=veterinario.id, id_clinica=veterinario.ids_clinicas[0],
                     tipo=TipoAtencion.CONTROL, motivo="Primer control")
        with self.assertRaises(EsquemaVacunasIncompletoError) as error:
            self.s.atenciones.registrar(**datos)
        self.assertEqual(len(error.exception.pendientes), 2)  # séxtuple y antirrábica
        vacunas = [(vo.id_vacuna, "L-1") for vo in error.exception.pendientes]
        atencion = self.s.atenciones.registrar(**datos, vacunas=vacunas)  # aplicándolas, el esquema queda al día
        self.assertEqual(atencion.vacunas_pendientes, [])
        self.assertEqual(self.s.atenciones.vacunas_pendientes(cachorro.id), [])


class TestCircuitoDeMuestras(BaseDeDatosDePrueba):
    def _atencion_con_orden(self, codigos: list[str]):
        veterinario = self.s.catalogos.listar("veterinario")[1]
        id_clinica = veterinario.ids_clinicas[0]
        ids = [self.id_de("SELECT id_tipo_analisis FROM tipo_analisis WHERE codigo = ?", (c,)) for c in codigos]
        atencion = self.s.atenciones.registrar(
            id_mascota=self.id_de("SELECT MAX(id_mascota) FROM mascota"), id_veterinario=veterinario.id,
            id_clinica=id_clinica, tipo=TipoAtencion.CONSULTA, motivo="Estudio", confirmar_esquema_incompleto=True,
            fecha_hora=fechas.ahora() - timedelta(hours=3),
            derivacion=SolicitudDerivacion(id_laboratorio=self.id_de("SELECT MIN(id_laboratorio) FROM laboratorio_central"),
                                           ids_tipo_analisis=ids))
        orden = atencion.ordenes[0]
        return atencion, orden, id_clinica, veterinario

    def _enviar(self, orden, id_clinica, veterinario):
        conservadora = next(c for c in self.s.derivaciones.conservadoras_disponibles() if c.temp_min_c >= 2 and c.temp_max_c <= 8)
        remito = self.s.derivaciones.armar_remito([m.id for m in orden.muestras], conservadora.id, id_clinica,
                                                  fechas.ahora() - timedelta(hours=2, minutes=30))
        self.s.derivaciones.precintar(remito.id, veterinario.id, fecha_hora=fechas.ahora() - timedelta(hours=2))
        self.s.derivaciones.despachar(remito.id, self.id_de("SELECT MIN(id_transportista) FROM transportista"),
                                      veterinario.id, fecha_hora=fechas.ahora() - timedelta(hours=1, minutes=30))
        return remito

    def test_precinta_y_despacha_solo_personal_de_la_clinica_de_origen(self):
        _, orden, id_clinica, veterinario = self._atencion_con_orden(["HEMO"])
        conservadora = next(c for c in self.s.derivaciones.conservadoras_disponibles() if c.temp_min_c >= 2 and c.temp_max_c <= 8)
        remito = self.s.derivaciones.armar_remito([m.id for m in orden.muestras], conservadora.id, id_clinica)
        habilitados = self.s.derivaciones.veterinarios_de_clinica(id_clinica)
        self.assertIn(veterinario.id, [v.id for v in habilitados])
        ajeno = next(v for v in self.s.catalogos.listar("veterinario") if not v.trabaja_en(id_clinica))
        with self.assertRaises(ValidacionError):
            self.s.derivaciones.precintar(remito.id, ajeno.id)
        with self.assertRaises(ValidacionError):
            self.s.derivaciones.precintar(remito.id, None)
        self.s.derivaciones.precintar(remito.id, veterinario.id)
        muestra = self.s.derivaciones.trazabilidad(orden.muestras[0].id)
        self.assertEqual(muestra.historial().ultimo().responsable, veterinario.nombre_completo())

        id_transportista = self.id_de("SELECT MIN(id_transportista) FROM transportista")
        with self.assertRaises(ValidacionError):
            self.s.derivaciones.despachar(remito.id, id_transportista, ajeno.id)
        with self.assertRaises(ValidacionError):
            self.s.derivaciones.despachar(remito.id, id_transportista, None)
        tramo = self.s.derivaciones.despachar(remito.id, id_transportista, veterinario.id)
        self.assertEqual(tramo.entregado_por, veterinario.nombre_completo())
        muestra = self.s.derivaciones.trazabilidad(orden.muestras[0].id)
        self.assertEqual(muestra.historial().ultimo().responsable, veterinario.nombre_completo())

    def test_precinto_roto_impide_procesar(self):
        _, orden, id_clinica, veterinario = self._atencion_con_orden(["HEMO"])
        remito = self._enviar(orden, id_clinica, veterinario)
        bioquimico = self.s.catalogos.listar("bioquimico")[0]
        recibido = self.s.laboratorio.registrar_recepcion(remito.id, bioquimico.id, precinto_intacto=False,
                                                          temperatura_arribo=5)
        self.assertEqual(recibido.nombre_estado(), "RECHAZADO")
        id_analisis = self.id_de("SELECT id_analisis_solicitado FROM analisis_solicitado WHERE id_orden = ?", (orden.id,))
        with self.assertRaises(TransicionInvalidaError):
            self.s.laboratorio.registrar_resultado(id_analisis, bioquimico.id, [])
        nueva = self.s.derivaciones.reextraer_muestra(orden.muestras[0].id, "Vet")  # nueva extracción, misma orden
        self.assertEqual(nueva.nombre_estado(), "EXTRAIDA")

    def test_resultado_completa_la_orden(self):
        _, orden, id_clinica, veterinario = self._atencion_con_orden(["BIOQ", "T4"])
        remito = self._enviar(orden, id_clinica, veterinario)
        bioquimico = self.s.catalogos.listar("bioquimico")[0]
        self.s.laboratorio.registrar_recepcion(remito.id, bioquimico.id, precinto_intacto=True, temperatura_arribo=5)
        for fila in self.bd.consultar("SELECT an.id_analisis_solicitado, ta.codigo FROM analisis_solicitado an "
                                      "JOIN tipo_analisis ta USING (id_tipo_analisis) WHERE id_orden = ?", (orden.id,)):
            detalles = self.s.laboratorio.plantilla_resultado(fila["codigo"])
            self.s.laboratorio.registrar_resultado(fila["id_analisis_solicitado"], bioquimico.id, detalles)
        self.assertEqual(self.bd.valor("SELECT estado FROM orden_derivacion WHERE id_orden = ?", (orden.id,)), "COMPLETA")
        muestra = self.s.derivaciones.trazabilidad(orden.muestras[0].id)
        self.assertEqual(muestra.nombre_estado(), "ANALIZADA")
        self.assertEqual(len(muestra.historial()), 5)

    def test_trazabilidad_inmutable_en_la_base(self):
        with self.assertRaises(ErrorPersistencia):
            self.bd.ejecutar("UPDATE cambio_estado_muestra SET estado_nuevo = 'ANALIZADA'")
        with self.assertRaises(ErrorPersistencia):
            self.bd.ejecutar("DELETE FROM cambio_estado_muestra")


class TestFacturacionYReportes(BaseDeDatosDePrueba):
    def test_comprobante_por_estrategia(self):
        pendiente = self.s.facturacion.atenciones_sin_comprobante()[0]
        comprobante = self.s.facturacion.emitir(pendiente["id_atencion"])
        self.assertEqual(comprobante.estrategia_tarifa, pendiente["tipo"])
        with self.assertRaises(ValidacionError):
            self.s.facturacion.emitir(pendiente["id_atencion"])  # una atención, un comprobante

    def test_reportes_generan_datos(self):
        hasta = date.today()
        desde = hasta - timedelta(days=120)
        for definicion in self.s.reportes.catalogo():
            for agrupacion in list(definicion.agrupaciones) or [None]:
                reporte = self.s.reportes.generar(definicion.clave, desde, hasta, agrupacion)
                self.assertTrue(reporte.secciones)
                self.assertTrue(any(seccion.filas for seccion in reporte.secciones), definicion.clave)


if __name__ == "__main__":
    unittest.main()
