"""Autenticación y control de acceso por rol para CopyMary ERP.

Usa las tablas fundacionales que ya existían en `erp_database.py`
(`app_users`, `app_roles`, `app_permissions`) pero que hasta ahora nadie
escribía ni leía. Este módulo es lo que faltaba para que "cualquiera que
abra la URL" (bloqueante #2 del análisis original) deje de ser cierto.

Diseño deliberadamente simple:
- El rol "Administrador" siempre tiene acceso total (no necesita filas en
  `app_permissions`) — evita que un admin quede bloqueado por accidente.
- Cualquier otro rol solo ve los módulos donde exista una fila explícita
  `allowed = 1` en `app_permissions`. Sin fila = sin acceso (deny by default).
- Las contraseñas se guardan como `salt_hex$hash_hex` en `password_hash`,
  con PBKDF2-HMAC-SHA256 (200,000 iteraciones). No se agregan dependencias
  externas nuevas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import os
from uuid import uuid4

import streamlit as st

from src.erp_database import connect, initialize_database, record_audit_event

ADMIN_ROLE_NAME = "Administrador"
SESSION_KEY = "auth_user"
PBKDF2_ITERATIONS = 200_000


# ---------------------------------------------------------------------------
# Hash de contraseñas
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, _ = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    candidate = _hash_password(password, salt)
    return candidate == stored


# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_one(query: str, params: tuple = ()) -> dict | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def _fetch_all(query: str, params: tuple = ()) -> list[dict]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def any_users_exist() -> bool:
    row = _fetch_one("SELECT COUNT(*) AS n FROM app_users")
    return bool(row and row["n"] > 0)


def get_role_by_name(name: str) -> dict | None:
    return _fetch_one("SELECT * FROM app_roles WHERE name = ?", (name,))


def list_roles() -> list[dict]:
    return _fetch_all("SELECT * FROM app_roles ORDER BY name")


def create_role(name: str, description: str = "") -> str:
    existing = get_role_by_name(name)
    if existing:
        return existing["role_id"]
    role_id = f"ROL-{uuid4().hex[:8].upper()}"
    initialize_database()
    with connect() as conn:
        conn.execute(
            "INSERT INTO app_roles(role_id, name, description, created_at_utc) VALUES (?, ?, ?, ?)",
            (role_id, name, description, _now()),
        )
    return role_id


def list_users() -> list[dict]:
    return _fetch_all(
        """
        SELECT u.*, r.name AS role_name
        FROM app_users u LEFT JOIN app_roles r ON r.role_id = u.role_id
        ORDER BY u.created_at_utc DESC
        """
    )


def get_user_by_email(email: str) -> dict | None:
    return _fetch_one("SELECT * FROM app_users WHERE email = ?", (email.strip().lower(),))


def create_user(email: str, display_name: str, password: str, role_id: str) -> str:
    initialize_database()
    user_id = f"USR-{uuid4().hex[:8].upper()}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO app_users(user_id, email, display_name, password_hash, status, role_id, created_at_utc)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
            """,
            (user_id, email.strip().lower(), display_name.strip(), _hash_password(password), role_id, _now()),
        )
    record_audit_event("auth", "app_users", user_id, "create", after={"email": email, "role_id": role_id})
    return user_id


def set_user_role(user_id: str, role_id: str) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute("UPDATE app_users SET role_id = ? WHERE user_id = ?", (role_id, user_id))


def set_user_status(user_id: str, status: str) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute("UPDATE app_users SET status = ? WHERE user_id = ?", (status, user_id))


