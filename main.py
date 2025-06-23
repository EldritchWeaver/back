# main.py
import os
import sqlite3
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict

DB_PATH = "app_db.db"
app = FastAPI(
    title="Torneo API",
    version="0.1.0",
    description="""
    Esta API permite la gestión completa de un sistema de torneos.
    Incluye funcionalidades para administrar:

    - **Usuarios**: Registro, consulta, actualización y eliminación de participantes.
    - **Equipos**: Creación, consulta, modificación y borrado de equipos, con asignación de capitán.
    - **Miembros de Equipo**: Asociación de usuarios a equipos con roles específicos (jugador, capitán, suplente).
    - **Torneos**: Configuración detallada de torneos, incluyendo fechas, descripciones y capacidad máxima de equipos.
    - **Inscripciones**: Gestión de la participación de equipos en torneos.
    - **Pagos**: Registro de pagos asociados a las inscripciones de equipos.
    - **Partidos**: Programación y registro de resultados de los encuentros dentro de los torneos.

    La base de datos utilizada es SQLite, y se inicializa automáticamente si no existe.
    """,
    # Define tags para agrupar las operaciones en la documentación de Swagger UI
    openapi_tags=[
        {"name": "Usuarios", "description": "Operaciones relacionadas con la gestión de usuarios."},
        {"name": "Equipos", "description": "Operaciones relacionadas con la gestión de equipos."},
        {"name": "Miembros de Equipo", "description": "Operaciones para gestionar la pertenencia de usuarios a equipos."},
        {"name": "Torneos", "description": "Operaciones para crear y administrar torneos."},
        {"name": "Inscripciones", "description": "Operaciones para gestionar la inscripción de equipos en torneos."},
        {"name": "Pagos", "description": "Operaciones para registrar y consultar pagos de torneos."},
        {"name": "Partidos", "description": "Operaciones para programar y gestionar partidos de torneos."},
    ]
)


# ————— Pydantic Schemas ————————————————————————————————————————————————

class UsuarioBase(BaseModel):
    """
    Esquema base para un usuario. Contiene los campos comunes para
    creación y actualización de usuarios.
    """
    nombre: str = Field(..., max_length=100, description="Nombre completo del usuario.")
    nickname: str = Field(..., max_length=100, description="Apodo o nombre de usuario único.")
    email: EmailStr = Field(..., description="Dirección de correo electrónico del usuario, debe ser única.")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"nombre": "Juan Pérez", "nickname": "jperez", "email": "juan.perez@example.com"}
            ]
        }
    )


class UsuarioCreate(UsuarioBase):
    """
    Esquema para la creación de un nuevo usuario. Incluye la contraseña hasheada.
    """
    pwd_hash: str = Field(..., min_length=60, description="Hash de la contraseña del usuario (ej. bcrypt).")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nombre": "Ana García",
                    "nickname": "agarcia",
                    "email": "ana.garcia@example.com",
                    "pwd_hash": "$2b$12$ABCDEFGHIJKLMNO.abcdefghijklmno.1234567890ABCDEFGHIJKL"
                }
            ]
        }
    )


class Usuario(UsuarioBase):
    """
    Esquema completo de un usuario, incluyendo su ID y fecha de registro.
    Representa el modelo de datos tal como se almacena y recupera.
    """
    id: int = Field(..., description="Identificador único del usuario.")
    fecha_reg: str = Field(..., description="Fecha y hora de registro del usuario (formato ISO 8601).")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": 1, "nombre": "Juan Pérez", "nickname": "jperez", "email": "juan.perez@example.com", "fecha_reg": "2023-10-27T10:00:00Z"}
            ]
        }
    )


class EquipoBase(BaseModel):
    """
    Esquema base para un equipo.
    """
    nombre: str = Field(..., max_length=100, description="Nombre único del equipo.")
    id_capitan: int = Field(..., description="ID del usuario que es capitán de este equipo. Debe existir en la tabla de usuarios.")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"nombre": "Los Campeones", "id_capitan": 1}
            ]
        }
    )


class EquipoCreate(EquipoBase):
    """
    Esquema para la creación de un nuevo equipo.
    """
    pass


class Equipo(EquipoBase):
    """
    Esquema completo de un equipo, incluyendo su ID.
    """
    id: int = Field(..., description="Identificador único del equipo.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": 101, "nombre": "Los Campeones", "id_capitan": 1}
            ]
        }
    )


class MiembroBase(BaseModel):
    """
    Esquema base para la relación entre un usuario y un equipo (miembro de equipo).
    """
    id_equipo: int = Field(..., description="ID del equipo al que pertenece el miembro.")
    id_usuario: int = Field(..., description="ID del usuario que es miembro del equipo.")
    rol: str = Field(
        "jugador",
        pattern="^(jugador|capitan|suplente)$",
        description="Rol del miembro dentro del equipo. Puede ser 'jugador', 'capitan' o 'suplente'."
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"id_equipo": 101, "id_usuario": 2, "rol": "jugador"}
            ]
        }
    )


class MiembroCreate(MiembroBase):
    """
    Esquema para la creación de un nuevo miembro de equipo.
    """
    pass


class Miembro(MiembroBase):
    """
    Esquema completo de un miembro de equipo, incluyendo su ID.
    """
    id: int = Field(..., description="Identificador único del registro de miembro de equipo.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": 1, "id_equipo": 101, "id_usuario": 2, "rol": "jugador"}
            ]
        }
    )


