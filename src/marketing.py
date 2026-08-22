"""Centro de marketing de CopyMary ERP.

Une estrategia, cliente ideal, campañas, calendario editorial, embudo y métricas.
Los registros usan la persistencia write-through del ERP.
"""
from __future__ import annotations
from datetime import date
from uuid import uuid4
import streamlit as st
from src import auth
from src.components import render_info_card, render_page_header
from src.erp_database import record_audit_event
from src.session_utils import now_iso, read_list, save_list

CAMPAIGNS_KEY="marketing_campaigns"; CONTENT_KEY="marketing_content"; METRICS_KEY="marketing_metrics"
STRATEGY_KEY="marketing_strategy"; PERSONAS_KEY="marketing_personas"; FUNNEL_KEY="marketing_funnel"
CHANNELS=("Instagram","TikTok","WhatsApp","Facebook","Tienda física","Otro")
CAMPAIGN_STATUSES=("Planificada","Activa","Pausada","Finalizada")
CONTENT_STATUSES=("Idea","Por diseñar","En revisión","Aprobado","Programado","Publicado")
CONTENT_TYPES=("Post","Reel","Historia","Carrusel","Video","Promoción","Otro")
PILLARS=("Educar","Inspirar","Entretener","Vender","Confianza/Prueba social","Comunidad")
FUNNEL_STAGES=("Descubrimiento","Interés","Consideración","Conversión","Fidelización")


def _actor_id():
    u=auth.current_user(); return u.user_id if u else ""

def _audit(entity,eid,action,after=None):
    record_audit_event("Marketing",entity,eid,action,after=after or {},actor_user_id=_actor_id())

def marketing_summary(campaigns=None,content=None,metrics=None):
    campaigns=read_list(CAMPAIGNS_KEY) if campaigns is None else campaigns; content=read_list(CONTENT_KEY) if content is None else content; metrics=read_list(METRICS_KEY) if metrics is None else metrics
    spend=sum(float(x.get("spend",0) or 0) for x in metrics); revenue=sum(float(x.get("revenue",0) or 0) for x in metrics); leads=sum(int(x.get("leads",0) or 0) for x in metrics); clicks=sum(int(x.get("clicks",0) or 0) for x in metrics); impressions=sum(int(x.get("impressions",0) or 0) for x in metrics); sales=sum(int(x.get("sales",0) or 0) for x in metrics)
    return {"active_campaigns":sum(x.get("status")=="Activa" for x in campaigns),"pending_content":sum(x.get("status")!="Publicado" for x in content),"published_content":sum(x.get("status")=="Publicado" for x in content),"spend":spend,"revenue":revenue,"leads":leads,"clicks":clicks,"impressions":impressions,"sales":sales,"ctr":clicks/impressions*100 if impressions else 0,"cpl":spend/leads if leads else 0,"roas":revenue/spend if spend else 0,"conversion":sales/leads*100 if leads else 0}

def _options(rows,id_key):
    out={"Sin asignar":""}; out.update({str(x.get("name") or x.get("title") or x.get(id_key)):str(x.get(id_key,"")) for x in rows}); return out

def _name(eid,rows,id_key):
    return next((str(x.get("name") or x.get("title") or eid) for x in rows if x.get(id_key)==eid),"Sin asignar")

