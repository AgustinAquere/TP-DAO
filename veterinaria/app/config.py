"""Configuración general de la aplicación (rutas, parámetros de negocio y plantillas)."""
from datetime import date, time
from pathlib import Path

# --- Rutas -------------------------------------------------------------------
DIR_APP = Path(__file__).resolve().parent
DIR_BASE = DIR_APP.parent
DIR_BD = DIR_BASE / "bd"
RUTA_BD = DIR_BD / "veterinaria.db"
RUTA_ESQUEMA = DIR_APP / "persistencia" / "schema.sql"
DIR_SALIDAS = DIR_BASE / "salidas"
RUTA_REGISTRO = DIR_BASE / "veterinaria.log"   # se usa cuando la app se inicia sin consola

APP_TITULO = "VetRed · Red de clínicas y laboratorio"

# --- Agenda de turnos --------------------------------------------------------
JORNADA_INICIO = time(8, 0)
JORNADA_FIN = time(20, 0)
INTERVALO_TURNOS_MIN = 30
DURACIONES_TURNO_MIN = (15, 30, 45, 60)

# --- Atención clínica y vacunación -------------------------------------------
# Peso máximo admisible en animales domésticos / pequeños animales (kg)
PESO_MAXIMO_KG = 150.0

# Lotes de vacunas con su fecha de vencimiento (código, vencimiento), sin manejo de stock
# para conservar el alcance del DER. Se ordenan/filtran por vigencia a la fecha de atención.
LOTES_VACUNA: dict[str, list[tuple[str, date]]] = {
    "Séxtuple canina": [
        ("L09412", date(2026, 3, 31)),
        ("L24810", date(2027, 6, 30)),
        ("L25340", date(2028, 2, 29)),
        ("L25915", date(2028, 9, 30)),
    ],
    "Antirrábica": [
        ("L09380", date(2026, 4, 30)),
        ("L24605", date(2027, 5, 31)),
        ("L25190", date(2028, 1, 31)),
        ("L25820", date(2028, 8, 31)),
    ],
    "Triple felina": [
        ("L24722", date(2027, 7, 31)),
        ("L25410", date(2028, 3, 31)),
    ],
    "Leucemia felina": [
        ("L24930", date(2027, 8, 31)),
        ("L25508", date(2028, 4, 30)),
    ],
    "Tos de las perreras": [
        ("L24885", date(2027, 7, 31)),
        ("L25612", date(2028, 5, 31)),
    ],
    "Mixomatosis": [
        ("L24590", date(2027, 4, 30)),
        ("L25275", date(2028, 2, 29)),
    ],
}
LOTES_VACUNA_GENERICOS: list[tuple[str, date]] = [
    ("L25100", date(2027, 12, 31)),
    ("L25750", date(2028, 6, 30)),
]

# --- Facturación (patrón Strategy) -------------------------------------------
# Servicio clínico que se factura según el tipo de atención (códigos de servicio_clinico)
SERVICIO_POR_TIPO_ATENCION = {
    "CONSULTA": "CONS",
    "CONTROL": "CTRL",
    "URGENCIA": "URG",
}
PRECIO_SUGERIDO_VACUNA = 9500.0
TARIFA_CONTROL_DESCUENTO_PCT = 20.0      # descuento sobre servicios clínicos
TARIFA_URGENCIA_RECARGO_PCT = 30.0       # recargo sobre servicios clínicos
TARIFA_URGENCIA_RECARGO_NOCTURNO_PCT = 25.0
HORARIO_NOCTURNO = (time(20, 0), time(8, 0))  # desde / hasta

# --- Laboratorio -------------------------------------------------------------
# Plantillas de parámetros sugeridos para cargar resultados, por código de análisis:
# (parámetro, unidad, valor de referencia mínimo, valor de referencia máximo)
PLANTILLAS_RESULTADO = {
    "HEMO": [
        ("Hematocrito", "%", 37.0, 55.0),
        ("Hemoglobina", "g/dL", 12.0, 18.0),
        ("Glóbulos rojos", "x10^6/µL", 5.5, 8.5),
        ("Leucocitos", "x10^3/µL", 6.0, 17.0),
        ("Plaquetas", "x10^3/µL", 200.0, 500.0),
    ],
    "BIOQ": [
        ("Glucosa", "mg/dL", 70.0, 110.0),
        ("Urea", "mg/dL", 20.0, 50.0),
        ("Creatinina", "mg/dL", 0.5, 1.5),
        ("ALT (GPT)", "U/L", 10.0, 100.0),
        ("Fosfatasa alcalina", "U/L", 20.0, 150.0),
    ],
    "ORIN": [
        ("Densidad", "", 1.015, 1.045),
        ("pH", "", 5.5, 7.5),
        ("Proteínas", "mg/dL", 0.0, 30.0),
    ],
    "COPRO": [
        ("Huevos de parásitos", "hpg", 0.0, 0.0),
        ("Ooquistes", "opg", 0.0, 0.0),
    ],
    "T4": [
        ("T4 total", "µg/dL", 1.0, 4.0),
    ],
    "CULT": [
        ("Recuento bacteriano", "UFC/mL", 0.0, 1000.0),
    ],
    "HISTO": [
        ("Índice mitótico", "mitosis/10 CAP", 0.0, 2.0),
    ],
    "PCRP": [
        ("Carga viral parvovirus", "copias/µL", 0.0, 0.0),
    ],
}
