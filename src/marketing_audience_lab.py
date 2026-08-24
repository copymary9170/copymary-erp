"""Laboratorio de audiencias para Meta Ads basado en la clase de segmentación/retargeting."""
from __future__ import annotations

from uuid import uuid4
import streamlit as st
from src.session_utils import now_iso, read_list, save_list

AUDIENCES_KEY = "marketing_audience_lab"
TEMPERATURES = ("Fría", "Caliente", "Remarketing")
SOURCES = ("Intereses / segmentación", "Instagram", "Facebook", "Video", "Formulario", "Sitio web", "Lista de clientes", "WhatsApp / CRM", "Otra")


def audience_diagnostics(row: dict) -> list[str]:
    notes=[]
    temp=row.get("temperature")
    if temp == "Fría" and not str(row.get("interests", "")).strip():
        notes.append("La audiencia fría no documenta intereses, amplitud o lógica de prospección.")
    if temp in ("Caliente", "Remarketing") and int(row.get("retention_days", 0) or 0) <= 0:
        notes.append("Define una ventana temporal para saber qué interacción hace que una persona permanezca en esta audiencia.")
    if temp == "Remarketing" and not str(row.get("exclude", "")).strip():
        notes.append("El remarketing no tiene exclusiones. Considera excluir compradores o personas que ya completaron la acción objetivo.")
    if not str(row.get("purpose", "")).strip():
        notes.append("Define para qué etapa del embudo usarás esta audiencia.")
    return notes


def render_audience_lab() -> None:
    st.markdown("## Audiencias y remarketing")
    st.caption("Diseña públicos fríos, calientes y de remarketing antes de replicarlos en Meta Ads.")
    rows=read_list(AUDIENCES_KEY)
    tab1,tab2,tab3=st.tabs(("Crear audiencia", "Mapa de temperaturas", "Auditar"))
    with tab1:
        with st.form("audience_lab_form", clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            name=c1.text_input("Nombre de audiencia")
            temperature=c2.selectbox("Temperatura", TEMPERATURES)
            source=c3.selectbox("Fuente", SOURCES)
            purpose=st.text_input("Objetivo / etapa del embudo", placeholder="Ej. captar nuevos usuarios, recuperar interesados, cerrar venta")
            c1,c2=st.columns(2)
            location=c1.text_input("Ubicación")
            retention=c2.number_input("Ventana de retención (días)", min_value=0, value=30, step=1)
            interests=st.text_area("Segmentación, intereses o condición de inclusión", placeholder="Intereses, personas que interactuaron, vieron video, visitaron web...")
            exclude=st.text_area("Exclusiones", placeholder="Compradores, leads ya convertidos, empleados, otra audiencia...")
            message=st.text_area("Mensaje/oferta para este público", placeholder="Qué necesita escuchar este público según su nivel de conocimiento")
            submitted=st.form_submit_button("Guardar audiencia", type="primary", use_container_width=True)
        if submitted:
            row={"audience_id":f"AUD-{uuid4().hex[:8].upper()}","name":name.strip(),"temperature":temperature,"source":source,"purpose":purpose.strip(),"location":location.strip(),"retention_days":int(retention),"interests":interests.strip(),"exclude":exclude.strip(),"message":message.strip(),"created_at_utc":now_iso()}
            save_list(AUDIENCES_KEY,[*rows,row]); st.rerun()
    with tab2:
        st.markdown("### Estructura de audiencias")
        st.write("**Público frío** → personas que todavía no han mostrado una relación suficiente con la marca; se trabaja prospección y descubrimiento.")
        st.write("**Público caliente** → personas que ya interactuaron, consumieron contenido o mostraron señales de interés.")
        st.write("**Remarketing** → personas con una señal concreta previa a las que se vuelve a impactar con un mensaje más cercano a la conversión.")
        st.info("La temperatura no reemplaza el embudo: sirve para decidir qué público recibe cada mensaje y qué exclusiones evitan solapamientos.")
    with tab3:
        if not rows:
            st.info("Todavía no hay audiencias guardadas.")
        else:
            labels=[f"{r.get('name','Sin nombre')} · {r.get('temperature','')}" for r in rows]
            selected=st.selectbox("Audiencia", labels)
            row=rows[labels.index(selected)]
            st.write({"Temperatura":row.get("temperature"),"Fuente":row.get("source"),"Ventana":f"{row.get('retention_days',0)} días","Objetivo":row.get("purpose"),"Excluir":row.get("exclude") or "—"})
            issues=audience_diagnostics(row)
            if issues:
                for issue in issues: st.warning(issue)
            else:
                st.success("La audiencia documenta fuente, objetivo, ventana y exclusiones de forma coherente.")
