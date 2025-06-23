import sqlite3

DB_PATH = "app_db.db"

def init_db(db_path: str):
    """Inicializa la base de datos SQLite con el esquema refinado."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1) Activar claves foráneas
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 2) Crear tablas
    cursor.executescript("""
    -- Usuarios
    CREATE TABLE IF NOT EXISTS usuarios (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      nombre      TEXT    NOT NULL,
      nickname    TEXT    NOT NULL,
      email       TEXT    NOT NULL UNIQUE,
      pwd_hash    TEXT    NOT NULL,
      fecha_reg   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- Equipos
    CREATE TABLE IF NOT EXISTS equipos (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      nombre      TEXT    NOT NULL UNIQUE,
      id_capitan  INTEGER NOT NULL,
      FOREIGN KEY(id_capitan)
        REFERENCES usuarios(id)
        ON DELETE RESTRICT
    );

    -- Miembros de equipo (sin unique partial)
    CREATE TABLE IF NOT EXISTS miembros_equipo (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      id_equipo    INTEGER NOT NULL,
      id_usuario   INTEGER NOT NULL,
      rol          TEXT    NOT NULL DEFAULT 'jugador'
                     CHECK(rol IN ('jugador','capitan','suplente')),
      UNIQUE (id_equipo, id_usuario),
      FOREIGN KEY(id_equipo)
        REFERENCES equipos(id)
        ON DELETE CASCADE,
      FOREIGN KEY(id_usuario)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
    );

    -- Torneos
    CREATE TABLE IF NOT EXISTS torneos (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      nombre       TEXT    NOT NULL,
      descripcion  TEXT,
      fecha_inicio DATETIME NOT NULL,
      fecha_fin    DATETIME NOT NULL,
      max_equipos  INTEGER NOT NULL CHECK(max_equipos > 0),
      estado       TEXT    NOT NULL DEFAULT 'programado'
                     CHECK(estado IN ('programado','en_curso','finalizado'))
    );

    -- Inscripciones (por equipo)
    CREATE TABLE IF NOT EXISTS inscripciones (
      id                 INTEGER PRIMARY KEY AUTOINCREMENT,
      id_equipo          INTEGER NOT NULL,
      id_torneo          INTEGER NOT NULL,
      fecha_inscripcion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE (id_equipo, id_torneo),
      FOREIGN KEY(id_equipo)
        REFERENCES equipos(id)
        ON DELETE CASCADE,
      FOREIGN KEY(id_torneo)
        REFERENCES torneos(id)
        ON DELETE CASCADE
    );

    -- Pagos (en centavos para precisión)
    CREATE TABLE IF NOT EXISTS pagos (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      id_equipo     INTEGER NOT NULL,
      id_torneo     INTEGER NOT NULL,
      monto_cent    INTEGER NOT NULL CHECK(monto_cent >= 0),
      estado        TEXT    NOT NULL DEFAULT 'pendiente'
                     CHECK(estado IN ('pendiente','confirmado')),
      fecha_pago    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(id_equipo)
        REFERENCES equipos(id)
        ON DELETE CASCADE,
      FOREIGN KEY(id_torneo)
        REFERENCES torneos(id)
        ON DELETE CASCADE
    );

    -- Partidos
    CREATE TABLE IF NOT EXISTS partidos (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      id_torneo           INTEGER NOT NULL,
      equipo_local        INTEGER NOT NULL,
      equipo_visitante    INTEGER NOT NULL,
      fecha               DATETIME NOT NULL,
      resultado_local     INTEGER DEFAULT NULL,
      resultado_visitante INTEGER DEFAULT NULL,
      FOREIGN KEY(id_torneo)
        REFERENCES torneos(id)
        ON DELETE CASCADE,
      FOREIGN KEY(equipo_local)
        REFERENCES equipos(id)
        ON DELETE RESTRICT,
      FOREIGN KEY(equipo_visitante)
        REFERENCES equipos(id)
        ON DELETE RESTRICT,
      CHECK(equipo_local <> equipo_visitante)
    );

    -- Índices generales
    CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
    CREATE INDEX IF NOT EXISTS idx_insc_torneo    ON inscripciones(id_torneo);
    CREATE INDEX IF NOT EXISTS idx_pagos_torneo   ON pagos(id_torneo);
    """)

    # 3) Partial unique index: sólo un capitán por equipo
    cursor.execute("""
      CREATE UNIQUE INDEX IF NOT EXISTS idx_unq_capitan_equipo
      ON miembros_equipo(id_equipo)
      WHERE rol = 'capitan';
    """)

    conn.commit()
    conn.close()
    print(f"Base de datos inicializada en '{db_path}' con el esquema refinado.")

if __name__ == "__main__":
    init_db(DB_PATH)

