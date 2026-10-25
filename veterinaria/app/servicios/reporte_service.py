"""Reportes del enunciado. Cada uno combina consultas SQL (ReporteDAO) con reglas del dominio."""
from collections import Counter, defaultdict
from datetime import date

from app.dominio.excepciones import ValidacionError
from app.dominio.vacunas import AplicacionVacuna
from app.persistencia.daos.catalogos_dao import EspecieDAO
from app.persistencia.daos.mascota_dao import MascotaDAO
from app.persistencia.daos.reporte_dao import ReporteDAO
from app.reportes.modelo import Columna, DefinicionReporte, Grafico, Reporte, Seccion
from app.utils import fechas, formato

# Formatos de columna (funciones lambda reutilizables)
ENTERO = lambda v: formato.numero(v or 0, 0)
HORAS = lambda v: "—" if v is None else f"{formato.numero(v, 1)} h"
PESOS = lambda v: formato.moneda(v or 0)
PORCENTAJE = lambda v: formato.porcentaje(v)
FECHA = lambda v: fechas.formatear_fecha(fechas.fecha_desde_sql(v) if isinstance(v, str) else v)
FECHA_HORA = lambda v: fechas.formatear_fecha_hora(fechas.fecha_hora_desde_sql(v)) if isinstance(v, str) else ""
TEMPERATURA = lambda v: "—" if v is None else f"{v:g} °C"


def porcentaje_de(parte: float, total: float) -> float | None:
    return None if not total else parte * 100 / total


# Causa de rechazo de una muestra según la recepción (primera regla que se cumple)
CAUSAS_RECHAZO = [
    (lambda f: f["precinto"] == "ROTO", "Precinto roto"),
    (lambda f: (f["motivo"] or "").startswith("Temperatura"), "Temperatura fuera de rango"),
    (lambda f: (f["motivo"] or "").startswith("Viabilidad"), "Viabilidad vencida"),
]


def causa_de_rechazo(fila: dict) -> str:
    return next((causa for regla, causa in CAUSAS_RECHAZO if regla(fila)), "Otra causa")


