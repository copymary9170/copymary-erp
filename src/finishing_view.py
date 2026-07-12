"""Vista genérica compartida por los módulos de acabado.

`finishing_laminating.py`, `finishing_cutting_cameo.py` y
`finishing_sublimation.py` son capas delgadas sobre `render_finishing_stage`:
cada una sólo declara su etapa, sus palabras clave de material/máquina y el
texto de la página. Evita triplicar la misma cola, el mismo formulario de
"completar" y el mismo consumo de inventario/activo en tres archivos casi
idénticos.
"""

from __future__ import annotations

import streamlit as st

from src.components import render_info_card, render_page_header
from src.finishing_jobs import assets_by_keyword, complete_job, jobs_for_stage, material_options, start_job


def render_finishing_stage(
    *,
    stage: str,
    title: str,
    subtitle: str,
    material_keywords: tuple[str, ...],
    material_label: str,
    asset_keywords: tuple[str, ...],
    asset_label: str,
    footer_note: str,
) -> None:
    render_page_header(title, subtitle)

    pending = jobs_for_stage(stage)
    done = jobs_for_stage(stage, include_done=True)
    completed = [job for job in done if job.get("status") == "Completado"]

    metrics = st.columns(3)
    metrics[0].metric("Pendientes", str(len(pending)))
    metrics[1].metric("Completados", str(len(completed)))
    metrics[2].metric("Total recibidos", str(len(done)))

    if not pending:
        st.info(f"No hay trabajos pendientes en {stage}. Los trabajos llegan aquí desde \"Análisis y costeo de impresión\" u otros módulos que envíen a esta etapa.")
    else:
        materials = material_options(*material_keywords)
        usable_materials = [item for item in materials if item["valid_cost"] and item["available"]]
        machines = assets_by_keyword(*asset_keywords)

        if not usable_materials:
            st.warning(f"No hay {material_label.lower()} con costo y existencia válidos en Inventario. Podrás completar el trabajo, pero sin descuento automático de material.")
        if not machines:
            st.caption(f"No hay {asset_label.lower()} registrada en Activos; el uso de máquina no se sumará automáticamente.")

        for job in pending:
            with st.container(border=True):
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"**{job.get('finishing_id')} · {job.get('description') or 'Trabajo de acabado'}**")
                cols[0].caption(f"Origen: {job.get('source_job_id') or 'independiente'} · Solicitado por {job.get('requested_by')} · {job.get('created_at_utc', '')[:16].replace('T', ' ')}")
                cols[1].metric("Estado", str(job.get("status")))
                cols[2].metric("Cantidad", str(job.get("quantity", 1)))

                if job.get("status") == "Pendiente" and st.button("Iniciar", key=f"start_{job['finishing_id']}", use_container_width=True):
                    start_job(job["finishing_id"])
                    st.rerun()

                with st.form(f"complete_{job['finishing_id']}", clear_on_submit=True):
                    material_labels = {f"{item['name']} · stock {item['stock']:,.2f} {item['unit']}": item for item in usable_materials}
                    selected_material = st.selectbox(material_label, ("Sin descuento de material", *material_labels.keys()), key=f"mat_{job['finishing_id']}")
                    material_qty = st.number_input("Cantidad de material usada", min_value=0.0, value=0.0, step=1.0, key=f"matqty_{job['finishing_id']}")
                    machine_labels = {f"{m.get('name', 'Máquina')}": m for m in machines}
                    selected_machine = st.selectbox(asset_label, ("Sin registrar uso", *machine_labels.keys()), key=f"mac_{job['finishing_id']}")
                    machine_units = st.number_input("Unidades de uso de máquina", min_value=0.0, value=float(job.get("quantity", 1) or 0), step=1.0, key=f"macunits_{job['finishing_id']}")
                    note = st.text_input("Nota", key=f"note_{job['finishing_id']}")
                    submitted = st.form_submit_button("Completar trabajo", type="primary", use_container_width=True)
                if submitted:
                    material = material_labels.get(selected_material)
                    machine = machine_labels.get(selected_machine)
                    complete_job(
                        job["finishing_id"],
                        material_item_id=material["item_id"] if material else "",
                        material_quantity=material_qty if material else 0.0,
                        asset_id=machine.get("asset_id", "") if machine else "",
                        machine_units=machine_units if machine else 0.0,
                        note=note,
                    )
                    st.success(f"{job['finishing_id']} completado.")
                    st.rerun()

    if completed:
        st.markdown("#### Historial reciente")
        for job in list(reversed(completed))[:50]:
            st.write(
                f"**{job.get('finishing_id')}** · {job.get('description') or ''} · "
                f"material: {job.get('material_used', 0)} ({'descontado' if job.get('material_deducted') else 'no descontado'}) · "
                f"{job.get('completed_at_utc', '')[:16].replace('T', ' ')}"
            )

    render_info_card(stage, footer_note, "ACABADOS")