class TorneoBase(BaseModel):
    """
    Esquema base para un torneo.
    """
    nombre: str = Field(..., description="Nombre del torneo.")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del torneo.")
    fecha_inicio: str = Field(..., description="Fecha y hora de inicio del torneo (formato ISO 8601, ej. 'YYYY-MM-DDTHH:MM:SSZ').")
    fecha_fin: str = Field(..., description="Fecha y hora de finalización del torneo (formato ISO 8601, ej. 'YYYY-MM-DDTHH:MM:SSZ').")
    max_equipos: int = Field(..., gt=0, description="Número máximo de equipos permitidos en el torneo.")
    estado: Optional[str] = Field(
        "programado",
        pattern="^(programado|en_curso|finalizado)$",
        description="Estado actual del torneo. Puede ser 'programado', 'en_curso' o 'finalizado'."
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "nombre": "Copa Verano 2024",
                    "descripcion": "Torneo de fútbol 5 amateur.",
                    "fecha_inicio": "2024-07-01T18:00:00Z",
                    "fecha_fin": "2024-07-31T22:00:00Z",
                    "max_equipos": 16,
                    "estado": "programado"
                }
            ]
        }
    )


class TorneoCreate(TorneoBase):
    """
    Esquema para la creación de un nuevo torneo.
    """
    pass


class Torneo(TorneoBase):
    """
    Esquema completo de un torneo, incluyendo su ID.
    """
    id: int = Field(..., description="Identificador único del torneo.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "nombre": "Copa Verano 2024",
                    "descripcion": "Torneo de fútbol 5 amateur.",
                    "fecha_inicio": "2024-07-01T18:00:00Z",
                    "fecha_fin": "2024-07-31T22:00:00Z",
                    "max_equipos": 16,
                    "estado": "programado"
                }
            ]
        }
    )


class InscripcionBase(BaseModel):
    """
    Esquema base para una inscripción de equipo en un torneo.
    """
    id_equipo: int = Field(..., description="ID del equipo que se inscribe.")
    id_torneo: int = Field(..., description="ID del torneo en el que se inscribe el equipo.")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"id_equipo": 101, "id_torneo": 1}
            ]
        }
    )


class InscripcionCreate(InscripcionBase):
    """
    Esquema para la creación de una nueva inscripción.
    """
    pass


class Inscripcion(InscripcionBase):
    """
    Esquema completo de una inscripción, incluyendo su ID y fecha de inscripción.
    """
    id: int = Field(..., description="Identificador único de la inscripción.")
    fecha_inscripcion: str = Field(..., description="Fecha y hora en que se realizó la inscripción (formato ISO 8601).")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": 1, "id_equipo": 101, "id_torneo": 1, "fecha_inscripcion": "2024-06-20T10:00:00Z"}
            ]
        }
    )


class PagoBase(BaseModel):
    """
    Esquema base para un pago.
    """
    id_equipo: int = Field(..., description="ID del equipo que realiza el pago.")
    id_torneo: int = Field(..., description="ID del torneo al que corresponde el pago.")
    monto_cent: int = Field(..., ge=0, description="Monto del pago en centavos (entero positivo).")
    estado: Optional[str] = Field(
        "pendiente",
        pattern="^(pendiente|confirmado)$",
        description="Estado del pago. Puede ser 'pendiente' o 'confirmado'."
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"id_equipo": 101, "id_torneo": 1, "monto_cent": 5000, "estado": "pendiente"}
            ]
        }
    )


class PagoCreate(PagoBase):
    """
    Esquema para la creación de un nuevo pago.
    """
    pass


class Pago(PagoBase):
    """
    Esquema completo de un pago, incluyendo su ID y fecha de pago.
    """
    id: int = Field(..., description="Identificador único del pago.")
    fecha_pago: str = Field(..., description="Fecha y hora en que se registró el pago (formato ISO 8601).")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": 1, "id_equipo": 101, "id_torneo": 1, "monto_cent": 5000, "estado": "confirmado", "fecha_pago": "2024-06-20T10:15:00Z"}
            ]
        }
    )


class PartidoBase(BaseModel):
    """
    Esquema base para un partido.
    """
    id_torneo: int = Field(..., description="ID del torneo al que pertenece el partido.")
    equipo_local: int = Field(..., description="ID del equipo local.")
    equipo_visitante: int = Field(..., description="ID del equipo visitante.")
    fecha: str = Field(..., description="Fecha y hora programada del partido (formato ISO 8601, ej. 'YYYY-MM-DDTHH:MM:SSZ').")
    resultado_local: Optional[int] = Field(None, description="Puntuación del equipo local (opcional, para resultados).")
    resultado_visitante: Optional[int] = Field(None, description="Puntuación del equipo visitante (opcional, para resultados).")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id_torneo": 1,
                    "equipo_local": 101,
                    "equipo_visitante": 102,
                    "fecha": "2024-07-05T20:00:00Z",
                    "resultado_local": None,
                    "resultado_visitante": None
                }
            ]
        }
    )


class PartidoCreate(PartidoBase):
    """
    Esquema para la creación de un nuevo partido.
    """
    pass


class Partido(PartidoBase):
    """
    Esquema completo de un partido, incluyendo su ID.
    """
    id: int = Field(..., description="Identificador único del partido.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "id_torneo": 1,
                    "equipo_local": 101,
                    "equipo_visitante": 102,
                    "fecha": "2024-07-05T20:00:00Z",
                    "resultado_local": 3,
                    "resultado_visitante": 1
                }
            ]
        }
    )


# ————— Utility para DB ————————————————————————————————————————————————