class ReporteService:
    def __init__(self, reportes: ReporteDAO, mascotas: MascotaDAO, especies: EspecieDAO):
        self._dao = reportes
        self._mascotas = mascotas
        self._especies = especies
        self._generadores = {
            "atenciones": self.atenciones_y_derivaciones,
            "rechazos": self.muestras_rechazadas,
            "tratamientos": self.tratamientos_y_vacunas_pendientes,
            "facturacion": self.facturacion_por_clinica,
            "tiempos": self.tiempos_de_muestras,
        }

    def catalogo(self) -> list[DefinicionReporte]:
        return [
            DefinicionReporte("atenciones", "Atenciones clínicas y derivaciones",
                              "Atenciones por tipo y proporción que terminó en una orden al laboratorio.",
                              "medical_services",
                              {"clinica": "Clínica", "veterinario": "Veterinario", "tipo": "Tipo de atención",
                               "especie": "Especie"}),
            DefinicionReporte("rechazos", "Muestras rechazadas por fallas en el transporte",
                              "Muestras rechazadas en la recepción del laboratorio, por causa y transportista.",
                              "report"),
            DefinicionReporte("tratamientos", "Tratamientos aplicados y vacunas pendientes",
                              "Tratamientos vigentes en el período y vacunas obligatorias adeudadas al cierre.",
                              "vaccines"),
            DefinicionReporte("facturacion", "Facturación por clínica y servicios de laboratorio",
                              "Importes facturados por concepto en cada clínica y detalle de análisis.",
                              "payments"),
            DefinicionReporte("tiempos", "Tiempo promedio de tránsito y procesamiento",
                              "Horas entre extracción, despacho, recepción y resultado de las muestras.",
                              "timer",
                              {"tipo_muestra": "Tipo de muestra", "laboratorio": "Laboratorio",
                               "clinica": "Clínica de origen", "transportista": "Transportista"}),
        ]

    def generar(self, clave: str, desde: date, hasta: date, agrupar_por: str | None = None) -> Reporte:
        if desde is None or hasta is None:
            raise ValidacionError("Indique el período del reporte.")
        if desde > hasta:
            raise ValidacionError("La fecha 'desde' no puede ser posterior a 'hasta'.")
        definicion = next(d for d in self.catalogo() if d.clave == clave)
        agrupar_por = agrupar_por or next(iter(definicion.agrupaciones), None)
        reporte = self._generadores[clave](desde, hasta, agrupar_por)
        reporte.parametros = {"Período": f"{fechas.formatear_fecha(desde)} al {fechas.formatear_fecha(hasta)}"}
        if agrupar_por:
            reporte.parametros["Agrupado por"] = definicion.agrupaciones[agrupar_por]
        return reporte

    # --- 1. Atenciones clínicas y derivaciones -------------------------------------------
    def atenciones_y_derivaciones(self, desde: date, hasta: date, agrupar_por: str) -> Reporte:
        etiqueta = dict(self.catalogo()[0].agrupaciones)[agrupar_por]
        filas = self._dao.atenciones_y_derivaciones(desde, hasta, agrupar_por)
        grupo = (lambda f: formato.etiqueta(f["grupo"])) if agrupar_por == "tipo" else (lambda f: f["grupo"])
        detalle = Seccion(f"Atenciones por {etiqueta.lower()}", [
            Columna(etiqueta), Columna("Atenciones", ENTERO, True), Columna("Consultas", ENTERO, True),
            Columna("Controles", ENTERO, True), Columna("Urgencias", ENTERO, True),
            Columna("Con derivación", ENTERO, True), Columna("% derivación", PORCENTAJE, True),
            Columna("Órdenes", ENTERO, True), Columna("Análisis solicitados", ENTERO, True)],
            [[grupo(f), f["atenciones"], f["consultas"], f["controles"], f["urgencias"], f["con_derivacion"],
              porcentaje_de(f["con_derivacion"], f["atenciones"]), f["ordenes"], f["analisis"]] for f in filas])
        total = lambda campo: sum(f[campo] or 0 for f in filas)
        analisis = self._dao.analisis_mas_solicitados(desde, hasta)
        total_analisis = sum(a["cantidad"] for a in analisis)
        ranking = Seccion("Análisis más solicitados", [
            Columna("Análisis"), Columna("Cantidad", ENTERO, True), Columna("% del total", PORCENTAJE, True)],
            [[a["analisis"], a["cantidad"], porcentaje_de(a["cantidad"], total_analisis)] for a in analisis])
        return Reporte("atenciones", "Atenciones clínicas y derivaciones",
                       "Atenciones registradas en el período y cuántas derivaron muestras al laboratorio central.",
                       indicadores=[("Atenciones", ENTERO(total("atenciones"))),
                                    ("Con derivación", ENTERO(total("con_derivacion"))),
                                    ("Tasa de derivación", PORCENTAJE(porcentaje_de(total("con_derivacion"),
                                                                                    total("atenciones")))),
                                    ("Órdenes emitidas", ENTERO(total("ordenes"))),
                                    ("Análisis solicitados", ENTERO(total("analisis")))],
                       secciones=[detalle, ranking],
                       grafico=Grafico("barras", f"Atenciones y derivaciones por {etiqueta.lower()}",
                                       [grupo(f) for f in filas],
                                       {"Atenciones": [f["atenciones"] for f in filas],
                                        "Con derivación": [f["con_derivacion"] for f in filas]}, "Cantidad"))

    # --- 2. Muestras rechazadas por fallas en el transporte --------------------------------
    def muestras_rechazadas(self, desde: date, hasta: date, _agrupar_por=None) -> Reporte:
        filas = self._dao.muestras_rechazadas_en_recepcion(desde, hasta)
        for fila in filas:
            fila["causa"] = causa_de_rechazo(fila)
            fila["entrego"] = (fila["transportistas"] or "").split(" > ")[-1]
        evaluadas = self._dao.muestras_evaluadas_en_recepcion(desde, hasta)
        por_causa = Counter(f["causa"] for f in filas)
        por_transportista = Counter(f["entrego"] for f in filas)
        detalle = Seccion("Detalle de muestras rechazadas", [
            Columna("Fecha", FECHA_HORA), Columna("Muestra"), Columna("Tipo", formato.etiqueta), Columna("Remito"),
            Columna("Origen » destino"), Columna("Transportistas"), Columna("Causa"), Columna("Detalle"),
            Columna("T° arribo", TEMPERATURA, True), Columna("Horas desde extracción", HORAS, True)],
            [[f["fecha_rechazo"], f["codigo"], f["tipo"], f["remito"], f"{f['clinica']} » {f['laboratorio']}",
              f["transportistas"], f["causa"], f["motivo"], f["temperatura_arribo_c"], f["horas_desde_extraccion"]]
             for f in filas],
            vacio="No se rechazaron muestras en la recepción durante el período.")
        causas = Seccion("Rechazos por causa", [
            Columna("Causa"), Columna("Muestras", ENTERO, True), Columna("% de los rechazos", PORCENTAJE, True)],
            [[causa, cantidad, porcentaje_de(cantidad, len(filas))] for causa, cantidad in por_causa.most_common()])
        transportistas = Seccion("Rechazos por transportista (último tramo)", [
            Columna("Transportista"), Columna("Muestras rechazadas", ENTERO, True)],
            [[t, cantidad] for t, cantidad in por_transportista.most_common()])
        principal = por_causa.most_common(1)[0][0] if por_causa else "—"
        return Reporte("rechazos", "Muestras rechazadas por fallas en el transporte",
                       "Muestras que llegaron al laboratorio y no pudieron procesarse: precinto roto, "
                       "temperatura de arribo fuera de rango o viabilidad vencida.",
                       indicadores=[("Muestras evaluadas en recepción", ENTERO(evaluadas)),
                                    ("Rechazadas", ENTERO(len(filas))),
                                    ("Tasa de rechazo", PORCENTAJE(porcentaje_de(len(filas), evaluadas))),
                                    ("Causa principal", principal)],
                       secciones=[detalle, causas, transportistas],
                       grafico=Grafico("torta", "Rechazos por causa", list(por_causa.keys()),
                                       {"Muestras": list(por_causa.values())}) if por_causa else None)

    # --- 3. Tratamientos aplicados y vacunas pendientes -------------------------------------
    def vacunas_pendientes(self, fecha: date) -> list[dict]:
        """Recorre todas las mascotas de clientes activos y evalúa el esquema obligatorio de su especie."""
        especies = {e.id: e for e in self._especies.listar()}
        datos = {f["id_mascota"]: f for f in self._dao.mascotas_de_clientes_activos()}
        aplicaciones = defaultdict(list)
        for f in self._dao.aplicaciones_de_vacunas():
            aplicaciones[f["id_mascota"]].append(AplicacionVacuna(id_vacuna=f["id_vacuna"], lote=f["lote"],
                                                                  fecha=fechas.fecha_desde_sql(f["fecha"])))
        pendientes = []
        for mascota in filter(lambda m: m.id in datos, self._mascotas.listar()):
            mascota.especie = especies.get(mascota.id_especie)
            mascota.aplicaciones = aplicaciones[mascota.id]
            for vo in mascota.vacunas_pendientes(fecha):
                exigible = vo.fecha_vencimiento(mascota)
                pendientes.append({
                    "mascota": mascota.nombre, "especie": datos[mascota.id]["especie"],
                    "cliente": datos[mascota.id]["cliente"], "telefono": datos[mascota.id]["telefono"],
                    "vacuna": vo.nombre_vacuna,
                    "situacion": "Nunca aplicada" if vo.ultima_aplicacion(mascota.aplicaciones) is None
                    else "Refuerzo vencido",
                    "exigible_desde": exigible, "dias_atraso": (fecha - exigible).days})
        return sorted(pendientes, key=lambda p: p["dias_atraso"], reverse=True)

    def tratamientos_y_vacunas_pendientes(self, desde: date, hasta: date, _agrupar_por=None) -> Reporte:
        tratamientos = self._dao.tratamientos_en_periodo(desde, hasta)
        vigente = lambda t: t["fecha_fin"] is None or fechas.fecha_desde_sql(t["fecha_fin"]) >= hasta
        corte = min(hasta, date.today())
        pendientes = self.vacunas_pendientes(corte)
        seccion_tratamientos = Seccion("Tratamientos aplicados en el período", [
            Columna("Inicio", FECHA), Columna("Fin", FECHA), Columna("Mascota"), Columna("Responsable"),
            Columna("Tratamiento"), Columna("Medicamento"), Columna("Dosis / frecuencia"), Columna("Veterinario"),
            Columna("Estado al cierre")],
            [[t["fecha_inicio"], t["fecha_fin"], f"{t['mascota']} ({t['especie']})", t["cliente"], t["descripcion"],
              t["medicamento"] or "", " · ".join(filter(None, [t["dosis"], t["frecuencia"]])), t["veterinario"],
              "Vigente" if vigente(t) else "Finalizado"] for t in tratamientos])
        seccion_vacunas = Seccion(f"Vacunas obligatorias pendientes al {fechas.formatear_fecha(corte)}", [
            Columna("Mascota"), Columna("Especie"), Columna("Responsable"), Columna("Teléfono"), Columna("Vacuna"),
            Columna("Situación"), Columna("Exigible desde", FECHA), Columna("Días de atraso", ENTERO, True)],
            [[p["mascota"], p["especie"], p["cliente"], p["telefono"], p["vacuna"], p["situacion"],
              p["exigible_desde"], p["dias_atraso"]] for p in pendientes],
            vacio="Todas las mascotas tienen el esquema obligatorio al día.")
        por_vacuna = Counter(p["vacuna"] for p in pendientes)
        return Reporte("tratamientos", "Tratamientos aplicados y vacunas pendientes",
                       "Tratamientos indicados que estuvieron vigentes en el período y control del esquema de "
                       "vacunación obligatorio de cada especie.",
                       indicadores=[("Tratamientos en el período", ENTERO(len(tratamientos))),
                                    ("Vigentes al cierre", ENTERO(sum(map(vigente, tratamientos)))),
                                    ("Mascotas con vacunas pendientes",
                                     ENTERO(len({(p["mascota"], p["cliente"]) for p in pendientes}))),
                                    ("Dosis pendientes", ENTERO(len(pendientes)))],
                       secciones=[seccion_tratamientos, seccion_vacunas],
                       grafico=Grafico("barras_h", "Dosis pendientes por vacuna", list(por_vacuna.keys()),
                                       {"Dosis pendientes": list(por_vacuna.values())}) if por_vacuna else None)

    # --- 4. Facturación por clínica y servicios de laboratorio -------------------------------
    def facturacion_por_clinica(self, desde: date, hasta: date, _agrupar_por=None) -> Reporte:
        clinicas = self._dao.facturacion_por_clinica(desde, hasta)
        laboratorio = self._dao.servicios_laboratorio_facturados(desde, hasta)
        conceptos = {"servicios": "Servicios clínicos", "analisis": "Análisis de laboratorio", "vacunas": "Vacunas",
                     "insumos": "Insumos"}
        total = lambda campo: sum(c[campo] or 0 for c in clinicas)
        fila = lambda c: [c["clinica"], c["comprobantes"], *[c[k] for k in conceptos], c["subtotal"],
                          c["total"] - c["subtotal"], c["total"]]
        totales = {"clinica": "TOTAL", **{k: total(k) for k in ("comprobantes", "subtotal", "total", *conceptos)}}
        resumen = Seccion("Facturación por clínica", [
            Columna("Clínica"), Columna("Comprobantes", ENTERO, True),
            *[Columna(etiqueta, PESOS, True) for etiqueta in conceptos.values()],
            Columna("Subtotal", PESOS, True), Columna("Recargos / descuentos", PESOS, True),
            Columna("Total facturado", PESOS, True)],
            [fila(c) for c in clinicas] + ([fila(totales)] if clinicas else []))
        total_lab_clinica = defaultdict(float)
        for item in laboratorio:
            total_lab_clinica[item["clinica"]] += item["importe"]
        detalle_lab = Seccion("Servicios de laboratorio facturados", [
            Columna("Clínica"), Columna("Análisis"), Columna("Cantidad", ENTERO, True), Columna("Importe", PESOS, True),
            Columna("% del laboratorio en la clínica", PORCENTAJE, True)],
            [[i["clinica"], i["analisis"], i["cantidad"], i["importe"],
              porcentaje_de(i["importe"], total_lab_clinica[i["clinica"]])] for i in laboratorio])
        return Reporte("facturacion", "Facturación por clínica y servicios de laboratorio",
                       "Importes de los comprobantes emitidos, desglosados por concepto. Los recargos y descuentos "
                       "surgen de la estrategia de tarifa (consulta, control o urgencia).",
                       indicadores=[("Total facturado", PESOS(total("total"))),
                                    ("Comprobantes", ENTERO(total("comprobantes"))),
                                    ("Ticket promedio", PESOS(total("total") / total("comprobantes")
                                                              if total("comprobantes") else 0)),
                                    ("Participación del laboratorio",
                                     PORCENTAJE(porcentaje_de(total("analisis"), total("subtotal"))))],
                       secciones=[resumen, detalle_lab],
                       grafico=Grafico("barras_apiladas", "Facturación por clínica y concepto",
                                       [c["clinica"] for c in clinicas],
                                       {etiqueta: [c[k] or 0 for c in clinicas] for k, etiqueta in conceptos.items()},
                                       "Pesos") if clinicas else None)

    # --- 5. Tiempo promedio de tránsito y procesamiento -------------------------------------
    def tiempos_de_muestras(self, desde: date, hasta: date, agrupar_por: str) -> Reporte:
        etiqueta = dict(self.catalogo()[4].agrupaciones)[agrupar_por]
        filas = self._dao.tiempos_de_muestras(desde, hasta, agrupar_por)
        grupo = (lambda f: formato.etiqueta(f["grupo"])) if agrupar_por == "tipo_muestra" else \
            (lambda f: f["grupo"] or "Sin dato")

        def promedio_ponderado(campo: str, peso: str) -> float | None:
            pares = [(f[campo], f[peso]) for f in filas if f[campo] is not None and f[peso]]
            total_peso = sum(p for _, p in pares)
            return sum(v * p for v, p in pares) / total_peso if total_peso else None

        seccion = Seccion(f"Tiempos por {etiqueta.lower()}", [
            Columna(etiqueta), Columna("Recibidas", ENTERO, True), Columna("Analizadas", ENTERO, True),
            Columna("Extracción a despacho", HORAS, True), Columna("Tránsito promedio", HORAS, True),
            Columna("Tránsito máximo", HORAS, True), Columna("Procesamiento promedio", HORAS, True),
            Columna("Extracción a resultado", HORAS, True)],
            [[grupo(f), f["recibidas"], f["analizadas"], f["espera_despacho"], f["transito"], f["transito_max"],
              f["procesamiento"], f["total"]] for f in filas])
        return Reporte("tiempos", "Tiempo promedio de tránsito y procesamiento",
                       "Calculado sobre el historial inmutable de estados de cada muestra: tránsito = de En tránsito a "
                       "Recibida; procesamiento = de Recibida a Analizada.",
                       indicadores=[("Muestras recibidas", ENTERO(sum(f["recibidas"] for f in filas))),
                                    ("Tránsito promedio", HORAS(promedio_ponderado("transito", "recibidas"))),
                                    ("Procesamiento promedio", HORAS(promedio_ponderado("procesamiento", "analizadas"))),
                                    ("Extracción a resultado", HORAS(promedio_ponderado("total", "analizadas")))],
                       secciones=[seccion],
                       grafico=Grafico("barras", f"Horas promedio por {etiqueta.lower()}", [grupo(f) for f in filas],
                                       {"Tránsito": [f["transito"] or 0 for f in filas],
                                        "Procesamiento": [f["procesamiento"] or 0 for f in filas]},
                                       "Horas") if filas else None)

    # --- Tablero de inicio -------------------------------------------------------------------
    def tablero(self, hoy: date | None = None) -> dict:
        hoy = hoy or date.today()
        indicadores = self._dao.indicadores_tablero(hoy)
        indicadores["vacunas_pendientes"] = len(self.vacunas_pendientes(hoy))
        return indicadores