def _strategy():
    st.subheader("Estrategia de marketing")
    current=(read_list(STRATEGY_KEY) or [{}])[-1]
    with st.form("mkt_strategy"):
        cols=st.columns(2); objective=cols[0].text_area("Objetivo principal",value=current.get("objective",""),placeholder="Qué debe lograr marketing en los próximos 90 días"); value=cols[1].text_area("Propuesta de valor",value=current.get("value_proposition",""),placeholder="Por qué el cliente debería elegirnos")
        cols=st.columns(3); monthly=cols[0].number_input("Meta de ventas atribuibles USD",min_value=0.0,value=float(current.get("sales_goal",0) or 0)); leads=cols[1].number_input("Meta de leads/consultas",min_value=0,value=int(current.get("lead_goal",0) or 0)); budget=cols[2].number_input("Presupuesto mensual USD",min_value=0.0,value=float(current.get("budget",0) or 0))
        positioning=st.text_area("Posicionamiento y mensaje",value=current.get("positioning","")); channels=st.multiselect("Canales prioritarios",CHANNELS,default=[x for x in current.get("channels",[]) if x in CHANNELS]); pillars=st.multiselect("Pilares de contenido",PILLARS,default=[x for x in current.get("pillars",[]) if x in PILLARS])
        if st.form_submit_button("Guardar estrategia",type="primary",use_container_width=True):
            row={"objective":objective.strip(),"value_proposition":value.strip(),"sales_goal":monthly,"lead_goal":leads,"budget":budget,"positioning":positioning.strip(),"channels":channels,"pillars":pillars,"updated_at_utc":now_iso()}; save_list(STRATEGY_KEY,[row]); _audit("marketing_strategy","current","update",row); st.success("Estrategia guardada."); st.rerun()

def _personas():
    st.subheader("Cliente ideal / Buyer persona"); rows=read_list(PERSONAS_KEY)
    with st.form("mkt_persona",clear_on_submit=True):
        name=st.text_input("Nombre del perfil",placeholder="Ej. Madre que necesita resolver impresiones escolares"); cols=st.columns(2); need=cols[0].text_area("Necesidades / deseos"); pain=cols[1].text_area("Problemas / frustraciones"); cols=st.columns(2); objections=cols[0].text_area("Objeciones antes de comprar"); triggers=cols[1].text_area("Qué la impulsa a comprar"); channels=st.multiselect("Dónde podemos alcanzarlo",CHANNELS)
        if st.form_submit_button("Guardar cliente ideal",type="primary",use_container_width=True) and name.strip():
            row={"persona_id":f"MKT-PER-{uuid4().hex[:8].upper()}","name":name.strip(),"need":need.strip(),"pain":pain.strip(),"objections":objections.strip(),"triggers":triggers.strip(),"channels":channels,"created_at_utc":now_iso()}; save_list(PERSONAS_KEY,[*rows,row]); _audit("marketing_persona",row["persona_id"],"create",row); st.rerun()
    for x in reversed(rows):
        with st.container(border=True): st.write(f"**{x.get('name')}**"); st.caption(f"Necesidad: {x.get('need','')} · Objeciones: {x.get('objections','')}")

def _campaigns(campaigns):
    st.subheader("Campañas"); personas=read_list(PERSONAS_KEY); popts=_options(personas,"persona_id")
    with st.form("mkt_campaign",clear_on_submit=True):
        name=st.text_input("Nombre de campaña"); objective=st.text_input("Objetivo SMART / resultado esperado"); cols=st.columns(3); channel=cols[0].selectbox("Canal",CHANNELS); status=cols[1].selectbox("Estado",CAMPAIGN_STATUSES); persona=cols[2].selectbox("Cliente ideal",tuple(popts))
        cols=st.columns(3); start=cols[0].date_input("Inicio",date.today()); end=cols[1].date_input("Cierre",date.today()); budget=cols[2].number_input("Presupuesto USD",min_value=0.0)
        offer=st.text_area("Oferta / propuesta de campaña"); cta=st.text_input("CTA principal"); kpi=st.text_input("KPI principal",placeholder="Leads, ventas, ROAS, mensajes...")
        submitted=st.form_submit_button("Crear campaña",type="primary",use_container_width=True)
    if submitted:
        if not name.strip(): st.error("El nombre es obligatorio.")
        elif end<start: st.error("La fecha de cierre no puede ser anterior al inicio.")
        else:
            row={"campaign_id":f"MKT-CMP-{uuid4().hex[:8].upper()}","name":name.strip(),"objective":objective.strip(),"persona_id":popts[persona],"channel":channel,"status":status,"start_date":start.isoformat(),"end_date":end.isoformat(),"budget":budget,"offer":offer.strip(),"cta":cta.strip(),"kpi":kpi.strip(),"created_at_utc":now_iso()}; save_list(CAMPAIGNS_KEY,[*campaigns,row]); _audit("marketing_campaign",row["campaign_id"],"create",row); st.rerun()
    for x in reversed(campaigns):
        with st.container(border=True): st.write(f"**{x.get('name')}** · {x.get('status')} · {x.get('channel')}"); st.caption(f"{x.get('objective','')} · Presupuesto ${float(x.get('budget',0) or 0):,.2f} · KPI: {x.get('kpi','No definido')}")

