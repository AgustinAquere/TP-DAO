# VetRed — Red de clínicas veterinarias y derivación a laboratorio

TP Integrador DAO 2026 · Tema 2. Aplicación de escritorio en **Python 3.11 o superior** (probada con 3.14) con **SQLite** (módulo `sqlite3`)
y una interfaz gráfica en **Flet 1.0**. Implementa los 7 procesos obligatorios, las 5 validaciones de negocio,
los 5 reportes sugeridos y los patrones **State**, **Strategy**, **Iterator**, **Singleton** y **DAO**, siguiendo
los diagramas de clases y el DER de la carpeta `Diagramas/`.

## Instalación y ejecución

### Con doble clic (Windows)

Hacer doble clic en **`iniciar.bat`**. La primera vez crea el entorno virtual `.venv` e instala las dependencias
(requiere internet y Python 3.11 o superior instalado); las siguientes solo abre la aplicación, sin ventana de
consola. Si `requirements.txt` cambia, las dependencias se actualizan solas en el próximo inicio.
Para tenerlo en el escritorio: clic derecho en `iniciar.bat` › *Enviar a* › *Escritorio (crear acceso directo)*.

Como la aplicación corre sin consola, sus mensajes y cualquier error quedan en `veterinaria.log`.

### Desde la terminal

```bash
cd veterinaria
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell (en Linux/macOS: source .venv/bin/activate)
python -m pip install -r requirements.txt
```

```bash
python main.py                    # aplicación de escritorio
python main.py --web              # en el navegador (http://localhost:8550)
python main.py --reiniciar-datos  # borra la base y vuelve a cargar los datos de ejemplo
python main.py --sin-datos-ejemplo
```

* La primera vez se crea `bd/veterinaria.db` con el esquema del DER (`app/persistencia/schema.sql`) y se cargan
  datos de ejemplo de los últimos ~75 días, para que todos los procesos y reportes tengan contenido.
* En el modo escritorio, Flet descarga su cliente gráfico la primera vez que se ejecuta (requiere internet).
  El modo `--web` usa el mismo código y no necesita esa descarga.
* Los PDF y CSV generados (reportes y comprobantes) se guardan en `salidas/`.

### Pruebas automáticas

```bash
python -m pytest
```

33 pruebas: ciclo de vida de muestra y remito (State), historial inmutable (Iterator), estrategias de tarifa,
superposición de turnos, esquema de vacunas y los servicios completos contra una base SQLite en memoria
(incluidos los triggers de validación del esquema).

## Arquitectura en capas

```
presentacion (Flet)  ──►  servicios (reglas de negocio)  ──►  persistencia (DAO + Singleton)  ──►  SQLite
                                  │                                   │
                                  └──────────────►  dominio  ◄────────┘
```

La interfaz solo conoce el contenedor de servicios (`app/servicios/contenedor.py`); no contiene SQL ni reglas
de negocio. El dominio no depende ni de la base ni de la interfaz, por eso se puede probar de forma aislada.

