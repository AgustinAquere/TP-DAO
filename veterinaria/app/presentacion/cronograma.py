"""Semana de un veterinario, con el mismo esquema que un calendario: horas a la izquierda y un día por columna."""
from collections.abc import Callable
from datetime import date, datetime, timedelta

import flet as ft

from app import config
from app.presentacion.componentes import COLOR_PRIMARIO, COLORES_ESTADO
from app.utils import fechas

ALTO_MEDIA_HORA = 42
ANCHO_HORA = 56
DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")

_INICIO = datetime.combine(date.min, config.JORNADA_INICIO)
_FIN = datetime.combine(date.min, config.JORNADA_FIN)
_MINUTOS_JORNADA = int((_FIN - _INICIO).total_seconds() // 60)
_FRANJAS = _MINUTOS_JORNADA // config.INTERVALO_TURNOS_MIN
ALTO_JORNADA = _FRANJAS * ALTO_MEDIA_HORA


def cronograma(lunes: date, turnos: list[dict], huecos: dict[date, list[datetime]], dia_activo: date,
               horario_elegido: str | None, turno_abierto: int | None, bloquear: dict[int, ft.Container],
               al_elegir_dia: Callable[[date], None], al_elegir_hueco: Callable[[datetime], None],
               al_elegir_turno: Callable[[dict], None]) -> ft.Control:
    """Grilla de lunes a domingo. `bloquear` queda con el bloque de cada turno, para remarcarlo al abrirlo."""
    dias = [lunes + timedelta(days=i) for i in range(7)]
    por_dia: dict[str, list[dict]] = {}
    for turno in turnos:
        por_dia.setdefault(turno["fecha_hora_inicio"][:10], []).append(turno)
    cuerpo = ft.Row([
        _horas(),
        *[_columna(dia, por_dia.get(dia.isoformat(), []), huecos.get(dia, []), dia == dias[-1],
                   horario_elegido, turno_abierto, bloquear, al_elegir_hueco, al_elegir_turno) for dia in dias],
    ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.START)
    return ft.Column([
        ft.Row([ft.Container(width=ANCHO_HORA),
                *[_encabezado_dia(dia, dia_activo, dia == dias[-1], al_elegir_dia) for dia in dias]],
               spacing=0),
        ft.Column([cuerpo], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0),
    ], spacing=0, expand=True)


def _encabezado_dia(dia: date, dia_activo: date, ultima: bool, al_elegir_dia: Callable[[date], None]) -> ft.Container:
    hoy = dia == date.today()
    numero = ft.Text(str(dia.day), size=16, weight=ft.FontWeight.W_600,
                     color=ft.Colors.WHITE if hoy else ft.Colors.ON_SURFACE)
    anillo = None if hoy or dia != dia_activo else ft.Border.all(1.5, COLOR_PRIMARIO)
    return ft.Container(
        ft.Column([
            ft.Text(DIAS[dia.weekday()], size=11,
                    color=COLOR_PRIMARIO if hoy else ft.Colors.ON_SURFACE_VARIANT),
            ft.Container(numero, width=32, height=32, border_radius=16, alignment=ft.Alignment.CENTER,
                         bgcolor=COLOR_PRIMARIO if hoy else None, border=anillo),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
        expand=True, padding=ft.Padding.only(top=2, bottom=8), ink=True,
        on_click=lambda e, d=dia: al_elegir_dia(d), border=_borde_dia(ultima))


def _horas() -> ft.Stack:
    marcas = []
    for i in range(0, _FRANJAS + 1, 2):
        hora = _INICIO + timedelta(minutes=i * config.INTERVALO_TURNOS_MIN)
        marcas.append(ft.Container(
            ft.Text(hora.strftime("%H:%M"), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
            top=min(max(i * ALTO_MEDIA_HORA - 8, 0), ALTO_JORNADA - 14), left=0, right=6, height=16,
            alignment=ft.Alignment.CENTER_RIGHT))
    return ft.Stack(marcas, width=ANCHO_HORA, height=ALTO_JORNADA)


def _columna(dia: date, turnos: list[dict], huecos: list[datetime], ultima: bool, horario_elegido: str | None,
             turno_abierto: int | None, bloquear: dict[int, ft.Container],
             al_elegir_hueco: Callable[[datetime], None], al_elegir_turno: Callable[[dict], None]) -> ft.Container:
    controles: list[ft.Control] = []
    for i in range(_FRANJAS):
        fuerte = i % 2 == 0
        controles.append(ft.Container(
            top=i * ALTO_MEDIA_HORA, left=0, right=0, height=ALTO_MEDIA_HORA,
            border=ft.Border.only(bottom=ft.BorderSide(
                1, ft.Colors.OUTLINE_VARIANT if fuerte else ft.Colors.with_opacity(0.45, ft.Colors.OUTLINE_VARIANT)))))
    for inicio in huecos:
        indice = _franja(inicio)
        if indice is None:
            continue
        elegido = inicio.isoformat() == horario_elegido
        controles.append(ft.Container(
            top=indice * ALTO_MEDIA_HORA, left=0, right=0, height=ALTO_MEDIA_HORA,
            bgcolor=_fondo_hueco(elegido, False),
            border=ft.Border.all(1, COLOR_PRIMARIO) if elegido else None,
            tooltip=f"Reservar a las {inicio:%H:%M}",
            on_click=lambda e, h=inicio: al_elegir_hueco(h),
            on_hover=lambda e, marcado=elegido: _resaltar_hueco(e, marcado)))
    for turno in turnos:
        if turno["estado"] == "CANCELADO":
            continue
        bloque = _bloque(turno, turno["id_turno"] == turno_abierto, al_elegir_turno)
        if bloque is not None:
            bloquear[turno["id_turno"]] = bloque
            controles.append(bloque)
    controles.extend(_marcas_ahora(dia))
    return ft.Container(
        ft.Stack(controles, height=ALTO_JORNADA),
        expand=True, height=ALTO_JORNADA, clip_behavior=ft.ClipBehavior.HARD_EDGE,
        bgcolor=ft.Colors.with_opacity(0.05, COLOR_PRIMARIO) if dia == date.today() else None,
        border=_borde_dia(ultima))


def _bloque(turno: dict, seleccionado: bool, al_elegir_turno: Callable[[dict], None]) -> ft.Container | None:
    inicio = fechas.fecha_hora_desde_sql(turno["fecha_hora_inicio"])
    indice = _franja(inicio)
    if indice is None:
        return None
    alto = turno["duracion_min"] / config.INTERVALO_TURNOS_MIN * ALTO_MEDIA_HORA
    color = COLORES_ESTADO.get(turno["estado"], COLOR_PRIMARIO)
    hora_ini, hora_fin = turno["fecha_hora_inicio"][11:16], turno["fecha_hora_fin"][11:16]
    textos = [ft.Text(turno["mascota"], size=12, weight=ft.FontWeight.W_600, color=color,
                      max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)]
    if alto >= 38:
        textos.append(ft.Text(f"{hora_ini} – {hora_fin}", size=11, color=color, max_lines=1,
                              overflow=ft.TextOverflow.ELLIPSIS))
    bloque = ft.Container(
        ft.Row([ft.Container(width=3, bgcolor=color, border_radius=2),
                ft.Column(textos, spacing=0, expand=True)],
               spacing=6, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
        top=indice * ALTO_MEDIA_HORA + 1, left=3, right=4, height=max(alto - 3, 18),
        bgcolor=ft.Colors.with_opacity(0.18, color),
        border=_borde(color, seleccionado), border_radius=6,
        padding=ft.Padding.only(right=4, top=2, bottom=2), clip_behavior=ft.ClipBehavior.HARD_EDGE,
        tooltip=f"{turno['mascota']} · {hora_ini}–{hora_fin} · {turno['responsable']}",
        ink=True, on_click=lambda e, t=turno: al_elegir_turno(t), data=color)
    return bloque


def _borde_dia(ultima: bool) -> ft.Border:
    lado = ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
    return ft.Border.only(left=lado, right=lado if ultima else None)


def _borde(color, seleccionado: bool) -> ft.Border:
    return ft.Border.all(2 if seleccionado else 1, color if seleccionado else ft.Colors.with_opacity(0.35, color))


def _marcas_ahora(dia: date) -> list[ft.Control]:
    """Punto y línea de la hora actual, como en un calendario, solo en la columna de hoy."""
    if dia != date.today():
        return []
    indice = _franja(fechas.ahora())
    if indice is None:
        return []
    top = indice * ALTO_MEDIA_HORA
    return [
        ft.Container(top=max(top - 3, 0), left=0, width=8, height=8, border_radius=4, bgcolor=ft.Colors.RED_600,
                     ignore_interactions=True),
        ft.Container(top=top, left=4, right=0, height=2, bgcolor=ft.Colors.RED_600, ignore_interactions=True),
    ]


def _franja(momento: datetime | None) -> float | None:
    """Índice de media hora desde el inicio de la jornada, o None si cae fuera."""
    if momento is None:
        return None
    minutos = (momento.hour * 60 + momento.minute) - (config.JORNADA_INICIO.hour * 60 + config.JORNADA_INICIO.minute)
    if minutos < 0 or minutos >= _MINUTOS_JORNADA:
        return None
    return minutos / config.INTERVALO_TURNOS_MIN


def _fondo_hueco(elegido: bool, hover: bool):
    """El horario elegido y el que está bajo el mouse se tiñen; el resto queda como grilla vacía."""
    if elegido:
        return ft.Colors.with_opacity(0.22, COLOR_PRIMARIO)
    if hover:
        return ft.Colors.with_opacity(0.14, COLOR_PRIMARIO)
    return ft.Colors.with_opacity(0, COLOR_PRIMARIO)


def _resaltar_hueco(e, elegido: bool) -> None:
    if elegido:
        return
    e.control.bgcolor = _fondo_hueco(False, e.data in (True, "true"))
    e.control.update()
