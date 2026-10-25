"""Genera la imagen PNG del gráfico de un reporte con matplotlib (sin ventana: backend Agg)."""
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.reportes.modelo import Grafico  # noqa: E402

PALETA = ["#0F766E", "#F59E0B", "#6366F1", "#E11D48", "#0EA5E9", "#84CC16"]


def _barras(ax, g: Grafico, apiladas: bool = False) -> None:
    cantidad = len(g.series)
    ancho = 0.8 if apiladas else 0.8 / max(cantidad, 1)
    posiciones = range(len(g.etiquetas))
    base = [0.0] * len(g.etiquetas)
    for i, (nombre, valores) in enumerate(g.series.items()):
        if apiladas:
            ax.bar(posiciones, valores, ancho, bottom=base, label=nombre, color=PALETA[i % len(PALETA)])
            base = [b + v for b, v in zip(base, valores)]
        else:
            desplazadas = [p - 0.4 + ancho * (i + 0.5) for p in posiciones]
            ax.bar(desplazadas, valores, ancho, label=nombre, color=PALETA[i % len(PALETA)])
    ax.set_xticks(list(posiciones))
    ax.set_xticklabels(g.etiquetas, rotation=20 if len(g.etiquetas) > 3 else 0, ha="right" if len(g.etiquetas) > 3 else "center")
    ax.set_ylabel(g.eje_y)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    if cantidad > 1:
        ax.legend(frameon=False)


def _barras_horizontales(ax, g: Grafico) -> None:
    nombre, valores = next(iter(g.series.items()))
    ax.barh(g.etiquetas, valores, color=PALETA[0])
    ax.invert_yaxis()
    ax.set_xlabel(nombre)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.3)


def _torta(ax, g: Grafico) -> None:
    _, valores = next(iter(g.series.items()))
    ax.pie(valores, labels=g.etiquetas, autopct="%1.0f%%", colors=PALETA[:len(valores)], startangle=90,
           wedgeprops={"linewidth": 1, "edgecolor": "white"})
    ax.axis("equal")


_DIBUJANTES = {
    "barras": _barras,
    "barras_apiladas": lambda ax, g: _barras(ax, g, apiladas=True),
    "barras_h": _barras_horizontales,
    "torta": _torta,
}


def generar_png(grafico: Grafico, ancho: float = 8, alto: float = 3.6) -> bytes:
    figura, ax = plt.subplots(figsize=(ancho, alto), dpi=110)
    try:
        _DIBUJANTES[grafico.tipo](ax, grafico)
        ax.set_title(grafico.titulo, fontsize=11, fontweight="bold")
        figura.tight_layout()
        buffer = BytesIO()
        figura.savefig(buffer, format="png")
        return buffer.getvalue()
    finally:
        plt.close(figura)