```
veterinaria/
├── iniciar.bat                  # inicio con doble clic (prepara el entorno la primera vez)
├── main.py                      # punto de entrada (argumentos de línea de comandos)
├── requirements.txt
├── app/
│   ├── config.py                # rutas, jornada de turnos, tarifas, plantillas de resultados
│   ├── dominio/                 # entidades y reglas (dataclasses + ABC)
│   │   ├── personas.py          # Persona (abstracta) → Cliente, Veterinario, Bioquimico
│   │   ├── mascota.py           # Especie, Mascota, HistoriaClinica (iterable)
│   │   ├── vacunas.py           # Vacuna, VacunaObligatoria (esquema), AplicacionVacuna
│   │   ├── turnos.py            # Turno, Agenda (sin superposiciones)
│   │   ├── atencion.py          # Atencion, Tratamiento
│   │   ├── derivacion.py        # TipoAnalisis, OrdenDerivacion, AnalisisSolicitado
│   │   ├── muestra.py           # Muestra (contexto State)
│   │   ├── estados_muestra.py   # Extraida, Empaquetada, EnTransito, Recibida, Analizada, Rechazada
│   │   ├── historial.py         # CambioEstado (frozen), HistorialEstados, IteradorHistorial
│   │   ├── remito.py            # RemitoBiologico (contexto State)
│   │   ├── estados_remito.py    # EnPreparacion, Precintado, EnTransito, Recibido, Rechazado
│   │   ├── envio.py             # Conservadora, PrecintoSanitario, TramoEnvio
│   │   ├── laboratorio.py       # RecepcionLaboratorio, ResultadoAnalisis, DetalleResultado
│   │   ├── facturacion.py       # ServicioClinico, ItemComprobante, ComprobanteAtencion
│   │   ├── tarifas.py           # EstrategiaTarifa → TarifaConsulta, TarifaControl, TarifaUrgencia
│   │   ├── organizaciones.py    # Clinica, LaboratorioCentral, Transportista
│   │   ├── enums.py · excepciones.py
│   ├── persistencia/
│   │   ├── conexion.py          # ConexionBD (Singleton, transacciones reentrantes)
│   │   ├── schema.sql           # copia del script del DER
│   │   ├── inicializador.py · semilla.py (datos de ejemplo cargados a través de los servicios)
│   │   └── daos/                # BaseDAO[T] + un DAO por entidad principal + ReporteDAO
│   ├── servicios/               # un servicio por proceso + ReporteService + CatalogoService
│   ├── reportes/                # modelo de reporte, gráficos (matplotlib), PDF (ReportLab) y CSV
│   ├── presentacion/            # app.py (navegación), componentes.py y una vista por proceso
│   └── utils/                   # fechas, formatos, validaciones declarativas
└── tests/
```

## Patrones de diseño

| Patrón | Dónde | Qué resuelve |
| --- | --- | --- |
| **State** (muestra) | `dominio/muestra.py`, `dominio/estados_muestra.py` | Cada estado redefine solo sus transiciones válidas; las demás lanzan `TransicionInvalidaError` (p. ej. una muestra *Rechazada* no puede *analizarse*). |
| **State** (remito) | `dominio/remito.py`, `dominio/estados_remito.py` | El remito delega en su estado, que además coordina las transiciones de sus muestras (precintar ⇒ empaquetar; recibir con precinto roto ⇒ rechazar todas). La interfaz muestra solo las acciones que el estado admite (`operaciones_permitidas()`). |
| **Iterator** | `dominio/historial.py` (`IteradorHistorial` explícito), `HistoriaClinica.__iter__` (generador) | Recorrer la trazabilidad sin exponer la lista interna; el historial es *append-only* y `CambioEstado` es `dataclass(frozen=True)`. |
| **Strategy** | `dominio/tarifas.py`, `servicios/facturacion_service.py` | El total del comprobante lo calcula la estrategia; se elige con un diccionario `{TipoAtencion: lambda}` sin `if/elif`. |
| **Singleton** | `persistencia/conexion.py` | Una única conexión (`__new__` + bandera `_inicializada`, como en el apunte) con `transaccion()` reentrante y un lock. |
| **DAO** + método plantilla | `persistencia/daos/base_dao.py` | `BaseDAO[T]` implementa el CRUD genérico y cada DAO define el mapeo fila ↔ objeto. |

## Procesos de negocio

| # | Proceso | Vista | Servicio |
| --- | --- | --- | --- |
| 1 | Administrar clientes | Clientes | `ClienteService` |
| 2 | Mascotas e historias clínicas | Mascotas (historia clínica con atenciones, tratamientos, vacunas y órdenes) | `MascotaService` |
| 3 | Consultas y órdenes de derivación | Atenciones (+ Agenda de turnos) | `AtencionService`, `TurnoService` |
| 4 | Empaquetar muestras: remito + precinto | Empaquetado y envío › Armar remito / Precintar | `DerivacionService` |
| 5 | Cadena de envío | Empaquetado y envío › Despachar / tramos | `DerivacionService` |
| 6 | Recepción verificando el precinto | Laboratorio › Recepción | `LaboratorioService` |
| 7 | Resultados y comprobantes | Laboratorio › Análisis pendientes · Facturación | `LaboratorioService`, `FacturacionService` |

