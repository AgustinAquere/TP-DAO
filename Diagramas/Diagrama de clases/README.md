# Diagramas de clases — TP Integrador Tema 2 (Veterinaria y derivación a laboratorio)

Fuentes en PlantUML (`.puml`, comparten `_estilo.iuml`) y exportados en `.png` / `.svg`.

| #   | Diagrama                     | Qué cubre                                                                                                                                |
| --- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `01_atencion_clinica`        | Clientes, mascotas, historia clínica, atenciones, tratamientos, vacunas y esquema obligatorio, turnos/agenda (procesos 1, 2, 3)          |
| 2   | `02_derivacion_trazabilidad` | Orden de derivación, muestras, conservadora, remito + precinto, tramos de envío, recepción y resultados (procesos 3–7)                   |
| 3   | `03_patron_state_muestra`    | **State** de la Muestra (Extraída → Empaquetada → En tránsito → Recibida → Analizada / Rechazada) + historial inmutable con **Iterator** |
| 4   | `04_patron_state_remito`     | **State** del Remito biológico (En preparación → Precintado → En tránsito → Recibido / Rechazado)                                        |
| 5   | `05_facturacion_strategy`    | Comprobante de atención con **Strategy** de tarifa (Consulta / Control / Urgencia)                                                       |
| 6   | `06_capas_servicios_dao`     | Servicios con las validaciones de negocio y persistencia con **DAO** + **Singleton** (conexión)                                          |

## Cómo se cubren las validaciones
- **Mascota con responsable**: multiplicidad `Cliente 1 — 0..* Mascota`; se valida en `MascotaService.alta`.
- **Precinto roto → Muestra Rechazada**: `RecepcionLaboratorio.evaluar` + estado `EnTransito` del remito llama `muestra.rechazar()`; `Rechazada` no admite `analizar()`.
- **Trazabilidad inmutable**: `CambioEstado` es `dataclass(frozen=True)` y `HistorialEstados` solo permite agregar (append-only); se persiste con `MuestraDAO.insertar_cambio_estado`.
- **Sin superposición de turnos**: `Turno.se_superpone_con` usado por `Agenda` / `TurnoService`.
- **Esquema de vacunas obligatorias**: `VacunaObligatoria` por `Especie`; `Atencion.validar_esquema_vacunas()`.

## Regenerar las imágenes
```
java -jar plantuml.jar -tpng -charset UTF-8 0*.puml
java -jar plantuml.jar -tsvg -charset UTF-8 0*.puml
```
