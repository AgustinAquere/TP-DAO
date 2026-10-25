"""Formatos de presentación de números e importes (convención argentina)."""


def moneda(valor: float | None) -> str:
    """12345.5 -> '$ 12.345,50'."""
    if valor is None:
        return ""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {texto}"


def numero(valor: float | None, decimales: int = 1) -> str:
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto


def porcentaje(valor: float | None, decimales: int = 1) -> str:
    return "—" if valor is None else f"{numero(valor, decimales)} %"


# Valores de enumeración cuya etiqueta lleva tilde
_ETIQUETAS = {
    "EXTRAIDA": "Extraída", "EN_TRANSITO": "En tránsito", "EN_PREPARACION": "En preparación",
    "SERVICIO_CLINICO": "Servicio clínico", "ANALISIS_LABORATORIO": "Análisis de laboratorio",
}


def etiqueta(valor) -> str:
    """Texto legible para un valor de enumeración: 'MATERIA_FECAL' -> 'Materia fecal'."""
    texto = str(getattr(valor, "value", valor) or "")
    return _ETIQUETAS.get(texto, texto.replace("_", " ").capitalize())