def get_db():
    """
    Dependencia que proporciona una conexión a la base de datos SQLite.

    Establece una conexión a la base de datos 'app_db.db', configura la
    factoría de filas para que devuelva diccionarios (sqlite3.Row) y asegura
    que las claves foráneas estén habilitadas. La conexión se cierra
    automáticamente después de su uso.

    Yields:
        sqlite3.Connection: Objeto de conexión a la base de datos.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def initialize_database():
    """
    Inicializa la base de datos al inicio de la aplicación.

    Si el archivo de la base de datos (`app_db.db`) no existe, lo crea y configura
    todas las tablas necesarias:
    - `usuarios`: Para almacenar información de los usuarios.
    - `equipos`: Para gestionar los equipos y su capitán.
    - `miembros_equipo`: Para la relación muchos a muchos entre usuarios y equipos, con un rol específico.
    - `torneos`: Para definir las características de cada torneo.
    - `inscripciones`: Para registrar qué equipo se inscribe en qué torneo.
    - `pagos`: Para controlar los pagos asociados a las inscripciones.
    - `partidos`: Para programar y registrar los resultados de los encuentros.

    También crea índices para mejorar el rendimiento de las consultas comunes.
    """
    if not os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.executescript("""
            PRAGMA foreign_keys = ON;

            CREATE TABLE usuarios (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              nombre      TEXT    NOT NULL,
              nickname    TEXT    NOT NULL,
              email       TEXT    NOT NULL UNIQUE,
              pwd_hash    TEXT    NOT NULL,
              fecha_reg   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE equipos (
              id          INTEGER PRIMARY KEY AUTOINCREMENT,
              nombre      TEXT    NOT NULL UNIQUE,
              id_capitan  INTEGER NOT NULL,
              FOREIGN KEY(id_capitan) REFERENCES usuarios(id) ON DELETE RESTRICT
            );

            CREATE TABLE miembros_equipo (
              id           INTEGER PRIMARY KEY AUTOINCREMENT,
              id_equipo    INTEGER NOT NULL,
              id_usuario   INTEGER NOT NULL,
              rol          TEXT    NOT NULL DEFAULT 'jugador'
                                   CHECK(rol IN ('jugador','capitan','suplente')),
              UNIQUE(id_equipo, id_usuario),
              FOREIGN KEY(id_equipo) REFERENCES equipos(id) ON DELETE CASCADE,
              FOREIGN KEY(id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE
            );

            CREATE UNIQUE INDEX idx_unq_capitan_equipo
              ON miembros_equipo(id_equipo)
              WHERE rol = 'capitan';

            CREATE TABLE torneos (
              id           INTEGER PRIMARY KEY AUTOINCREMENT,
              nombre       TEXT    NOT NULL,
              descripcion  TEXT,
              fecha_inicio DATETIME NOT NULL,
              fecha_fin    DATETIME NOT NULL,
              max_equipos  INTEGER NOT NULL CHECK(max_equipos > 0),
              estado       TEXT NOT NULL DEFAULT 'programado'
                                   CHECK(estado IN ('programado','en_curso','finalizado'))
            );

            CREATE TABLE inscripciones (
              id                   INTEGER PRIMARY KEY AUTOINCREMENT,
              id_equipo            INTEGER NOT NULL,
              id_torneo            INTEGER NOT NULL,
              fecha_inscripcion    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(id_equipo, id_torneo),
              FOREIGN KEY(id_equipo) REFERENCES equipos(id) ON DELETE CASCADE,
              FOREIGN KEY(id_torneo) REFERENCES torneos(id) ON DELETE CASCADE
            );

            CREATE TABLE pagos (
              id            INTEGER PRIMARY KEY AUTOINCREMENT,
              id_equipo     INTEGER NOT NULL,
              id_torneo     INTEGER NOT NULL,
              monto_cent    INTEGER NOT NULL CHECK(monto_cent >= 0),
              estado        TEXT NOT NULL DEFAULT 'pendiente'
                                    CHECK(estado IN ('pendiente','confirmado')),
              fecha_pago    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(id_equipo) REFERENCES equipos(id) ON DELETE CASCADE,
              FOREIGN KEY(id_torneo) REFERENCES torneos(id) ON DELETE CASCADE
            );

            CREATE TABLE partidos (
              id                   INTEGER PRIMARY KEY AUTOINCREMENT,
              id_torneo            INTEGER NOT NULL,
              equipo_local         INTEGER NOT NULL,
              equipo_visitante     INTEGER NOT NULL,
              fecha                DATETIME NOT NULL,
              resultado_local      INTEGER,
              resultado_visitante  INTEGER,
              FOREIGN KEY(id_torneo) REFERENCES torneos(id) ON DELETE CASCADE,
              FOREIGN KEY(equipo_local) REFERENCES equipos(id) ON DELETE RESTRICT,
              FOREIGN KEY(equipo_visitante) REFERENCES equipos(id) ON DELETE RESTRICT,
              CHECK(equipo_local <> equipo_visitante)
            );

            CREATE INDEX idx_usuarios_email  ON usuarios(email);
            CREATE INDEX idx_insc_torneo     ON inscripciones(id_torneo);
            CREATE INDEX idx_pagos_torneo    ON pagos(id_torneo);
            """)
            print("🔧 DB creada.")

# --- CRUD Endpoints ---------------------------------------------------------

# 1) Usuarios ----------------------------------------------------------------
@app.post(
    "/users/",
    response_model=Usuario,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo usuario",
    description="Registra un nuevo usuario en la base de datos con su nombre, nickname, email y contraseña hasheada.",
    tags=["Usuarios"],
    responses={
        status.HTTP_201_CREATED: {
            "description": "Usuario creado exitosamente.",
            "content": {
                "application/json": {
                    "example": {"id": 1, "nombre": "Nuevo Usuario", "nickname": "nuevouser", "email": "nuevo.usuario@example.com", "fecha_reg": "2024-06-20T11:00:00"}
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Email duplicado o datos de entrada inválidos.",
            "content": {
                "application/json": {
                    "example": {"detail": "Email duplicado o datos inválidos"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada (e.g., formato de email inválido, longitud de contraseña).",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "email"],
                                "msg": "value is not a valid email address",
                                "type": "value_error.email"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def create_user(u: UsuarioCreate, db=Depends(get_db)):
    """
    Crea un nuevo usuario en el sistema.

    Args:
        u (UsuarioCreate): Los datos del usuario a crear.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `400 Bad Request`: Si el email ya está registrado o hay datos inválidos que violan restricciones de la DB.

    Returns:
        Usuario: El objeto Usuario recién creado, incluyendo su ID y fecha de registro.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (nombre, nickname, email, pwd_hash) VALUES (?, ?, ?, ?)",
            (u.nombre, u.nickname, u.email, u.pwd_hash)
        )
        db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Email duplicado o datos inválidos")
    row = cursor.execute("SELECT * FROM usuarios WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Usuario(**row)


@app.get(
    "/users/",
    response_model=List[Usuario],
    summary="Listar todos los usuarios",
    description="Obtiene una lista de todos los usuarios registrados en el sistema.",
    tags=["Usuarios"]
)
def list_users(db=Depends(get_db)):
    """
    Obtiene una lista de todos los usuarios.

    Args:
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        List[Usuario]: Una lista de objetos Usuario.
    """
    rows = db.execute("SELECT * FROM usuarios").fetchall()
    return [Usuario(**r) for r in rows]


@app.get(
    "/users/{user_id}",
    response_model=Usuario,
    summary="Obtener un usuario por ID",
    description="Recupera los detalles de un usuario específico por su ID.",
    tags=["Usuarios"],
    responses={
        status.HTTP_200_OK: {
            "description": "Detalles del usuario.",
            "content": {
                "application/json": {
                    "example": {"id": 1, "nombre": "Juan Pérez", "nickname": "jperez", "email": "juan.perez@example.com", "fecha_reg": "2023-10-27T10:00:00"}
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Usuario no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Usuario no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID de usuario (e.g., ID no numérico).",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "user_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def get_user(user_id: int, db=Depends(get_db)):
    """
    Obtiene un usuario por su ID.

    Args:
        user_id (int): El ID del usuario a recuperar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el usuario con el ID proporcionado no existe.

    Returns:
        Usuario: El objeto Usuario correspondiente al ID.
    """
    row = db.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return Usuario(**row)


@app.put(
    "/users/{user_id}",
    response_model=Usuario,
    summary="Actualizar un usuario por ID",
    description="Actualiza la información (nombre, nickname, email) de un usuario existente por su ID.",
    tags=["Usuarios"],
    responses={
        status.HTTP_200_OK: {
            "description": "Usuario actualizado exitosamente.",
            "content": {
                "application/json": {
                    "example": {"id": 1, "nombre": "Juan Modificado", "nickname": "jperez_updated", "email": "juan.modificado@example.com", "fecha_reg": "2023-10-27T10:00:00"}
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Usuario no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Usuario no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada o ID.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "email"],
                                "msg": "value is not a valid email address",
                                "type": "value_error.email"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def update_user(user_id: int, u: UsuarioBase, db=Depends(get_db)):
    """
    Actualiza la información de un usuario.

    Args:
        user_id (int): El ID del usuario a actualizar.
        u (UsuarioBase): Los datos del usuario para la actualización.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el usuario con el ID proporcionado no existe.

    Returns:
        Usuario: El objeto Usuario actualizado.
    """
    cursor = db.cursor()
    cursor.execute(
        "UPDATE usuarios SET nombre=?, nickname=?, email=? WHERE id=?",
        (u.nombre, u.nickname, u.email, user_id)
    )
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    db.commit()
    row = db.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    return Usuario(**row)


@app.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un usuario por ID",
    description="Elimina un usuario específico de la base de datos por su ID.",
    tags=["Usuarios"],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Usuario eliminado exitosamente. No se devuelve contenido."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Usuario no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Usuario no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID de usuario.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "user_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def delete_user(user_id: int, db=Depends(get_db)):
    """
    Elimina un usuario por su ID.

    Args:
        user_id (int): El ID del usuario a eliminar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el usuario con el ID proporcionado no existe.

    Returns:
        None: No devuelve contenido si la eliminación es exitosa (código 204).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    db.commit()
    return


# 2) Equipos ----------------------------------------------------------------
@app.post(
    "/teams/",
    response_model=Equipo,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo equipo",
    description="Registra un nuevo equipo en la base de datos. El `id_capitan` debe corresponder a un usuario existente y el `nombre` del equipo debe ser único.",
    tags=["Equipos"],
    responses={
        status.HTTP_201_CREATED: {
            "description": "Equipo creado exitosamente.",
            "content": {
                "application/json": {
                    "example": {"id": 101, "nombre": "Nuevo Equipo", "id_capitan": 1}
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Nombre de equipo duplicado o capitán inexistente.",
            "content": {
                "application/json": {
                    "example": {"detail": "Nombre duplicado o capitán inexistente"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "nombre"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def create_team(t: EquipoCreate, db=Depends(get_db)):
    """
    Crea un nuevo equipo en el sistema.

    Args:
        t (EquipoCreate): Los datos del equipo a crear.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `400 Bad Request`: Si el nombre del equipo ya existe o el ID del capitán no corresponde a un usuario válido.

    Returns:
        Equipo: El objeto Equipo recién creado, incluyendo su ID.
    """
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO equipos (nombre, id_capitan) VALUES (?, ?)",
            (t.nombre, t.id_capitan)
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nombre duplicado o capitán inexistente")
    row = db.execute("SELECT * FROM equipos WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Equipo(**row)


@app.get(
    "/teams/",
    response_model=List[Equipo],
    summary="Listar todos los equipos",
    description="Obtiene una lista de todos los equipos registrados en el sistema.",
    tags=["Equipos"]
)
def list_teams(db=Depends(get_db)):
    """
    Obtiene una lista de todos los equipos.

    Args:
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        List[Equipo]: Una lista de objetos Equipo.
    """
    rows = db.execute("SELECT * FROM equipos").fetchall()
    return [Equipo(**r) for r in rows]


@app.get(
    "/teams/{team_id}",
    response_model=Equipo,
    summary="Obtener un equipo por ID",
    description="Recupera los detalles de un equipo específico por su ID.",
    tags=["Equipos"],
    responses={
        status.HTTP_200_OK: {
            "description": "Detalles del equipo.",
            "content": {
                "application/json": {
                    "example": {"id": 101, "nombre": "Los Campeones", "id_capitan": 1}
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Equipo no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Equipo no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID del equipo.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "team_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def get_team(team_id: int, db=Depends(get_db)):
    """
    Obtiene un equipo por su ID.

    Args:
        team_id (int): El ID del equipo a recuperar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el equipo con el ID proporcionado no existe.

    Returns:
        Equipo: El objeto Equipo correspondiente al ID.
    """
    row = db.execute("SELECT * FROM equipos WHERE id = ?", (team_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return Equipo(**row)


@app.put(
    "/teams/{team_id}",
    response_model=Equipo,
    summary="Actualizar un equipo por ID",
    description="Actualiza la información (nombre, id_capitan) de un equipo existente por su ID. El `id_capitan` debe ser un usuario existente.",
    tags=["Equipos"],
    responses={
        status.HTTP_200_OK: {
            "description": "Equipo actualizado exitosamente.",
            "content": {
                "application/json": {
                    "example": {"id": 101, "nombre": "Los Campeones (Actualizado)", "id_capitan": 1}
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Equipo no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Equipo no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada o ID.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "id_capitan"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def update_team(team_id: int, t: EquipoBase, db=Depends(get_db)):
    """
    Actualiza la información de un equipo.

    Args:
        team_id (int): El ID del equipo a actualizar.
        t (EquipoBase): Los datos del equipo para la actualización.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el equipo con el ID proporcionado no existe.

    Returns:
        Equipo: El objeto Equipo actualizado.
    """
    cursor = db.cursor()
    cursor.execute(
        "UPDATE equipos SET nombre=?, id_capitan=? WHERE id=?",
        (t.nombre, t.id_capitan, team_id)
    )
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    db.commit()
    row = db.execute("SELECT * FROM equipos WHERE id = ?", (team_id,)).fetchone()
    return Equipo(**row)


@app.delete(
    "/teams/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un equipo por ID",
    description="Elimina un equipo específico de la base de datos por su ID. Tenga en cuenta las restricciones de clave externa: si un usuario es capitán de este equipo, no se podrá eliminar sin antes reasignar o eliminar al capitán.",
    tags=["Equipos"],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Equipo eliminado exitosamente. No se devuelve contenido."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Equipo no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Equipo no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID del equipo.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "team_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def delete_team(team_id: int, db=Depends(get_db)):
    """
    Elimina un equipo por su ID.

    Args:
        team_id (int): El ID del equipo a eliminar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el equipo con el ID proporcionado no existe.

    Returns:
        None: No devuelve contenido si la eliminación es exitosa (código 204).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM equipos WHERE id = ?", (team_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    db.commit()
    return


# 3) Miembros de Equipo -----------------------------------------------------
@app.post(
    "/members/",
    response_model=Miembro,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir un miembro a un equipo",
    description="Asocia un usuario a un equipo con un rol específico (jugador, capitán, suplente). Un usuario no puede ser miembro duplicado del mismo equipo y solo puede haber un capitán por equipo.",
    tags=["Miembros de Equipo"],
    responses={
        status.HTTP_201_CREATED: {
            "description": "Miembro añadido exitosamente.",
            "content": {
                "application/json": {
                    "example": {"id": 1, "id_equipo": 101, "id_usuario": 2, "rol": "jugador"}
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Miembro duplicado para el equipo/usuario, o el rol 'capitan' ya está asignado para este equipo, o los IDs de equipo/usuario no existen.",
            "content": {
                "application/json": {
                    "example": {"detail": "Duplicado o datos inválidos (revisa equipo/usuario/rol)"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "rol"],
                                "msg": "value does not match regex \"^(jugador|capitan|suplente)$\"",
                                "type": "value_error.str.regex"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def add_member(m: MiembroCreate, db=Depends(get_db)):
    """
    Añade un usuario como miembro a un equipo.

    Args:
        m (MiembroCreate): Los datos del miembro a añadir (ID de equipo, ID de usuario, rol).
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `400 Bad Request`: Si la combinación equipo/usuario ya existe, o si el rol 'capitan' ya está ocupado
              para ese equipo, o si los IDs de equipo/usuario no existen.

    Returns:
        Miembro: El objeto Miembro recién creado, incluyendo su ID.
    """
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO miembros_equipo (id_equipo, id_usuario, rol) VALUES (?, ?, ?)",
            (m.id_equipo, m.id_usuario, m.rol)
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicado o datos inválidos (revisa equipo/usuario/rol)")
    row = db.execute("SELECT * FROM miembros_equipo WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Miembro(**row)


@app.get(
    "/members/",
    response_model=List[Miembro],
    summary="Listar todos los miembros de equipo",
    description="Obtiene una lista de todas las asociaciones entre usuarios y equipos (miembros de equipo).",
    tags=["Miembros de Equipo"]
)
def list_members(db=Depends(get_db)):
    """
    Obtiene una lista de todos los miembros de equipo.

    Args:
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        List[Miembro]: Una lista de objetos Miembro.
    """
    rows = db.execute("SELECT * FROM miembros_equipo").fetchall()
    return [Miembro(**r) for r in rows]


@app.delete(
    "/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un miembro de equipo por ID",
    description="Elimina una asociación de miembro de equipo específica por su ID.",
    tags=["Miembros de Equipo"],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Miembro de equipo eliminado exitosamente. No se devuelve contenido."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Miembro de equipo no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Miembro no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID del miembro.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "member_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def delete_member(member_id: int, db=Depends(get_db)):
    """
    Elimina un miembro de equipo por su ID.

    Args:
        member_id (int): El ID del miembro de equipo a eliminar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el miembro de equipo con el ID proporcionado no existe.

    Returns:
        None: No devuelve contenido si la eliminación es exitosa (código 204).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM miembros_equipo WHERE id = ?", (member_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Miembro no encontrado")
    db.commit()
    return


# 4) Torneos ---------------------------------------------------------------
@app.post(
    "/tournaments/",
    response_model=Torneo,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo torneo",
    description="Crea un nuevo registro de torneo en la base de datos con sus detalles como nombre, descripción, fechas de inicio y fin, y el número máximo de equipos.",
    tags=["Torneos"],
    responses={
        status.HTTP_201_CREATED: {
            "description": "Torneo creado exitosamente.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "nombre": "Copa de Invierno",
                        "descripcion": "Torneo de eSports de invierno.",
                        "fecha_inicio": "2025-01-15T10:00:00Z",
                        "fecha_fin": "2025-02-15T20:00:00Z",
                        "max_equipos": 32,
                        "estado": "programado"
                    }
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada (e.g., fechas inválidas, max_equipos menor o igual a 0).",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "max_equipos"],
                                "msg": "ensure this value is greater than 0",
                                "type": "value_error.number.not_gt"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def create_tournament(t: TorneoCreate, db=Depends(get_db)):
    """
    Crea un nuevo torneo.

    Args:
        t (TorneoCreate): Los datos del torneo a crear.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        Torneo: El objeto Torneo recién creado, incluyendo su ID.
    """
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO torneos
           (nombre, descripcion, fecha_inicio, fecha_fin, max_equipos, estado)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (t.nombre, t.descripcion, t.fecha_inicio, t.fecha_fin, t.max_equipos, t.estado)
    )
    db.commit()
    row = db.execute("SELECT * FROM torneos WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Torneo(**row)


@app.get(
    "/tournaments/",
    response_model=List[Torneo],
    summary="Listar todos los torneos",
    description="Obtiene una lista de todos los torneos registrados en el sistema.",
    tags=["Torneos"]
)
def list_tournaments(db=Depends(get_db)):
    """
    Obtiene una lista de todos los torneos.

    Args:
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        List[Torneo]: Una lista de objetos Torneo.
    """
    rows = db.execute("SELECT * FROM torneos").fetchall()
    return [Torneo(**r) for r in rows]


@app.get(
    "/tournaments/{tournament_id}",
    response_model=Torneo,
    summary="Obtener un torneo por ID",
    description="Recupera los detalles de un torneo específico por su ID.",
    tags=["Torneos"],
    responses={
        status.HTTP_200_OK: {
            "description": "Detalles del torneo.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "nombre": "Copa de Invierno",
                        "descripcion": "Torneo de eSports de invierno.",
                        "fecha_inicio": "2025-01-15T10:00:00Z",
                        "fecha_fin": "2025-02-15T20:00:00Z",
                        "max_equipos": 32,
                        "estado": "programado"
                    }
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Torneo no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Torneo no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID del torneo.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "tournament_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def get_tournament(tournament_id: int, db=Depends(get_db)):
    """
    Obtiene un torneo por su ID.

    Args:
        tournament_id (int): El ID del torneo a recuperar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el torneo con el ID proporcionado no existe.

    Returns:
        Torneo: El objeto Torneo correspondiente al ID.
    """
    row = db.execute("SELECT * FROM torneos WHERE id = ?", (tournament_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Torneo no encontrado")
    return Torneo(**row)


@app.put(
    "/tournaments/{tournament_id}",
    response_model=Torneo,
    summary="Actualizar un torneo por ID",
    description="Actualiza la información de un torneo existente por su ID. Se pueden modificar el nombre, descripción, fechas, máximo de equipos y estado.",
    tags=["Torneos"],
    responses={
        status.HTTP_200_OK: {
            "description": "Torneo actualizado exitosamente.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "nombre": "Copa de Invierno (Actualizada)",
                        "descripcion": "Torneo de eSports de invierno con nuevas reglas.",
                        "fecha_inicio": "2025-01-15T10:00:00Z",
                        "fecha_fin": "2025-02-28T22:00:00Z",
                        "max_equipos": 48,
                        "estado": "en_curso"
                    }
                }
            }
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Torneo no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Torneo no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada o ID.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "fecha_fin"],
                                "msg": "invalid datetime format",
                                "type": "value_error.datetime"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def update_tournament(tournament_id: int, t: TorneoBase, db=Depends(get_db)):
    """
    Actualiza la información de un torneo.

    Args:
        tournament_id (int): El ID del torneo a actualizar.
        t (TorneoBase): Los datos del torneo para la actualización.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el torneo con el ID proporcionado no existe.

    Returns:
        Torneo: El objeto Torneo actualizado.
    """
    cursor = db.cursor()
    cursor.execute(
        """UPDATE torneos
           SET nombre=?, descripcion=?, fecha_inicio=?, fecha_fin=?, max_equipos=?, estado=?
           WHERE id=?""",
        (t.nombre, t.descripcion, t.fecha_inicio, t.fecha_fin, t.max_equipos, t.estado, tournament_id)
    )
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Torneo no encontrado")
    db.commit()
    row = db.execute("SELECT * FROM torneos WHERE id = ?", (tournament_id,)).fetchone()
    return Torneo(**row)


@app.delete(
    "/tournaments/{tournament_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un torneo por ID",
    description="Elimina un torneo específico de la base de datos por su ID. Tenga en cuenta que esto también eliminará en cascada las inscripciones, pagos y partidos asociados a este torneo.",
    tags=["Torneos"],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Torneo eliminado exitosamente. No se devuelve contenido."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Torneo no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Torneo no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID del torneo.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "tournament_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def delete_tournament(tournament_id: int, db=Depends(get_db)):
    """
    Elimina un torneo por su ID.

    Args:
        tournament_id (int): El ID del torneo a eliminar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el torneo con el ID proporcionado no existe.

    Returns:
        None: No devuelve contenido si la eliminación es exitosa (código 204).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM torneos WHERE id = ?", (tournament_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Torneo no encontrado")
    db.commit()
    return


# 5) Inscripciones ----------------------------------------------------------
@app.post(
    "/inscriptions/",
    response_model=Inscripcion,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva inscripción",
    description="Registra la inscripción de un equipo en un torneo. Un equipo solo puede inscribirse una vez por torneo.",
    tags=["Inscripciones"],
    responses={
        status.HTTP_201_CREATED: {
            "description": "Inscripción creada exitosamente.",
            "content": {
                "application/json": {
                    "example": {"id": 1, "id_equipo": 101, "id_torneo": 1, "fecha_inscripcion": "2024-06-20T10:00:00"}
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Inscripción duplicada para el equipo/torneo, o datos inválidos (equipo/torneo inexistente).",
            "content": {
                "application/json": {
                    "example": {"detail": "Inscripción duplicada o datos inválidos"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "id_equipo"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def create_inscription(i: InscripcionCreate, db=Depends(get_db)):
    """
    Crea una nueva inscripción de un equipo en un torneo.

    Args:
        i (InscripcionCreate): Los datos de la inscripción a crear.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `400 Bad Request`: Si la inscripción ya existe para ese equipo y torneo,
              o si los IDs de equipo/torneo no son válidos (violan restricciones de clave foránea).

    Returns:
        Inscripcion: El objeto Inscripcion recién creado, incluyendo su ID y fecha.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO inscripciones (id_equipo, id_torneo) VALUES (?, ?)",
            (i.id_equipo, i.id_torneo)
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Inscripción duplicada o datos inválidos")
    row = db.execute("SELECT * FROM inscripciones WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Inscripcion(**row)


@app.get(
    "/inscriptions/",
    response_model=List[Inscripcion],
    summary="Listar todas las inscripciones",
    description="Obtiene una lista de todas las inscripciones de equipos en torneos registradas.",
    tags=["Inscripciones"]
)
def list_inscriptions(db=Depends(get_db)):
    """
    Obtiene una lista de todas las inscripciones.

    Args:
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        List[Inscripcion]: Una lista de objetos Inscripcion.
    """
    rows = db.execute("SELECT * FROM inscripciones").fetchall()
    return [Inscripcion(**r) for r in rows]


@app.delete(
    "/inscriptions/{insc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una inscripción por ID",
    description="Elimina una inscripción específica por su ID.",
    tags=["Inscripciones"],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Inscripción eliminada exitosamente. No se devuelve contenido."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Inscripción no encontrada.",
            "content": {
                "application/json": {
                    "example": {"detail": "Inscripción no encontrada"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID de inscripción.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "insc_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def delete_inscription(insc_id: int, db=Depends(get_db)):
    """
    Elimina una inscripción por su ID.

    Args:
        insc_id (int): El ID de la inscripción a eliminar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si la inscripción con el ID proporcionado no existe.

    Returns:
        None: No devuelve contenido si la eliminación es exitosa (código 204).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM inscripciones WHERE id = ?", (insc_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inscripción no encontrada")
    db.commit()
    return


# 6) Pagos ------------------------------------------------------------------
@app.post(
    "/payments/",
    response_model=Pago,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo pago",
    description="Registra un nuevo pago asociado a un equipo y un torneo, especificando el monto en centavos y su estado inicial (pendiente/confirmado).",
    tags=["Pagos"],
    responses={
        status.HTTP_201_CREATED: {
            "description": "Pago creado exitosamente.",
            "content": {
                "application/json": {
                    "example": {"id": 1, "id_equipo": 101, "id_torneo": 1, "monto_cent": 5000, "estado": "pendiente", "fecha_pago": "2024-06-20T10:15:00"}
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Datos de pago inválidos (equipo/torneo inexistente o monto negativo).",
            "content": {
                "application/json": {
                    "example": {"detail": "Pago inválido o duplicado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "monto_cent"],
                                "msg": "ensure this value is greater than or equal to 0",
                                "type": "value_error.number.not_ge"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def create_payment(p: PagoCreate, db=Depends(get_db)):
    """
    Crea un nuevo registro de pago.

    Args:
        p (PagoCreate): Los datos del pago a crear.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `400 Bad Request`: Si los IDs de equipo/torneo no son válidos (violan restricciones de clave foránea)
              o si el monto es negativo.

    Returns:
        Pago: El objeto Pago recién creado, incluyendo su ID y fecha de pago.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO pagos (id_equipo, id_torneo, monto_cent, estado) VALUES (?, ?, ?, ?)",
            (p.id_equipo, p.id_torneo, p.monto_cent, p.estado)
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pago inválido o duplicado")
    row = db.execute("SELECT * FROM pagos WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Pago(**row)


@app.get(
    "/payments/",
    response_model=List[Pago],
    summary="Listar todos los pagos",
    description="Obtiene una lista de todos los pagos registrados.",
    tags=["Pagos"]
)
def list_payments(db=Depends(get_db)):
    """
    Obtiene una lista de todos los pagos.

    Args:
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        List[Pago]: Una lista de objetos Pago.
    """
    rows = db.execute("SELECT * FROM pagos").fetchall()
    return [Pago(**r) for r in rows]


@app.delete(
    "/payments/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un pago por ID",
    description="Elimina un registro de pago específico por su ID.",
    tags=["Pagos"],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Pago eliminado exitosamente. No se devuelve contenido."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Pago no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Pago no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID de pago.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "payment_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def delete_payment(payment_id: int, db=Depends(get_db)):
    """
    Elimina un pago por su ID.

    Args:
        payment_id (int): El ID del pago a eliminar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el pago con el ID proporcionado no existe.

    Returns:
        None: No devuelve contenido si la eliminación es exitosa (código 204).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM pagos WHERE id = ?", (payment_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pago no encontrado")
    db.commit()
    return


# 7) Partidos ---------------------------------------------------------------
@app.post(
    "/matches/",
    response_model=Partido,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo partido",
    description="Programa un nuevo partido entre dos equipos dentro de un torneo. Los equipos (`equipo_local`, `equipo_visitante`) deben ser diferentes y existir en la base de datos, y el `id_torneo` también debe ser válido.",
    tags=["Partidos"],
    responses={
        status.HTTP_201_CREATED: {
            "description": "Partido creado exitosamente.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "id_torneo": 1,
                        "equipo_local": 101,
                        "equipo_visitante": 102,
                        "fecha": "2024-07-05T20:00:00",
                        "resultado_local": None,
                        "resultado_visitante": None
                    }
                }
            }
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Datos de partido inválidos (ej. equipos duplicados, torneo/equipos inexistentes).",
            "content": {
                "application/json": {
                    "example": {"detail": "Datos de partido inválidos"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación de los datos de entrada.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "fecha"],
                                "msg": "invalid datetime format",
                                "type": "value_error.datetime"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def create_match(m: PartidoCreate, db=Depends(get_db)):
    """
    Crea un nuevo partido.

    Args:
        m (PartidoCreate): Los datos del partido a crear.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `400 Bad Request`: Si los IDs de torneo/equipos no son válidos (violan restricciones de clave foránea),
              o si el equipo local y el visitante son el mismo.

    Returns:
        Partido: El objeto Partido recién creado, incluyendo su ID.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            """INSERT INTO partidos
               (id_torneo, equipo_local, equipo_visitante, fecha, resultado_local, resultado_visitante)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (m.id_torneo, m.equipo_local, m.equipo_visitante,
             m.fecha, m.resultado_local, m.resultado_visitante)
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Datos de partido inválidos")
    row = db.execute("SELECT * FROM partidos WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Partido(**row)


@app.get(
    "/matches/",
    response_model=List[Partido],
    summary="Listar todos los partidos",
    description="Obtiene una lista de todos los partidos registrados.",
    tags=["Partidos"]
)
def list_matches(db=Depends(get_db)):
    """
    Obtiene una lista de todos los partidos.

    Args:
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Returns:
        List[Partido]: Una lista de objetos Partido.
    """
    rows = db.execute("SELECT * FROM partidos").fetchall()
    return [Partido(**r) for r in rows]


@app.delete(
    "/matches/{match_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un partido por ID",
    description="Elimina un partido específico de la base de datos por su ID.",
    tags=["Partidos"],
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Partido eliminado exitosamente. No se devuelve contenido."},
        status.HTTP_404_NOT_FOUND: {
            "description": "Partido no encontrado.",
            "content": {
                "application/json": {
                    "example": {"detail": "Partido no encontrado"}
                }
            }
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación del ID del partido.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "match_id"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def delete_match(match_id: int, db=Depends(get_db)):
    """
    Elimina un partido por su ID.

    Args:
        match_id (int): El ID del partido a eliminar.
        db (sqlite3.Connection): Conexión a la base de datos inyectada por FastAPI.

    Raises:
        HTTPException:
            - `404 Not Found`: Si el partido con el ID proporcionado no existe.

    Returns:
        None: No devuelve contenido si la eliminación es exitosa (código 204).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM partidos WHERE id = ?", (match_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Partido no encontrado")
    db.commit()
    return

# --- Run: source venv/bin/activate

# --- Only after activate venv and install the requrimentes.txt -----------------------------------

# --- For Local Run with: python -m uvicorn main:app --reload -------------------------------------
# --- For Public Run with: python -m uvicorn main:app --reload --host 192.168.x.x --port 8000 -----

