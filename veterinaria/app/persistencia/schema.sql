-- =====================================================================
-- TP Integrador 2026 - Tema 2: Veterinaria, red de clínicas y derivación
-- a laboratorio. Esquema relacional (SQLite) que implementa el DER.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 1. Atención clínica
-- ---------------------------------------------------------------------
CREATE TABLE clinica (
    id_clinica      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    direccion       TEXT    NOT NULL,
    telefono        TEXT,
    cuit            TEXT    NOT NULL UNIQUE
);

CREATE TABLE cliente (
    id_cliente      INTEGER PRIMARY KEY AUTOINCREMENT,
    dni             TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    apellido        TEXT    NOT NULL,
    telefono        TEXT,
    email           TEXT,
    direccion       TEXT,
    fecha_alta      DATE    NOT NULL DEFAULT (date('now')),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE veterinario (
    id_veterinario  INTEGER PRIMARY KEY AUTOINCREMENT,
    dni             TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    apellido        TEXT    NOT NULL,
    telefono        TEXT,
    email           TEXT,
    matricula       TEXT    NOT NULL UNIQUE,
    especialidad    TEXT
);

-- N:M "Veterinario trabaja en Clínica"
CREATE TABLE veterinario_clinica (
    id_veterinario  INTEGER NOT NULL REFERENCES veterinario (id_veterinario),
    id_clinica      INTEGER NOT NULL REFERENCES clinica (id_clinica),
    PRIMARY KEY (id_veterinario, id_clinica)
);

CREATE TABLE especie (
    id_especie      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL UNIQUE
);

-- Validación: toda mascota debe tener un responsable (id_cliente NOT NULL)
CREATE TABLE mascota (
    id_mascota       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente       INTEGER NOT NULL REFERENCES cliente (id_cliente),
    id_especie       INTEGER NOT NULL REFERENCES especie (id_especie),
    nombre           TEXT    NOT NULL,
    raza             TEXT,
    sexo             TEXT    CHECK (sexo IN ('M', 'H')),
    fecha_nacimiento DATE,
    peso_kg          REAL    CHECK (peso_kg > 0),
    microchip        TEXT    UNIQUE
);

-- 1:1 con mascota (UNIQUE sobre la FK)
CREATE TABLE historia_clinica (
    id_historia             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_mascota              INTEGER NOT NULL UNIQUE REFERENCES mascota (id_mascota),
    numero                  TEXT    NOT NULL UNIQUE,
    fecha_apertura          DATE    NOT NULL DEFAULT (date('now')),
    observaciones_generales TEXT,
    alergias                TEXT
);

-- La "Agenda" del diagrama de clases es una vista de los turnos de un
-- veterinario en una fecha: no requiere tabla propia.
CREATE TABLE turno (
    id_turno          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_veterinario    INTEGER  NOT NULL REFERENCES veterinario (id_veterinario),
    id_mascota        INTEGER  NOT NULL REFERENCES mascota (id_mascota),
    id_clinica        INTEGER  NOT NULL REFERENCES clinica (id_clinica),
    fecha_hora_inicio DATETIME NOT NULL,
    duracion_min      INTEGER  NOT NULL CHECK (duracion_min > 0),
    estado            TEXT     NOT NULL DEFAULT 'RESERVADO'
                      CHECK (estado IN ('RESERVADO', 'ATENDIDO', 'CANCELADO', 'AUSENTE'))
);
CREATE INDEX ix_turno_vet_fecha ON turno (id_veterinario, fecha_hora_inicio);

-- Validación: evitar superposición de turnos del mismo veterinario
CREATE TRIGGER tg_turno_sin_superposicion_ins
BEFORE INSERT ON turno
WHEN NEW.estado <> 'CANCELADO'
BEGIN
    SELECT RAISE(ABORT, 'El turno se superpone con otro turno del veterinario')
    WHERE EXISTS (
        SELECT 1 FROM turno t
        WHERE t.id_veterinario = NEW.id_veterinario
          AND t.estado <> 'CANCELADO'
          AND datetime(NEW.fecha_hora_inicio) <
              datetime(t.fecha_hora_inicio, '+' || t.duracion_min || ' minutes')
          AND datetime(t.fecha_hora_inicio) <
              datetime(NEW.fecha_hora_inicio, '+' || NEW.duracion_min || ' minutes')
    );
END;

CREATE TRIGGER tg_turno_sin_superposicion_upd
BEFORE UPDATE OF id_veterinario, fecha_hora_inicio, duracion_min, estado ON turno
WHEN NEW.estado <> 'CANCELADO'
BEGIN
    SELECT RAISE(ABORT, 'El turno se superpone con otro turno del veterinario')
    WHERE EXISTS (
        SELECT 1 FROM turno t
        WHERE t.id_veterinario = NEW.id_veterinario
          AND t.id_turno <> NEW.id_turno
          AND t.estado <> 'CANCELADO'
          AND datetime(NEW.fecha_hora_inicio) <
              datetime(t.fecha_hora_inicio, '+' || t.duracion_min || ' minutes')
          AND datetime(t.fecha_hora_inicio) <
              datetime(NEW.fecha_hora_inicio, '+' || NEW.duracion_min || ' minutes')
    );
END;

CREATE TABLE atencion (
    id_atencion        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_historia        INTEGER  NOT NULL REFERENCES historia_clinica (id_historia),
    id_veterinario     INTEGER  NOT NULL REFERENCES veterinario (id_veterinario),
    id_clinica         INTEGER  NOT NULL REFERENCES clinica (id_clinica),
    id_turno           INTEGER  UNIQUE REFERENCES turno (id_turno),  -- NULL en urgencias sin turno
    fecha_hora         DATETIME NOT NULL,
    tipo               TEXT     NOT NULL CHECK (tipo IN ('CONSULTA', 'CONTROL', 'URGENCIA')),
    motivo             TEXT     NOT NULL,
    anamnesis          TEXT,
    diagnostico        TEXT,
    peso_registrado_kg REAL     CHECK (peso_registrado_kg > 0)
);

CREATE TABLE tratamiento (
    id_tratamiento  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atencion     INTEGER NOT NULL REFERENCES atencion (id_atencion) ON DELETE CASCADE,
    descripcion     TEXT    NOT NULL,
    medicamento     TEXT,
    dosis           TEXT,
    frecuencia      TEXT,
    fecha_inicio    DATE    NOT NULL,
    fecha_fin       DATE,
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
);

CREATE TABLE vacuna (
    id_vacuna              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                 TEXT    NOT NULL UNIQUE,
    laboratorio_fabricante TEXT
);

-- Esquema de vacunación obligatorio por especie
CREATE TABLE vacuna_obligatoria (
    id_vacuna_obligatoria    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_especie               INTEGER NOT NULL REFERENCES especie (id_especie),
    id_vacuna                INTEGER NOT NULL REFERENCES vacuna (id_vacuna),
    edad_minima_semanas      INTEGER NOT NULL CHECK (edad_minima_semanas >= 0),
    frecuencia_refuerzo_dias INTEGER CHECK (frecuencia_refuerzo_dias > 0),  -- NULL = dosis única
    UNIQUE (id_especie, id_vacuna)
);

CREATE TABLE aplicacion_vacuna (
    id_aplicacion       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atencion         INTEGER NOT NULL REFERENCES atencion (id_atencion) ON DELETE CASCADE,
    id_vacuna           INTEGER NOT NULL REFERENCES vacuna (id_vacuna),
    fecha               DATE    NOT NULL,
    lote                TEXT    NOT NULL,
    fecha_proxima_dosis DATE
);

-- ---------------------------------------------------------------------
-- 2. Derivación, empaquetado, envío, recepción y resultados
-- ---------------------------------------------------------------------
CREATE TABLE laboratorio_central (
    id_laboratorio  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    direccion       TEXT    NOT NULL,
    telefono        TEXT
);

CREATE TABLE bioquimico (
    id_bioquimico   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_laboratorio  INTEGER NOT NULL REFERENCES laboratorio_central (id_laboratorio),
    dni             TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    apellido        TEXT    NOT NULL,
    telefono        TEXT,
    email           TEXT,
    matricula       TEXT    NOT NULL UNIQUE
);

CREATE TABLE tipo_analisis (
    id_tipo_analisis       INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo                 TEXT    NOT NULL UNIQUE,
    nombre                 TEXT    NOT NULL,
    tipo_muestra_requerida TEXT    NOT NULL
        CHECK (tipo_muestra_requerida IN ('SANGRE', 'SUERO', 'ORINA', 'MATERIA_FECAL', 'TEJIDO', 'HISOPADO')),
    temp_min_c             REAL    NOT NULL,
    temp_max_c             REAL    NOT NULL,
    horas_max_viabilidad   INTEGER NOT NULL CHECK (horas_max_viabilidad > 0),
    precio                 REAL    NOT NULL CHECK (precio >= 0),
    CHECK (temp_min_c <= temp_max_c)
);

CREATE TABLE orden_derivacion (
    id_orden              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atencion           INTEGER  NOT NULL REFERENCES atencion (id_atencion),
    id_laboratorio        INTEGER  NOT NULL REFERENCES laboratorio_central (id_laboratorio),
    numero                TEXT     NOT NULL UNIQUE,
    fecha_emision         DATETIME NOT NULL,
    prioridad             TEXT     NOT NULL DEFAULT 'NORMAL' CHECK (prioridad IN ('NORMAL', 'URGENTE')),
    indicaciones_clinicas TEXT,
    estado                TEXT     NOT NULL DEFAULT 'EMITIDA'
                          CHECK (estado IN ('EMITIDA', 'EN_PROCESO', 'COMPLETA', 'CANCELADA'))
);

CREATE TABLE conservadora (
    id_conservadora INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT    NOT NULL UNIQUE,
    capacidad       INTEGER NOT NULL CHECK (capacidad > 0),
    temp_min_c      REAL    NOT NULL,
    temp_max_c      REAL    NOT NULL,
    disponible      INTEGER NOT NULL DEFAULT 1 CHECK (disponible IN (0, 1)),
    CHECK (temp_min_c <= temp_max_c)
);

CREATE TABLE remito_biologico (
    id_remito              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_conservadora        INTEGER  NOT NULL REFERENCES conservadora (id_conservadora),
    id_clinica_origen      INTEGER  NOT NULL REFERENCES clinica (id_clinica),
    id_laboratorio_destino INTEGER  NOT NULL REFERENCES laboratorio_central (id_laboratorio),
    numero                 TEXT     NOT NULL UNIQUE,
    fecha_hora_emision     DATETIME NOT NULL,
    estado                 TEXT     NOT NULL DEFAULT 'EN_PREPARACION'
        CHECK (estado IN ('EN_PREPARACION', 'PRECINTADO', 'EN_TRANSITO', 'RECIBIDO', 'RECHAZADO'))
);

-- estado = estado actual (patrón State); el historial completo e
-- inmutable está en cambio_estado_muestra.
CREATE TABLE muestra (
    id_muestra            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_orden              INTEGER  NOT NULL REFERENCES orden_derivacion (id_orden),
    id_veterinario        INTEGER  NOT NULL REFERENCES veterinario (id_veterinario),  -- extraída por
    id_remito             INTEGER  REFERENCES remito_biologico (id_remito),          -- NULL hasta empaquetar
    codigo                TEXT     NOT NULL UNIQUE,
    tipo                  TEXT     NOT NULL
        CHECK (tipo IN ('SANGRE', 'SUERO', 'ORINA', 'MATERIA_FECAL', 'TEJIDO', 'HISOPADO')),
    fecha_hora_extraccion DATETIME NOT NULL,
    volumen_ml            REAL     CHECK (volumen_ml > 0),
    estado                TEXT     NOT NULL DEFAULT 'EXTRAIDA'
        CHECK (estado IN ('EXTRAIDA', 'EMPAQUETADA', 'EN_TRANSITO', 'RECIBIDA', 'ANALIZADA', 'RECHAZADA')),
    CHECK (estado = 'EXTRAIDA' OR estado = 'RECHAZADA' OR id_remito IS NOT NULL)
);
CREATE INDEX ix_muestra_remito ON muestra (id_remito);

-- Trazabilidad inmutable: solo INSERT (append-only)
CREATE TABLE cambio_estado_muestra (
    id_cambio       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_muestra      INTEGER  NOT NULL REFERENCES muestra (id_muestra),
    fecha_hora      DATETIME NOT NULL DEFAULT (datetime('now')),
    estado_anterior TEXT,  -- NULL en el primer registro (extracción)
    estado_nuevo    TEXT     NOT NULL
        CHECK (estado_nuevo IN ('EXTRAIDA', 'EMPAQUETADA', 'EN_TRANSITO', 'RECIBIDA', 'ANALIZADA', 'RECHAZADA')),
    responsable     TEXT     NOT NULL,
    observacion     TEXT
);
CREATE INDEX ix_cambio_muestra ON cambio_estado_muestra (id_muestra, fecha_hora);

CREATE TRIGGER tg_cambio_estado_muestra_no_update
BEFORE UPDATE ON cambio_estado_muestra
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de la muestra es inmutable');
END;

CREATE TRIGGER tg_cambio_estado_muestra_no_delete
BEFORE DELETE ON cambio_estado_muestra
BEGIN
    SELECT RAISE(ABORT, 'El historial de estados de la muestra es inmutable');
END;

-- Validación: una muestra rechazada no puede procesarse (pasar a ANALIZADA)
CREATE TRIGGER tg_muestra_rechazada_no_procesa
BEFORE UPDATE OF estado ON muestra
WHEN OLD.estado IN ('RECHAZADA', 'ANALIZADA') AND NEW.estado <> OLD.estado
BEGIN
    SELECT RAISE(ABORT, 'La muestra está en un estado final y no admite transiciones');
END;

CREATE TABLE analisis_solicitado (
    id_analisis_solicitado INTEGER PRIMARY KEY AUTOINCREMENT,
    id_orden               INTEGER NOT NULL REFERENCES orden_derivacion (id_orden),
    id_tipo_analisis       INTEGER NOT NULL REFERENCES tipo_analisis (id_tipo_analisis),
    id_muestra             INTEGER NOT NULL REFERENCES muestra (id_muestra),
    observaciones          TEXT,
    UNIQUE (id_orden, id_tipo_analisis)
);

-- 1:1 con remito
CREATE TABLE precinto_sanitario (
    id_precinto           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_remito             INTEGER  NOT NULL UNIQUE REFERENCES remito_biologico (id_remito),
    numero                TEXT     NOT NULL UNIQUE,
    fecha_hora_colocacion DATETIME NOT NULL,
    estado                TEXT     NOT NULL DEFAULT 'INTACTO' CHECK (estado IN ('INTACTO', 'ROTO'))
);

CREATE TABLE transportista (
    id_transportista INTEGER PRIMARY KEY AUTOINCREMENT,
    razon_social     TEXT    NOT NULL,
    cuit             TEXT    NOT NULL UNIQUE,
    telefono         TEXT,
    patente_vehiculo TEXT
);

-- Cadena de custodia: cada tramo es un eslabón del envío
CREATE TABLE tramo_envio (
    id_tramo              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_remito             INTEGER  NOT NULL REFERENCES remito_biologico (id_remito),
    id_transportista      INTEGER  NOT NULL REFERENCES transportista (id_transportista),
    nro_orden             INTEGER  NOT NULL CHECK (nro_orden > 0),
    origen                TEXT     NOT NULL,
    destino               TEXT     NOT NULL,
    fecha_hora_salida     DATETIME NOT NULL,
    fecha_hora_llegada    DATETIME,
    temperatura_salida_c  REAL,
    temperatura_llegada_c REAL,
    entregado_por         TEXT     NOT NULL,
    recibido_por          TEXT,
    observaciones         TEXT,
    UNIQUE (id_remito, nro_orden),
    CHECK (fecha_hora_llegada IS NULL OR fecha_hora_llegada >= fecha_hora_salida)
);

-- 1:1 con remito. Precinto ROTO => recepción no aceptada
CREATE TABLE recepcion_laboratorio (
    id_recepcion               INTEGER PRIMARY KEY AUTOINCREMENT,
    id_remito                  INTEGER  NOT NULL UNIQUE REFERENCES remito_biologico (id_remito),
    id_bioquimico              INTEGER  NOT NULL REFERENCES bioquimico (id_bioquimico),
    fecha_hora                 DATETIME NOT NULL,
    estado_precinto_verificado TEXT     NOT NULL CHECK (estado_precinto_verificado IN ('INTACTO', 'ROTO')),
    temperatura_arribo_c       REAL,
    aceptada                   INTEGER  NOT NULL CHECK (aceptada IN (0, 1)),
    motivo_rechazo             TEXT,
    CHECK (estado_precinto_verificado = 'INTACTO' OR aceptada = 0),
    CHECK (aceptada = 1 OR motivo_rechazo IS NOT NULL)
);

-- 1:1 con analisis_solicitado
CREATE TABLE resultado_analisis (
    id_resultado           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_analisis_solicitado INTEGER  NOT NULL UNIQUE REFERENCES analisis_solicitado (id_analisis_solicitado),
    id_bioquimico          INTEGER  NOT NULL REFERENCES bioquimico (id_bioquimico),  -- firma
    fecha_hora             DATETIME NOT NULL,
    interpretacion         TEXT,
    observaciones          TEXT
);

-- Validación: solo se cargan resultados sobre muestras RECIBIDAS
CREATE TRIGGER tg_resultado_requiere_muestra_recibida
BEFORE INSERT ON resultado_analisis
BEGIN
    SELECT RAISE(ABORT, 'Solo se registran resultados de muestras recibidas (no rechazadas)')
    WHERE (SELECT m.estado
             FROM analisis_solicitado a
             JOIN muestra m ON m.id_muestra = a.id_muestra
            WHERE a.id_analisis_solicitado = NEW.id_analisis_solicitado)
          NOT IN ('RECIBIDA', 'ANALIZADA');
END;

CREATE TABLE detalle_resultado (
    id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_resultado    INTEGER NOT NULL REFERENCES resultado_analisis (id_resultado) ON DELETE CASCADE,
    parametro       TEXT    NOT NULL,
    valor           REAL    NOT NULL,
    unidad          TEXT,
    valor_ref_min   REAL,
    valor_ref_max   REAL
);

-- ---------------------------------------------------------------------
-- 3. Facturación (comprobantes de atención)
-- ---------------------------------------------------------------------
CREATE TABLE servicio_clinico (
    id_servicio     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    precio_base     REAL    NOT NULL CHECK (precio_base >= 0)
);

-- estrategia_tarifa y total quedan "congelados" al emitir (Strategy)
CREATE TABLE comprobante_atencion (
    id_comprobante    INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atencion       INTEGER  NOT NULL UNIQUE REFERENCES atencion (id_atencion),
    id_cliente        INTEGER  NOT NULL REFERENCES cliente (id_cliente),
    id_clinica        INTEGER  NOT NULL REFERENCES clinica (id_clinica),
    numero            TEXT     NOT NULL UNIQUE,
    fecha_emision     DATETIME NOT NULL,
    estrategia_tarifa TEXT     NOT NULL CHECK (estrategia_tarifa IN ('CONSULTA', 'CONTROL', 'URGENCIA')),
    subtotal          REAL     NOT NULL CHECK (subtotal >= 0),
    total             REAL     NOT NULL CHECK (total >= 0)
);

-- Cada ítem referencia, según su tipo, el concepto facturado
CREATE TABLE item_comprobante (
    id_item          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_comprobante   INTEGER NOT NULL REFERENCES comprobante_atencion (id_comprobante) ON DELETE CASCADE,
    tipo             TEXT    NOT NULL
        CHECK (tipo IN ('SERVICIO_CLINICO', 'ANALISIS_LABORATORIO', 'VACUNA', 'INSUMO')),
    id_servicio      INTEGER REFERENCES servicio_clinico (id_servicio),
    id_tipo_analisis INTEGER REFERENCES tipo_analisis (id_tipo_analisis),
    id_vacuna        INTEGER REFERENCES vacuna (id_vacuna),
    descripcion      TEXT    NOT NULL,
    cantidad         INTEGER NOT NULL DEFAULT 1 CHECK (cantidad > 0),
    precio_unitario  REAL    NOT NULL CHECK (precio_unitario >= 0),
    CHECK (
        (tipo = 'SERVICIO_CLINICO'     AND id_servicio IS NOT NULL AND id_tipo_analisis IS NULL AND id_vacuna IS NULL) OR
        (tipo = 'ANALISIS_LABORATORIO' AND id_tipo_analisis IS NOT NULL AND id_servicio IS NULL AND id_vacuna IS NULL) OR
        (tipo = 'VACUNA'               AND id_vacuna IS NOT NULL AND id_servicio IS NULL AND id_tipo_analisis IS NULL) OR
        (tipo = 'INSUMO'               AND id_servicio IS NULL AND id_tipo_analisis IS NULL AND id_vacuna IS NULL)
    )
);
