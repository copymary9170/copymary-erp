"""Administración de usuarios y roles (solo visible/operable para Administrador).

Permite crear roles adicionales a "Administrador" (que siempre tiene acceso
total), asignarles permisos módulo por módulo, y crear/gestionar usuarios.
"""

import streamlit as st

from src import app_shell, auth
from src.components import render_info_card, render_page_header
from src.module_bootstrap import MODULE_RENDERERS


def _all_module_names() -> list[str]:
    names = {"Inicio"}
    names.update(app_shell.FUNCTIONAL_MODULES.keys())
    names.update(name for name, _path, _attr in MODULE_RENDERERS)
    return sorted(names)


def render_users_roles() -> None:
    render_page_header("Usuarios y roles", "Controla quién puede entrar y qué puede ver cada rol.")

    user = auth.current_user()
    if user is None or user.role_name != auth.ADMIN_ROLE_NAME:
        st.error("Solo un usuario con rol Administrador puede administrar usuarios y roles.")
        return

    roles = auth.list_roles()
    users = auth.list_users()

    cols = st.columns(2)
    cols[0].metric("Roles", str(len(roles)))
    cols[1].metric("Usuarios", str(len(users)))

    role_tab, user_tab = st.tabs(("Roles y permisos", "Usuarios"))

    with role_tab:
        st.subheader("Crear rol")
        with st.form("auth_role_form", clear_on_submit=True):
            role_name = st.text_input("Nombre del rol", placeholder="Ej. Ventas, Producción, Finanzas")
            role_description = st.text_input("Descripción", placeholder="Opcional")
            submitted = st.form_submit_button("Crear rol", type="primary", use_container_width=True)
        if submitted:
            if not role_name.strip():
                st.error("El nombre del rol es obligatorio.")
            elif role_name.strip() == auth.ADMIN_ROLE_NAME:
                st.error(f"'{auth.ADMIN_ROLE_NAME}' ya existe y siempre tiene acceso total.")
            else:
                auth.create_role(role_name.strip(), role_description.strip())
                st.success("Rol creado.")
                st.rerun()

        st.divider()
        st.subheader("Permisos por rol")
        non_admin_roles = [role for role in roles if role["name"] != auth.ADMIN_ROLE_NAME]
        if not non_admin_roles:
            st.info(
                f"Solo existe el rol '{auth.ADMIN_ROLE_NAME}', que ya tiene acceso a todo. "
                "Crea otro rol arriba para configurar permisos limitados."
            )
        else:
            role_options = {f"{role['name']}": role for role in non_admin_roles}
            selected_role_name = st.selectbox("Rol a configurar", tuple(role_options.keys()))
            selected_role = role_options[selected_role_name]
            current_permissions = {
                row["module_name"]: bool(row["allowed"])
                for row in auth.permissions_for_role(selected_role["role_id"])
            }
            st.caption("Marca los módulos a los que este rol puede entrar. Lo que no marques queda oculto y bloqueado.")
            with st.form(f"auth_permissions_form_{selected_role['role_id']}"):
                selections = {}
                module_columns = st.columns(3)
                for index, module_name in enumerate(_all_module_names()):
                    with module_columns[index % 3]:
                        selections[module_name] = st.checkbox(
                            module_name,
                            value=current_permissions.get(module_name, False),
                            key=f"perm_{selected_role['role_id']}_{module_name}",
                        )
                save_permissions = st.form_submit_button("Guardar permisos", type="primary", use_container_width=True)
            if save_permissions:
                for module_name, checked in selections.items():
                    auth.grant_permission(selected_role["role_id"], module_name, checked)
                st.success(f"Permisos actualizados para '{selected_role_name}'.")
                st.rerun()

        st.divider()
        for role in roles:
            allowed = auth.allowed_modules_for_role(role["role_id"], role["name"])
            access_label = "Acceso total" if allowed is None else f"{len(allowed)} módulo(s) permitido(s)"
            st.write(f"**{role['name']}** · {access_label}")

    with user_tab:
        st.subheader("Crear usuario")
        if not roles:
            st.info("Primero crea al menos un rol.")
        else:
            role_options = {role["name"]: role for role in roles}
            with st.form("auth_user_form", clear_on_submit=True):
                email = st.text_input("Correo")
                display_name = st.text_input("Nombre para mostrar")
                password = st.text_input("Contraseña temporal", type="password")
                role_name = st.selectbox("Rol", tuple(role_options.keys()))
                submitted_user = st.form_submit_button("Crear usuario", type="primary", use_container_width=True)
            if submitted_user:
                if not email.strip() or not display_name.strip():
                    st.error("Correo y nombre son obligatorios.")
                elif len(password) < 8:
                    st.error("La contraseña debe tener al menos 8 caracteres.")
                elif auth.get_user_by_email(email):
                    st.error("Ya existe un usuario con ese correo.")
                else:
                    auth.create_user(email.strip(), display_name.strip(), password, role_options[role_name]["role_id"])
                    st.success("Usuario creado. Comparte la contraseña temporal por un canal seguro.")
                    st.rerun()

        st.divider()
        st.subheader("Usuarios existentes")
        for row in users:
            info_col, action_col = st.columns([4, 1])
            with info_col:
                st.write(
                    f"**{row['display_name']}** · {row['email']} · rol: {row.get('role_name') or 'sin rol'} · "
                    f"estado: {row['status']}"
                )
            with action_col:
                is_self = row["user_id"] == user.user_id
                if row["status"] == "active":
                    if st.button("Desactivar", key=f"deact_{row['user_id']}", disabled=is_self, use_container_width=True):
                        auth.set_user_status(row["user_id"], "inactive")
                        st.rerun()
                else:
                    if st.button("Reactivar", key=f"react_{row['user_id']}", use_container_width=True):
                        auth.set_user_status(row["user_id"], "active")
                        st.rerun()

    render_info_card(
        "Cómo funciona el acceso",
        f"El rol '{auth.ADMIN_ROLE_NAME}' siempre ve todo. Cualquier otro rol solo ve los módulos "
        "marcados explícitamente aquí — lo no marcado queda oculto y bloqueado, incluso por URL directa.",
        "SEGURIDAD",
    )


app_shell.FUNCTIONAL_MODULES["Usuarios y roles"] = render_users_roles
