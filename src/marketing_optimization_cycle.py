"""Ciclo de diagnóstico, contenido, medición y aprendizaje para Marketing."""
from __future__ import annotations

from collections import Counter
from uuid import uuid4

import streamlit as st

from src.session_utils import now_iso, read_dict, read_list, save_dict, save_list
from src import marketing_workspace as legacy

AUDIT_KEY = "marketing_presence_audit"
IDEAS_KEY = "marketing_content_bank"
LEARNINGS_KEY = legacy.LEARNINGS_KEY
CONTENT_KEY = legacy.CONTENT_KEY

CHANNELS = ("Instagram", "TikTok", "WhatsApp Business", "Facebook", "Sitio web")
AUDIT_AREAS = {
    "Perfil": ("Identidad reconocible", "Qué vende", "Para quién", "Propuesta de valor", "CTA", "Contacto", "Ubicación / cobertura"),
    "Contenido": ("Feed coherente", "Reels / video", "Historias", "Destacadas", "Portadas", "Copy claro", "Constancia"),
    "Identidad": ("Logo correcto", "Colores de marca", "Tipografías", "Consistencia", "Legibilidad"),
}
STATUS_SCORE = {"Correcto": 100, "Mejorable": 60, "Problema": 20, "Sin evaluar": 0}
CONTENT_GOALS = ("Atraer", "Educar", "Generar confianza", "Mostrar producto", "Vender", "Fidelizar")
FUNNEL_BY_GOAL = {
    "Atraer": "Reconocimiento", "Educar": "Solución", "Generar confianza": "Confianza",
    "Mostrar producto": "Demostración", "Vender": "CTA", "Fidelizar": "Cliente",
}
IDEA_STATUSES = ("Idea", "Guion", "Diseño", "Revisión", "Aprobado", "Programado", "Publicado", "Medido")
PRIORITIES = ("Alta", "Media", "Baja")


