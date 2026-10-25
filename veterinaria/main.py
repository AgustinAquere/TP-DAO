"""Punto de entrada de la aplicación.

    python main.py                    # aplicación de escritorio
    python main.py --web              # en el navegador (http://localhost:8550)
    python main.py --reiniciar-datos  # borra la base y vuelve a cargar los datos de ejemplo

También se inicia con doble clic en iniciar.bat (Windows).
"""
import argparse
import logging
import sys

import flet as ft

from app import config
from app.persistencia.conexion import ConexionBD
from app.persistencia.inicializador import base_vacia, crear_esquema
from app.persistencia.semilla import cargar_datos_de_ejemplo
from app.presentacion.app import VeterinariaApp
from app.servicios.contenedor import Servicios


def preparar_base(reiniciar: bool, con_ejemplos: bool) -> Servicios:
    if reiniciar and config.RUTA_BD.exists():
        config.RUTA_BD.unlink()
    conexion = ConexionBD(config.RUTA_BD)
    if crear_esquema(conexion):
        logging.info("Base de datos creada en %s", config.RUTA_BD)
    servicios = Servicios(conexion)
    if con_ejemplos and base_vacia(conexion):
        cargar_datos_de_ejemplo(servicios)
        logging.info("Datos de ejemplo cargados")
    return servicios


def configurar_registro() -> None:
    """Sin consola (pythonw, al iniciar con doble clic) no existen sys.stdout ni sys.stderr: se redirigen
    a un archivo para que las bibliotecas que escriben en ellos funcionen y los errores queden registrados."""
    if sys.stdout is None or sys.stderr is None:
        archivo = open(config.RUTA_REGISTRO, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - vive con el proceso
        sys.stdout, sys.stderr = sys.stdout or archivo, sys.stderr or archivo
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description=config.APP_TITULO)
    parser.add_argument("--web", action="store_true", help="abrir la aplicación en el navegador")
    parser.add_argument("--puerto", type=int, default=8550, help="puerto del modo web (por defecto 8550)")
    parser.add_argument("--reiniciar-datos", action="store_true", help="borrar la base y recargar los datos de ejemplo")
    parser.add_argument("--sin-datos-ejemplo", action="store_true", help="iniciar con la base vacía")
    argumentos = parser.parse_args()
    configurar_registro()

    servicios = preparar_base(argumentos.reiniciar_datos, not argumentos.sin_datos_ejemplo)

    def iniciar(page: ft.Page) -> None:
        VeterinariaApp(page, servicios)

    if argumentos.web:
        ft.run(iniciar, view=ft.AppView.WEB_BROWSER, port=argumentos.puerto)
    else:
        ft.run(iniciar)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("La aplicación se cerró por un error inesperado")
        raise