def _content(campaigns,content):
    st.subheader("Plan y calendario de contenido"); copts=_options(campaigns,"campaign_id")
    with st.form("mkt_content",clear_on_submit=True):
        title=st.text_input("Idea / título"); cols=st.columns(4); ctype=cols[0].selectbox("Formato",CONTENT_TYPES); channel=cols[1].selectbox("Canal",CHANNELS); pillar=cols[2].selectbox("Pilar",PILLARS); stage=cols[3].selectbox("Etapa del embudo",FUNNEL_STAGES)
        cols=st.columns(3); status=cols[0].selectbox("Estado",CONTENT_STATUSES); pub=cols[1].date_input("Fecha",date.today()); campaign=cols[2].selectbox("Campaña",tuple(copts))
        hook=st.text_input("Gancho / primera frase"); copy=st.text_area("Copy / desarrollo"); cta=st.text_input("CTA"); cols=st.columns(2); canva=cols[0].text_input("Enlace de Canva"); path=cols[1].text_input("Ruta del archivo")
        submitted=st.form_submit_button("Agregar al plan",type="primary",use_container_width=True)
    if submitted and title.strip():
        row={"content_id":f"MKT-CNT-{uuid4().hex[:8].upper()}","title":title.strip(),"content_type":ctype,"channel":channel,"pillar":pillar,"funnel_stage":stage,"status":status,"publish_date":pub.isoformat(),"campaign_id":copts[campaign],"hook":hook.strip(),"copy":copy.strip(),"cta":cta.strip(),"canva_url":canva.strip(),"folder_path":path.strip(),"created_at_utc":now_iso()}; save_list(CONTENT_KEY,[*content,row]); _audit("marketing_content",row["content_id"],"create",row); st.rerun()
    filters=st.columns(4); fch=filters[0].selectbox("Canal",("Todos",*CHANNELS),key="mkt_fch"); fp=filters[1].selectbox("Pilar",("Todos",*PILLARS),key="mkt_fp"); fs=filters[2].selectbox("Embudo",("Todos",*FUNNEL_STAGES),key="mkt_fs"); fst=filters[3].selectbox("Estado",("Todos",*CONTENT_STATUSES),key="mkt_fst")
    rows=[x for x in content if (fch=="Todos" or x.get("channel")==fch) and (fp=="Todos" or x.get("pillar")==fp) and (fs=="Todos" or x.get("funnel_stage")==fs) and (fst=="Todos" or x.get("status")==fst)]
    for x in sorted(rows,key=lambda r:str(r.get("publish_date",""))):
        with st.container(border=True): st.write(f"**{x.get('publish_date','')} · {x.get('title')}**"); st.caption(f"{x.get('channel')} · {x.get('content_type')} · {x.get('pillar','')} · {x.get('funnel_stage','')} · {x.get('status')}"); st.write(x.get("hook","") or x.get("copy",""))

def _funnel():
    st.subheader("Embudo y seguimiento de oportunidades"); rows=read_list(FUNNEL_KEY)
    with st.form("mkt_funnel",clear_on_submit=True):
        cols=st.columns(3); source=cols[0].selectbox("Origen",CHANNELS); stage=cols[1].selectbox("Etapa",FUNNEL_STAGES); value=cols[2].number_input("Valor potencial USD",min_value=0.0); contact=st.text_input("Contacto / referencia"); notes=st.text_input("Notas")
        if st.form_submit_button("Registrar oportunidad",type="primary",use_container_width=True):
            row={"lead_id":f"MKT-LEAD-{uuid4().hex[:8].upper()}","source":source,"stage":stage,"value":value,"contact":contact.strip(),"notes":notes.strip(),"created_at_utc":now_iso()}; save_list(FUNNEL_KEY,[*rows,row]); _audit("marketing_lead",row["lead_id"],"create",row); st.rerun()
    counts={s:sum(x.get("stage")==s for x in rows) for s in FUNNEL_STAGES}; cols=st.columns(len(FUNNEL_STAGES))
    for i,s in enumerate(FUNNEL_STAGES): cols[i].metric(s,str(counts[s]))