def _num(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def audit_score(audit: dict) -> dict:
    """Calcula score total y por área sin inventar evaluaciones faltantes."""
    areas: dict[str, float] = {}
    evaluated = 0
    total = 0.0
    for area, checks in AUDIT_AREAS.items():
        values = []
        for check in checks:
            status = str(audit.get(area, {}).get(check, "Sin evaluar"))
            if status != "Sin evaluar":
                values.append(STATUS_SCORE.get(status, 0))
        areas[area] = sum(values) / len(values) if values else 0.0
        evaluated += len(values)
        total += sum(values)
    return {"score": total / evaluated if evaluated else 0.0, "areas": areas, "evaluated": evaluated}


def five_second_test(audit: dict) -> dict:
    """Evalúa si la propuesta básica puede entenderse rápidamente."""
    profile = audit.get("Perfil", {})
    required = ("Qué vende", "Para quién", "Propuesta de valor", "CTA")
    ok = [name for name in required if profile.get(name) == "Correcto"]
    problems = [name for name in required if profile.get(name) in ("Problema", "Sin evaluar", None)]
    return {"passed": len(ok) == len(required), "ok": ok, "problems": problems, "score": len(ok) / len(required) * 100}


def classify_content_goal(row: dict) -> str:
    goal = str(row.get("marketing_goal") or row.get("goal") or "").strip()
    if goal in CONTENT_GOALS:
        return goal
    stage = str(row.get("funnel_stage") or row.get("funnel") or "").strip()
    mapping = {"Reconocimiento": "Atraer", "Necesidad": "Educar", "Solución": "Educar", "Demostración": "Mostrar producto", "Confianza": "Generar confianza", "CTA": "Vender", "Cliente": "Fidelizar"}
    return mapping.get(stage, "")


def content_balance(content: list[dict]) -> dict:
    counts = Counter(classify_content_goal(row) for row in content if classify_content_goal(row))
    total = sum(counts.values())
    percentages = {goal: (counts.get(goal, 0) / total * 100 if total else 0.0) for goal in CONTENT_GOALS}
    warnings = []
    if total:
        if percentages["Vender"] > 50:
            warnings.append(f"{percentages['Vender']:.0f}% del contenido intenta vender directamente; conviene reforzar atracción, educación o confianza.")
        if counts.get("Atraer", 0) == 0:
            warnings.append("No hay contenido de atracción registrado.")
        if counts.get("Generar confianza", 0) == 0:
            warnings.append("No hay contenido de confianza o prueba social registrado.")
    else:
        warnings.append("Aún no hay contenido suficiente para evaluar el balance.")
    return {"counts": dict(counts), "percentages": percentages, "total": total, "warnings": warnings}


def piece_metrics(row: dict) -> dict:
    reach = _num(row.get("views", row.get("reach")))
    interactions = _num(row.get("interactions"))
    clicks = _num(row.get("clicks"))
    leads = _num(row.get("leads"))
    sales = _num(row.get("sales"))
    revenue = _num(row.get("revenue"))
    spend = _num(row.get("spend"))
    return {
        "reach": reach, "interactions": interactions, "clicks": clicks, "leads": leads, "sales": sales,
        "revenue": revenue, "spend": spend,
        "engagement": interactions / reach * 100 if reach else 0.0,
        "lead_rate": leads / clicks * 100 if clicks else 0.0,
        "sales_rate": sales / leads * 100 if leads else 0.0,
        "roas": revenue / spend if spend else 0.0,
    }


def compare_content(a: dict, b: dict) -> dict:
    ma, mb = piece_metrics(a), piece_metrics(b)
    score_a = ma["sales"] * 5 + ma["leads"] * 2 + ma["interactions"] * 0.05 + ma["reach"] * 0.001
    score_b = mb["sales"] * 5 + mb["leads"] * 2 + mb["interactions"] * 0.05 + mb["reach"] * 0.001
    winner = "A" if score_a > score_b else "B" if score_b > score_a else "Empate"
    return {"a": ma, "b": mb, "winner": winner, "score_a": score_a, "score_b": score_b}


def priority_actions(audit: dict, content: list[dict]) -> list[str]:
    """Devuelve solo acciones sustentadas por problemas observados."""
    actions: list[str] = []
    profile = audit.get("Perfil", {})
    if profile.get("Propuesta de valor") == "Problema":
        actions.append("Reescribir la propuesta de valor para explicar beneficio y diferenciación.")
    if profile.get("CTA") == "Problema":
        actions.append("Hacer visible una llamada a la acción concreta para iniciar la compra o consulta.")
    if profile.get("Qué vende") == "Problema":
        actions.append("Aclarar en el perfil qué productos o servicios ofrece el negocio.")
    balance = content_balance(content)
    actions.extend(balance["warnings"])
    metrics_rows = [piece_metrics(x) for x in content if x.get("status") in ("Publicado", "Medido")]
    if len(metrics_rows) >= 3 and sum(x["leads"] for x in metrics_rows) == 0:
        actions.append("Hay varias publicaciones medidas sin leads: revisar oferta, CTA y captura de consultas.")
    return actions[:3]


def _dashboard(audit: dict, content: list[dict], ideas: list[dict]) -> None:
    score = audit_score(audit)
    measured = [x for x in content if x.get("status") in ("Publicado", "Medido")]
    totals = {k: sum(piece_metrics(x)[k] for x in measured) for k in ("leads", "sales", "revenue", "spend")}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Auditoría", f"{score['score']:.0f}/100" if score["evaluated"] else "Sin evaluar")
    c2.metric("Banco de contenido", len(ideas))
    c3.metric("Leads registrados", int(totals["leads"]))
    c4.metric("Ventas atribuidas", int(totals["sales"]))
    st.markdown("#### Qué hacer ahora")
    actions = priority_actions(audit, content)
    if actions:
        for action in actions:
            st.warning(action)
    else:
        st.success("No hay alertas prioritarias con los datos actuales. Sigue midiendo y comparando contenido.")
    st.markdown("#### Balance de contenido")
    balance = content_balance(content)
    cols = st.columns(3)
    for i, goal in enumerate(CONTENT_GOALS):
        cols[i % 3].metric(goal, balance["counts"].get(goal, 0), f"{balance['percentages'][goal]:.0f}%")


def _audit_view(audit: dict) -> None:
    st.subheader("Auditoría de presencia digital")
    channel = st.selectbox("Canal auditado", CHANNELS, index=0)
    audit.setdefault("channel", channel)
    with st.form("marketing_presence_audit"):
        updated = {k: dict(v) if isinstance(v, dict) else v for k, v in audit.items()}
        updated["channel"] = channel
        for area, checks in AUDIT_AREAS.items():
            st.markdown(f"#### {area}")
            updated.setdefault(area, {})
            for check in checks:
                current = updated[area].get(check, "Sin evaluar")
                options = ("Sin evaluar", "Correcto", "Mejorable", "Problema")
                updated[area][check] = st.selectbox(check, options, index=options.index(current) if current in options else 0, key=f"audit_{area}_{check}")
        notes = st.text_area("Notas del diagnóstico", value=str(audit.get("notes", "")))
        if st.form_submit_button("Guardar auditoría", type="primary", use_container_width=True):
            updated["notes"] = notes.strip()
            updated["updated_at_utc"] = now_iso()
            save_dict(AUDIT_KEY, updated)
            st.rerun()
    score = audit_score(audit)
    if score["evaluated"]:
        st.markdown("#### Resultado")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", f"{score['score']:.0f}/100")
        for col, area in zip((c2, c3, c4), AUDIT_AREAS):
            col.metric(area, f"{score['areas'][area]:.0f}/100")
        quick = five_second_test(audit)
        if quick["passed"]:
            st.success("Prueba de 5 segundos: la oferta básica está clara.")
        else:
            st.warning("Prueba de 5 segundos: revisar " + ", ".join(quick["problems"]) + ".")


def _content_bank(ideas: list[dict]) -> None:
    st.subheader("Banco de contenido")
    with st.form("marketing_content_idea", clear_on_submit=True):
        c1, c2 = st.columns(2)
        title = c1.text_input("Idea / título interno")
        brand = c2.text_input("Marca / línea")
        c1, c2, c3 = st.columns(3)
        channel = c1.selectbox("Canal", CHANNELS)
        goal = c2.selectbox("Objetivo", CONTENT_GOALS)
        priority = c3.selectbox("Prioridad", PRIORITIES)
        c1, c2 = st.columns(2)
        format_ = c1.text_input("Formato", placeholder="Reel, post, historia...")
        status = c2.selectbox("Estado", IDEA_STATUSES)
        problem = st.text_area("Problema, duda o necesidad que aborda")
        hook = st.text_input("Gancho")
        cta = st.text_input("CTA")
        if st.form_submit_button("Guardar idea", type="primary", use_container_width=True) and title.strip():
            row = {"idea_id": f"MKT-IDEA-{uuid4().hex[:8].upper()}", "title": title.strip(), "brand": brand.strip(), "channel": channel, "marketing_goal": goal, "funnel_stage": FUNNEL_BY_GOAL[goal], "priority": priority, "format": format_.strip(), "status": status, "problem": problem.strip(), "hook": hook.strip(), "cta": cta.strip(), "created_at_utc": now_iso()}
            save_list(IDEAS_KEY, [*ideas, row])
            st.rerun()
    if ideas:
        st.dataframe([{"Idea": x.get("title"), "Marca": x.get("brand"), "Objetivo": x.get("marketing_goal"), "Embudo": x.get("funnel_stage"), "Estado": x.get("status"), "Prioridad": x.get("priority")} for x in ideas], use_container_width=True, hide_index=True)


def _calendar(ideas: list[dict], content: list[dict]) -> None:
    st.subheader("Calendario estratégico")
    st.caption("La planificación se revisa por objetivo y etapa, no solo por cantidad de publicaciones.")
    combined = [*ideas, *content]
    balance = content_balance(combined)
    for warning in balance["warnings"]:
        st.warning(warning)
    st.dataframe([{"Contenido": x.get("title", "—"), "Canal": x.get("channel", "—"), "Objetivo": classify_content_goal(x) or "Sin clasificar", "Embudo": x.get("funnel_stage") or x.get("funnel") or "—", "Estado": x.get("status", "—"), "Fecha": x.get("scheduled_date") or x.get("date") or "—"} for x in combined], use_container_width=True, hide_index=True)


def _comparison(content: list[dict]) -> None:
    st.subheader("Comparador de contenido")
    measurable = [x for x in content if x.get("status") in ("Publicado", "Medido")]
    if len(measurable) < 2:
        st.info("Necesitas al menos dos piezas publicadas o medidas para compararlas.")
        return
    c1, c2 = st.columns(2)
    a_idx = c1.selectbox("Pieza A", range(len(measurable)), format_func=lambda i: measurable[i].get("title", f"Pieza {i+1}"), key="cmp_a")
    b_idx = c2.selectbox("Pieza B", range(len(measurable)), format_func=lambda i: measurable[i].get("title", f"Pieza {i+1}"), key="cmp_b", index=1)
    result = compare_content(measurable[a_idx], measurable[b_idx])
    st.info(f"Resultado comparativo: **{result['winner']}**")
    st.dataframe([
        {"Métrica": "Alcance", "A": result["a"]["reach"], "B": result["b"]["reach"]},
        {"Métrica": "Interacciones", "A": result["a"]["interactions"], "B": result["b"]["interactions"]},
        {"Métrica": "Leads", "A": result["a"]["leads"], "B": result["b"]["leads"]},
        {"Métrica": "Ventas", "A": result["a"]["sales"], "B": result["b"]["sales"]},
        {"Métrica": "ROAS", "A": round(result["a"]["roas"], 2), "B": round(result["b"]["roas"], 2)},
    ], use_container_width=True, hide_index=True)


def _learnings() -> None:
    st.subheader("Aprendizajes")
    rows = read_list(LEARNINGS_KEY)
    st.caption("Registra patrones concretos para que las próximas decisiones reutilicen lo que ya funcionó o falló.")
    with st.form("marketing_learning", clear_on_submit=True):
        source = st.text_input("Fuente / publicación / campaña")
        learning = st.text_area("Aprendizaje verificable")
        next_action = st.text_input("Qué probar después")
        if st.form_submit_button("Guardar aprendizaje", type="primary", use_container_width=True) and learning.strip():
            save_list(LEARNINGS_KEY, [*rows, {"learning_id": f"MKT-LRN-{uuid4().hex[:8].upper()}", "source": source.strip(), "learning": learning.strip(), "next_action": next_action.strip(), "created_at_utc": now_iso()}])
            st.rerun()
    for row in reversed(rows[-20:]):
        with st.container(border=True):
            st.write(f"**{row.get('source') or 'Aprendizaje'}**")
            st.write(row.get("learning", ""))
            if row.get("next_action"):
                st.caption("Próxima prueba: " + str(row.get("next_action")))


def render_marketing_optimization_cycle() -> None:
    """Renderiza la capa de diagnóstico y aprendizaje del módulo Marketing."""
    st.subheader("Centro de rendimiento de Marketing")
    st.caption("Diagnostica antes de recomendar, ejecuta con intención y aprende después de publicar.")
    audit = read_dict(AUDIT_KEY)
    content = read_list(CONTENT_KEY)
    ideas = read_list(IDEAS_KEY)
    tab = st.radio("Sección", ("Inicio", "Auditoría", "Banco de contenido", "Calendario", "Comparador", "Aprendizajes"), horizontal=True, label_visibility="collapsed", key="marketing_optimization_tab")
    st.divider()
    if tab == "Auditoría":
        _audit_view(audit)
    elif tab == "Banco de contenido":
        _content_bank(ideas)
    elif tab == "Calendario":
        _calendar(ideas, content)
    elif tab == "Comparador":
        _comparison(content)
    elif tab == "Aprendizajes":
        _learnings()
    else:
        _dashboard(audit, content, ideas)
