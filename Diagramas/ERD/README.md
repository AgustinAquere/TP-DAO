# DER — TP Integrador Tema 2 (Veterinaria y derivación a laboratorio)

| Archivo      | Contenido                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------ |
| `DER.puml`   | Diagrama entidad-relación en PlantUML (notación pata de gallo)                              |
| `schema.sql` | Script SQLite que implementa el DER (tablas, claves, `CHECK` y triggers de validación)      |

Notación del diagrama: `*` = NOT NULL, `<<PK>>` clave primaria, `<<FK>>` clave foránea, `<<UK>>` único.

## Tablas (31)

| Bloque                          | Tablas                                                                                                                                                                                                                                                                                                  |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Atención clínica                | `clinica`, `cliente`, `veterinario`, `veterinario_clinica`, `especie`, `mascota`, `historia_clinica`, `turno`, `atencion`, `tratamiento`, `vacuna`, `vacuna_obligatoria`, `aplicacion_vacuna`                                                                                                          |
| Derivación y laboratorio        | `laboratorio_central`, `bioquimico`, `tipo_analisis`, `orden_derivacion`, `analisis_solicitado`, `muestra`, `cambio_estado_muestra`, `conservadora`, `remito_biologico`, `precinto_sanitario`, `transportista`, `tramo_envio`, `recepcion_laboratorio`, `resultado_analisis`, `detalle_resultado`       |
| Facturación                     | `servicio_clinico`, `comprobante_atencion`, `item_comprobante`                                                                                                                                                                                                                                         |

## Decisiones de mapeo (clases → tablas)

- **Herencia `Persona`**: tabla por clase concreta (`cliente`, `veterinario`, `bioquimico`), cada una con los datos personales. No se comparten personas entre roles, así que se evita una tabla `persona` y sus joins.
- **`Agenda`**: no tiene tabla; es la consulta de `turno` por `id_veterinario` y fecha (índice `ix_turno_vet_fecha`).
- **Veterinario ↔ Clínica (N:M)**: tabla asociativa `veterinario_clinica`.
- **Relaciones 1:1** (`mascota`–`historia_clinica`, `remito`–`precinto`, `remito`–`recepcion`, `analisis_solicitado`–`resultado`, `atencion`–`comprobante`, `turno`–`atencion`): FK con `UNIQUE`.
- **Patrón State** (Muestra y Remito): se persiste el nombre del estado actual en la columna `estado`; el objeto estado se reconstruye al leer.
- **Historial inmutable (Iterator)**: `cambio_estado_muestra` guarda cada `CambioEstado`; es la fuente para el reporte de tiempos de tránsito y procesamiento.
- **Patrón Strategy**: `comprobante_atencion.estrategia_tarifa` registra qué estrategia se aplicó, y `subtotal`/`total` quedan guardados al emitir para que los reportes de facturación no dependan de recalcular con precios que pueden cambiar.
- **`item_comprobante`**: una FK opcional por tipo de concepto (`id_servicio`, `id_tipo_analisis`, `id_vacuna`); un `CHECK` exige que esté cargada exactamente la que corresponde al `tipo` (ninguna para `INSUMO`).

## Validaciones de negocio en la base

| Validación del enunciado                              | Cómo la refuerza el esquema                                                                                                                         |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Toda mascota tiene un responsable                     | `mascota.id_cliente NOT NULL` + FK a `cliente`                                                                                                      |
| Precinto roto ⇒ muestra rechazada, no se procesa      | `CHECK` en `recepcion_laboratorio` (ROTO ⇒ `aceptada = 0` con motivo); trigger `tg_resultado_requiere_muestra_recibida`; trigger `tg_muestra_rechazada_no_procesa` (RECHAZADA y ANALIZADA son finales) |
| Trazabilidad inmutable de estados de la muestra       | Triggers que abortan `UPDATE`/`DELETE` sobre `cambio_estado_muestra`                                                                                |
| Sin superposición de turnos                           | Triggers `tg_turno_sin_superposicion_ins/upd` (ignora turnos cancelados)                                                                            |
| Esquema de vacunas obligatorias                       | Datos en `vacuna_obligatoria` (por especie) + `aplicacion_vacuna`; el control lo hace `AtencionService` (requiere calcular edad y refuerzos)         |

El orden válido de transiciones (Extraída → Empaquetada → En tránsito → Recibida → Analizada) lo controla el patrón State en la capa de dominio; la base solo bloquea los casos críticos de arriba.

## Reportes que soporta

- Atenciones y derivaciones: `atencion` ⋈ `orden_derivacion` (por clínica, veterinario, tipo, período).
- Muestras rechazadas por transporte: `muestra.estado = 'RECHAZADA'` ⋈ `remito_biologico` ⋈ `recepcion_laboratorio` / `tramo_envio` (motivo, temperatura, transportista).
- Tratamientos y vacunas pendientes: `tratamiento`, `aplicacion_vacuna.fecha_proxima_dosis` y `vacuna_obligatoria` contra la edad de cada mascota.
- Facturación por clínica y servicios de laboratorio: `comprobante_atencion` ⋈ `item_comprobante` agrupado por `id_clinica` y `tipo`.
- Tiempo promedio de tránsito y procesamiento: diferencias de `fecha_hora` en `cambio_estado_muestra` (EN_TRANSITO → RECIBIDA → ANALIZADA) o entre `tramo_envio` y `recepcion_laboratorio`.