def _metrics(campaigns,metrics):
    st.subheader("Métricas y rentabilidad"); copts=_options(campaigns,"campaign_id")
    with st.form("mkt_metrics",clear_on_submit=True):
        campaign=st.selectbox("Campaña",tuple(copts)); cols=st.columns(4); impressions=cols[0].number_input("Impresiones",min_value=0); reach=cols[1].number_input("Alcance",min_value=0); clicks=cols[2].number_input("Clics",min_value=0); leads=cols[3].number_input("Leads",min_value=0); cols=st.columns(3); sales=cols[0].number_input("Ventas",min_value=0); spend=cols[1].number_input("Inversión USD",min_value=0.0); revenue=cols[2].number_input("Ingresos USD",min_value=0.0)
        if st.form_submit_button("Registrar métricas",type="primary",use_container_width=True):
            row={"metric_id":f"MKT-MET-{uuid4().hex[:8].upper()}","campaign_id":copts[campaign],"date":date.today().isoformat(),"impressions":impressions,"reach":reach,"clicks":clicks,"leads":leads,"sales":sales,"spend":spend,"revenue":revenue,"created_at_utc":now_iso()}; save_list(METRICS_KEY,[*metrics,row]); _audit("marketing_metric",row["metric_id"],"create",row); st.rerun()
    s=marketing_summary([],[],metrics); cols=st.columns(5); cols[0].metric("CTR",f"{s['ctr']:.2f}%"); cols[1].metric("CPL",f"${s['cpl']:.2f}"); cols[2].metric("Conversión",f"{s['conversion']:.2f}%"); cols[3].metric("ROAS",f"{s['roas']:.2f}x"); cols[4].metric("Ingresos",f"${s['revenue']:,.2f}")

def _summary(campaigns,content,metrics):
    s=marketing_summary(campaigns,content,metrics); cols=st.columns(5); cols[0].metric("Campañas activas",s["active_campaigns"]); cols[1].metric("Por publicar",s["pending_content"]); cols[2].metric("Leads",s["leads"]); cols[3].metric("Ventas",s["sales"]); cols[4].metric("ROAS",f"{s['roas']:.2f}x")
    st.markdown("### Próximas publicaciones"); upcoming=sorted([x for x in content if x.get("status")!="Publicado"],key=lambda x:str(x.get("publish_date","")))[:7]
    for x in upcoming:
        with st.container(border=True): st.write(f"**{x.get('publish_date','')} · {x.get('title')}**"); st.caption(f"{x.get('channel')} · {x.get('pillar','Sin pilar')} · {x.get('funnel_stage','Sin etapa')}")
    if not upcoming: st.caption("No hay publicaciones pendientes.")

def render_marketing():
    render_page_header("Marketing","Convierte la estrategia en contenido, campañas, oportunidades y ventas medibles.")
    campaigns=read_list(CAMPAIGNS_KEY); content=read_list(CONTENT_KEY); metrics=read_list(METRICS_KEY)
    tabs=st.tabs(("Resumen","Estrategia","Cliente ideal","Campañas","Contenido","Embudo","Métricas"))
    with tabs[0]: _summary(campaigns,content,metrics)
    with tabs[1]: _strategy()
    with tabs[2]: _personas()
    with tabs[3]: _campaigns(campaigns)
    with tabs[4]: _content(campaigns,content)
    with tabs[5]: _funnel()
    with tabs[6]: _metrics(campaigns,metrics)
    render_info_card("Flujo recomendado","Define estrategia y cliente ideal → crea campañas → planifica contenido por pilar y etapa del embudo → registra oportunidades → mide CTR, CPL, conversión y ROAS.","MARKETING")