def grant_permission(role_id: str, module_name: str, allowed: bool = True) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO app_permissions(permission_id, role_id, module_name, action_name, allowed, created_at_utc)
            VALUES (?, ?, ?, 'view', ?, ?)
            ON CONFLICT(role_id, module_name, action_name)
            DO UPDATE SET allowed = excluded.allowed
            """,
            (f"PRM-{uuid4().hex[:8].upper()}", role_id, module_name, 1 if allowed else 0, _now()),
        )


def permissions_for_role(role_id: str) -> list[dict]:
    return _fetch_all("SELECT * FROM app_permissions WHERE role_id = ?", (role_id,))


def allowed_modules_for_role(role_id: str, role_name: str) -> set[str] | None:
    """None significa "acceso total" (rol Administrador). Si no, deny-by-default."""
    if role_name == ADMIN_ROLE_NAME:
        return None
    rows = permissions_for_role(role_id)
    return {row["module_name"] for row in rows if row.get("allowed")}


# ---------------------------------------------------------------------------
# Sesión / login
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str
    display_name: str
    role_id: str
    role_name: str


def current_user() -> AuthUser | None:
    return st.session_state.get(SESSION_KEY)


def _login_with_row(row: dict) -> None:
    role = _fetch_one("SELECT * FROM app_roles WHERE role_id = ?", (row.get("role_id"),))
    st.session_state[SESSION_KEY] = AuthUser(
        user_id=row["user_id"],
        email=row["email"],
        display_name=row["display_name"],
        role_id=row.get("role_id") or "",
        role_name=(role or {}).get("name", "Sin rol"),
    )


def authenticate(email: str, password: str) -> bool:
    row = get_user_by_email(email)
    if not row or row.get("status") != "active":
        return False
    if not row.get("password_hash") or not _verify_password(password, row["password_hash"]):
        return False
    _login_with_row(row)
    record_audit_event("auth", "app_users", row["user_id"], "login")
    return True


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)


def _bootstrap_first_admin(email: str, display_name: str, password: str) -> None:
    role_id = create_role(ADMIN_ROLE_NAME, "Acceso total a todos los módulos.")
    create_user(email, display_name, password, role_id)
    row = get_user_by_email(email)
    _login_with_row(row)


def require_login() -> bool:
    """Muestra la pantalla de configuración inicial o de login.

    Devuelve True si hay un usuario autenticado en esta sesión (y por lo
    tanto la app puede continuar); False si se debe detener el render
    porque se está mostrando el formulario de login/setup.
    """
    if current_user() is not None:
        return True

    initialize_database()

    st.markdown(
        '<div style="text-align:center;padding:2.2rem 0 1rem;">'
        '<div style="font-weight:900;font-size:1.4rem;color:#1f2937;">CopyMary ERP</div>'
        '<div style="color:#7c8494;">Acceso restringido — inicia sesión para continuar</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    center = st.columns([1, 2, 1])[1]

    if not any_users_exist():
        with center:
            st.info("No hay usuarios todavía. Crea el primer usuario administrador para comenzar.")
            with st.form("auth_bootstrap_form"):
                email = st.text_input("Correo del administrador", key="auth_bootstrap_email")
                display_name = st.text_input("Nombre para mostrar", key="auth_bootstrap_display_name")
                password = st.text_input("Contraseña", type="password", key="auth_bootstrap_password")
                password_confirm = st.text_input("Confirmar contraseña", type="password", key="auth_bootstrap_password_confirm")
                submitted = st.form_submit_button("Crear administrador y entrar", type="primary", use_container_width=True)
            if submitted:
                if not email.strip() or not display_name.strip():
                    st.error("Correo y nombre son obligatorios.")
                elif len(password) < 8:
                    st.error("La contraseña debe tener al menos 8 caracteres.")
                elif password != password_confirm:
                    st.error("Las contraseñas no coinciden.")
                elif get_user_by_email(email):
                    st.error("Ya existe un usuario con ese correo.")
                else:
                    _bootstrap_first_admin(email, display_name, password)
                    st.rerun()
        return False

    with center:
        with st.form("auth_login_form"):
            email = st.text_input("Correo", key="auth_login_email")
            password = st.text_input("Contraseña", type="password", key="auth_login_password")
            submitted = st.form_submit_button("Iniciar sesión", type="primary", use_container_width=True)
        if submitted:
            if authenticate(email, password):
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos, o usuario inactivo.")
    return False
