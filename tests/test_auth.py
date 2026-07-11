"""Pruebas de autenticación y control de acceso por rol (`src/auth.py`)."""

from __future__ import annotations

import pytest

from src import auth


# ---------------------------------------------------------------------------
# Hash de contraseñas
# ---------------------------------------------------------------------------

def test_password_hash_uses_unique_salt_each_time():
    hash_a = auth._hash_password("mi-clave-segura")
    hash_b = auth._hash_password("mi-clave-segura")

    # Mismo password, pero salts distintos -> hashes distintos.
    assert hash_a != hash_b
    assert "$" in hash_a


def test_verify_password_accepts_correct_password():
    stored = auth._hash_password("mi-clave-segura")
    assert auth._verify_password("mi-clave-segura", stored) is True


def test_verify_password_rejects_wrong_password():
    stored = auth._hash_password("mi-clave-segura")
    assert auth._verify_password("clave-incorrecta", stored) is False


def test_verify_password_rejects_malformed_stored_value():
    """Un valor sin `$` (corrupto o vacío) no debe lanzar excepción."""
    assert auth._verify_password("cualquier-cosa", "no-tiene-formato-valido") is False


# ---------------------------------------------------------------------------
# Roles y permisos (deny-by-default)
# ---------------------------------------------------------------------------

def test_admin_role_has_unrestricted_access(isolated_database):
    role_id = auth.create_role(auth.ADMIN_ROLE_NAME)
    modules = auth.allowed_modules_for_role(role_id, auth.ADMIN_ROLE_NAME)
    # None es el valor especial que significa "acceso total".
    assert modules is None


def test_non_admin_role_denies_by_default(isolated_database):
    role_id = auth.create_role("Vendedor")
    modules = auth.allowed_modules_for_role(role_id, "Vendedor")
    # Sin filas explícitas en app_permissions, no debe tener acceso a nada.
    assert modules == set()


def test_granting_permission_allows_specific_module(isolated_database):
    role_id = auth.create_role("Vendedor")
    auth.grant_permission(role_id, "Ventas", allowed=True)

    modules = auth.allowed_modules_for_role(role_id, "Vendedor")
    assert modules == {"Ventas"}


def test_revoking_permission_removes_access(isolated_database):
    role_id = auth.create_role("Vendedor")
    auth.grant_permission(role_id, "Ventas", allowed=True)
    auth.grant_permission(role_id, "Ventas", allowed=False)

    modules = auth.allowed_modules_for_role(role_id, "Vendedor")
    assert modules == set()


def test_create_role_is_idempotent_by_name(isolated_database):
    first_id = auth.create_role("Contador")
    second_id = auth.create_role("Contador")
    assert first_id == second_id


# ---------------------------------------------------------------------------
# Autenticación de usuarios
# ---------------------------------------------------------------------------

def test_create_user_and_authenticate_success(isolated_database):
    role_id = auth.create_role(auth.ADMIN_ROLE_NAME)
    auth.create_user("admin@copymary.test", "Admin", "clave-larga-123", role_id)

    assert auth.authenticate("admin@copymary.test", "clave-larga-123") is True
    assert auth.current_user() is not None
    assert auth.current_user().email == "admin@copymary.test"


def test_authenticate_fails_with_wrong_password(isolated_database):
    role_id = auth.create_role(auth.ADMIN_ROLE_NAME)
    auth.create_user("admin@copymary.test", "Admin", "clave-larga-123", role_id)

    assert auth.authenticate("admin@copymary.test", "clave-incorrecta") is False
    assert auth.current_user() is None


def test_authenticate_fails_for_unknown_email(isolated_database):
    assert auth.authenticate("nadie@copymary.test", "cualquier-cosa") is False


def test_authenticate_fails_for_inactive_user(isolated_database):
    role_id = auth.create_role(auth.ADMIN_ROLE_NAME)
    user_id = auth.create_user("admin@copymary.test", "Admin", "clave-larga-123", role_id)
    auth.set_user_status(user_id, "inactive")

    assert auth.authenticate("admin@copymary.test", "clave-larga-123") is False


def test_logout_clears_current_user(isolated_database):
    role_id = auth.create_role(auth.ADMIN_ROLE_NAME)
    auth.create_user("admin@copymary.test", "Admin", "clave-larga-123", role_id)
    auth.authenticate("admin@copymary.test", "clave-larga-123")

    auth.logout()
    assert auth.current_user() is None


def test_any_users_exist_reflects_database_state(isolated_database):
    assert auth.any_users_exist() is False
    role_id = auth.create_role(auth.ADMIN_ROLE_NAME)
    auth.create_user("admin@copymary.test", "Admin", "clave-larga-123", role_id)
    assert auth.any_users_exist() is True