Opcionales cubiertos: stock de conservadoras (se marcan *en uso* mientras viajan y se liberan al recibirse;
ABM en Catálogos) y nueva extracción para muestras rechazadas (Trazabilidad).

## Validaciones de negocio

| Validación | Dominio / servicio | Refuerzo en la base |
| --- | --- | --- |
| Toda mascota tiene responsable | `Mascota.validar()`, `MascotaService._validar_responsable()` | `mascota.id_cliente NOT NULL` + FK |
| Precinto roto ⇒ muestra rechazada, no se procesa | `EnTransito.recibir()` del remito, `LaboratorioService.registrar_resultado()` | `CHECK` en `recepcion_laboratorio`, triggers `tg_resultado_requiere_muestra_recibida` y `tg_muestra_rechazada_no_procesa` |
| Trazabilidad inmutable | `HistorialEstados` (append-only), `CambioEstado` (frozen), `MuestraDAO` solo inserta cambios nuevos | Triggers que impiden `UPDATE`/`DELETE` en `cambio_estado_muestra` |
| Sin superposición de turnos | `Turno.se_superpone_con()`, `Agenda.reservar()` | Triggers `tg_turno_sin_superposicion_ins/upd` |
| Esquema de vacunas al registrar atenciones | `Atencion.validar_esquema_vacunas()`; `AtencionService.registrar()` lanza `EsquemaVacunasIncompletoError` y la interfaz pide confirmación | Datos en `vacuna_obligatoria` |

Además, al recibir un remito con precinto intacto cada muestra se evalúa por **temperatura de arribo** y
**viabilidad** (horas desde la extracción); la conservadora solo admite muestras cuyo rango de conservación
la contiene y respeta su capacidad.

## Reportes (pantalla, PDF y CSV)

1. **Atenciones clínicas y derivaciones** — por clínica, veterinario, tipo o especie; tasa de derivación y análisis más solicitados.
2. **Muestras rechazadas por fallas en el transporte** — detalle, causas (precinto, temperatura, viabilidad) y transportistas.
3. **Tratamientos aplicados y vacunas pendientes** — tratamientos vigentes y dosis obligatorias adeudadas (calculadas con el dominio).
4. **Facturación por clínica y servicios de laboratorio** — desglose por concepto, recargos/descuentos de la estrategia y análisis facturados.
5. **Tiempo promedio de tránsito y procesamiento** — calculado sobre el historial de estados, por tipo de muestra, laboratorio, clínica o transportista.

## Buenas prácticas del material de la cátedra

* **Lambdas, comprensiones, `map`, `filter` y `reduce`**: reglas de validación declarativas (`utils/validaciones.py`),
  subtotales con `reduce` (`dominio/tarifas.py`), mapeo de filas con `map` (`BaseDAO._mapear`), selección de la
  estrategia con un diccionario de lambdas, formatos de columnas de los reportes, filtros del esquema de vacunas.
* **POO**: herencia (`Persona`), clases abstractas (`ABC`), polimorfismo (estados y estrategias), encapsulamiento
  (el estado y el historial de la muestra solo cambian mediante sus operaciones).
* **sqlite3**: consultas parametrizadas con `?`, `row_factory = sqlite3.Row`, `lastrowid`, transacciones con
  `commit`/`rollback` y traducción de errores de integridad a mensajes para el usuario.
* **Flet**: cada vista es una clase con `construir()`; los eventos delegan en los servicios (sin SQL en la interfaz).
* **Reportes**: ReportLab con el gráfico de matplotlib incrustado, y CSV con el módulo estándar `csv`.

## Decisiones respecto de los diagramas

* Las operaciones de la muestra y del remito reciben además `responsable` y `fecha_hora`, que se registran en cada
  `CambioEstado` y permiten cargar la historia de ejemplo con fechas pasadas.
* `RemitoBiologico` agrega `quitar_muestra()` (en preparación) y `cerrar_tramo()` (llegada de un tramo) para
  modelar la cadena de custodia con cambios de transportista.
* El DER no guarda el precio de las vacunas: al facturar se sugiere `PRECIO_SUGERIDO_VACUNA` (`config.py`) y el
  importe queda editable en el comprobante. El esquema SQL se usa tal cual está en `Diagramas/ERD/schema.sql`.
