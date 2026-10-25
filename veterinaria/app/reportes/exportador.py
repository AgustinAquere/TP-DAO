"""Exportación de reportes a PDF (ReportLab + gráfico de matplotlib) y a CSV, y PDF del comprobante."""
import csv
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import config
from app.reportes.graficos import generar_png
from app.reportes.modelo import Reporte, Seccion
from app.utils import formato

COLOR_PRIMARIO = colors.HexColor("#0F766E")
COLOR_FILA_PAR = colors.HexColor("#F0FDFA")

# Fuente TrueType con Unicode completo (°, µ, →): se reutiliza la DejaVu que trae matplotlib
_DIR_FUENTES = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DejaVu", str(_DIR_FUENTES / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_DIR_FUENTES / "DejaVuSans-Bold.ttf")))
registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")
FUENTE, FUENTE_NEGRITA = "DejaVu", "DejaVu-Bold"


def _ruta_salida(nombre: str, extension: str) -> Path:
    config.DIR_SALIDAS.mkdir(parents=True, exist_ok=True)
    return config.DIR_SALIDAS / f"{nombre}_{datetime.now():%Y%m%d_%H%M%S}.{extension}"


def _estilos():
    estilos = getSampleStyleSheet()
    for nombre in ("BodyText", "Title", "Heading2", "Heading3"):
        estilos[nombre].fontName = FUENTE_NEGRITA if nombre != "BodyText" else FUENTE
    estilos.add(ParagraphStyle("Celda", parent=estilos["BodyText"], fontSize=7.5, leading=9))
    estilos.add(ParagraphStyle("CeldaEncabezado", parent=estilos["BodyText"], fontSize=7.5, leading=9,
                               textColor=colors.white, fontName=FUENTE_NEGRITA))
    estilos.add(ParagraphStyle("Pie", parent=estilos["BodyText"], fontSize=7, textColor=colors.grey))
    return estilos


def _tabla(seccion: Seccion, ancho_disponible: float, estilos) -> Table:
    encabezados = [Paragraph(escape(t), estilos["CeldaEncabezado"]) for t in seccion.encabezados()]
    filas = [[Paragraph(escape(valor), estilos["Celda"]) for valor in fila] for fila in seccion.filas_formateadas()]
    tabla = Table([encabezados] + filas, repeatRows=1, colWidths=[ancho_disponible / len(encabezados)] * len(encabezados))
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARIO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    estilo += [("BACKGROUND", (0, i), (-1, i), COLOR_FILA_PAR) for i in range(2, len(filas) + 1, 2)]
    tabla.setStyle(TableStyle(estilo))
    return tabla


def exportar_pdf(reporte: Reporte) -> Path:
    ruta = _ruta_salida(reporte.clave, "pdf")
    estilos = _estilos()
    documento = SimpleDocTemplate(str(ruta), pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                                  topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=reporte.titulo)
    ancho = documento.width
    elementos = [Paragraph(config.APP_TITULO, estilos["Pie"]),
                 Paragraph(reporte.titulo, estilos["Title"]),
                 Paragraph(reporte.descripcion, estilos["BodyText"]),
                 Paragraph(" · ".join(f"<b>{k}:</b> {v}" for k, v in reporte.parametros.items()), estilos["BodyText"]),
                 Spacer(1, 8)]
    if reporte.indicadores:
        indicadores = Table([[Paragraph(f"<b>{v}</b><br/><font size=7>{k}</font>", estilos["BodyText"])
                              for k, v in reporte.indicadores]],
                            colWidths=[ancho / len(reporte.indicadores)] * len(reporte.indicadores))
        indicadores.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, COLOR_PRIMARIO),
                                         ("INNERGRID", (0, 0), (-1, -1), 0.25, COLOR_PRIMARIO),
                                         ("BACKGROUND", (0, 0), (-1, -1), COLOR_FILA_PAR)]))
        elementos += [indicadores, Spacer(1, 10)]
    if reporte.grafico and reporte.grafico.etiquetas:
        elementos += [Image(BytesIO(generar_png(reporte.grafico)), width=17 * cm, height=7.6 * cm), Spacer(1, 10)]
    for seccion in reporte.secciones:
        elementos.append(Paragraph(seccion.titulo, estilos["Heading3"]))
        elementos.append(_tabla(seccion, ancho, estilos) if seccion.filas
                         else Paragraph(seccion.vacio, estilos["BodyText"]))
        elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(f"Generado el {datetime.now():%d/%m/%Y %H:%M}", estilos["Pie"]))
    documento.build(elementos)
    return ruta


def exportar_csv(reporte: Reporte) -> Path:
    """Un archivo con todas las secciones, separadas por una línea en blanco (separador ';' para Excel)."""
    ruta = _ruta_salida(reporte.clave, "csv")
    with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")
        escritor.writerow([reporte.titulo])
        for clave, valor in reporte.parametros.items():
            escritor.writerow([clave, valor])
        for seccion in reporte.secciones:
            escritor.writerow([])
            escritor.writerow([seccion.titulo])
            escritor.writerow(seccion.encabezados())
            escritor.writerows([["" if v is None else v for v in fila] for fila in seccion.filas])
    return ruta


def exportar_comprobante_pdf(comprobante, datos: dict, descripcion_tarifa: str) -> Path:
    """PDF del comprobante de atención. `datos` trae los nombres de cliente, clínica y mascota."""
    ruta = _ruta_salida(f"comprobante_{comprobante.numero}", "pdf")
    estilos = _estilos()
    documento = SimpleDocTemplate(str(ruta), pagesize=A4, title=f"Comprobante {comprobante.numero}")
    filas = [["Descripción", "Tipo", "Cant.", "P. unitario", "Importe"]] + [
        [i.descripcion, formato.etiqueta(i.tipo), str(i.cantidad), formato.moneda(i.precio_unitario),
         formato.moneda(i.importe())] for i in comprobante.items]
    tabla = Table(filas, colWidths=[7.5 * cm, 3.5 * cm, 1.5 * cm, 2.6 * cm, 2.6 * cm])
    tabla.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARIO),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTNAME", (0, 0), (-1, -1), FUENTE),
                               ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA),
                               ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                               ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1"))]))
    totales = Table([["Subtotal", formato.moneda(comprobante.subtotal())],
                     ["Recargo / descuento", formato.moneda(comprobante.ajuste())],
                     ["TOTAL", formato.moneda(comprobante.total())]], colWidths=[4 * cm, 3.5 * cm], hAlign="RIGHT")
    totales.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), FUENTE),
                                 ("FONTNAME", (0, 2), (-1, 2), FUENTE_NEGRITA),
                                 ("LINEABOVE", (0, 2), (-1, 2), 0.75, COLOR_PRIMARIO)]))
    elementos = [
        Paragraph(f"<b>{datos['clinica']}</b>", estilos["Heading2"]),
        Paragraph(f"Comprobante de atención N.º <b>{comprobante.numero}</b> — "
                  f"{comprobante.fecha_emision:%d/%m/%Y %H:%M}", estilos["BodyText"]),
        Paragraph(f"Cliente: {datos['cliente']} (DNI {datos['dni']}) · Paciente: {datos['mascota']}",
                  estilos["BodyText"]),
        Paragraph(f"Tarifa aplicada: {descripcion_tarifa}", estilos["BodyText"]),
        Spacer(1, 12), tabla, Spacer(1, 10), totales,
    ]
    documento.build(elementos)
    return ruta
