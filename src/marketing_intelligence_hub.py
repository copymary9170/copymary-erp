"""Inteligencia de marketing basada en auditoría, marca, públicos y KPI."""
from __future__ import annotations
import streamlit as st
from src.session_utils import read_list, save_list, now_iso

KEY="marketing_intelligence_records"
ARCHETYPES=("Inocente","Explorador","Sabio","Héroe","Rebelde","Mago","Persona corriente","Amante","Bufón","Cuidador","Creador","Gobernante")
HOOKS=("Deseo / historia","Número / lista","Pregunta reflexiva","Contraste","Actualidad","Debate")
CHANNELS=("Instagram","TikTok","WhatsApp","Web","E-mail","Tienda física","Volantes / impresos","Eventos","Material POP","Otro")

def kpis(d:dict)->dict:
    followers=max(float(d.get("followers",0) or 0),0); interactions=max(float(d.get("interactions",0) or 0),0); posts=max(float(d.get("posts",0) or 0),0)
    return {"engagement": interactions/followers*100 if followers else 0,"interactions_per_post":interactions/posts if posts else 0}

def potus_ready(d:dict)->tuple[int,list[str]]:
    fields=(("purpose","Propósito"),("objective","Objetivo"),("tactic","Táctica"),("uniqueness","Unicidad"),("segmentation","Segmentación"))
    missing=[label for key,label in fields if not str(d.get(key,"")).strip()]
    return round((len(fields)-len(missing))/len(fields)*100),missing

def render_marketing_intelligence_hub()->None:
    st.header("🧠 Inteligencia de Marketing")
    st.caption("Audita la marca, define públicos, prepara POTUS y mide resultados mensuales.")
    tabs=st.tabs(["Marca y FODA","Públicos + POTUS","Copywriting","Canales","Indicadores"])
    with tabs[0]:
        st.subheader("Marca y auditoría")
        archetype=st.selectbox("Arquetipo de personalidad",ARCHETYPES)
        personality=st.text_area("Personalidad, valores y tono")
        promise=st.text_area("Propuesta de valor / experiencia que queremos asociar a la marca")
        c1,c2=st.columns(2); strengths=c1.text_area("Fortalezas"); weaknesses=c2.text_area("Debilidades")
        c3,c4=st.columns(2); opportunities=c3.text_area("Oportunidades"); threats=c4.text_area("Amenazas")
        if st.button("Guardar auditoría de marca"):
            rows=read_list(KEY); rows.append({"type":"brand_audit","archetype":archetype,"personality":personality,"promise":promise,"strengths":strengths,"weaknesses":weaknesses,"opportunities":opportunities,"threats":threats,"created_at":now_iso()}); save_list(KEY,rows); st.success("Auditoría guardada.")
    with tabs[1]:
        st.subheader("Constructor de público y campaña POTUS")
        product=st.text_input("Producto o servicio"); location=st.text_input("Ubicación"); age=st.text_input("Edad / rango"); interests=st.text_area("Intereses o señales del público")
        purpose=st.text_area("P · Propósito"); objective=st.text_area("O · Objetivo"); tactic=st.text_area("T · Táctica"); uniqueness=st.text_area("U · Unicidad"); segmentation=st.text_area("S · Segmentación")
        score,missing=potus_ready(locals()); st.metric("Preparación POTUS",f"{score}%")
        if missing: st.warning("Falta: "+", ".join(missing))
        st.caption("Para pruebas, prepara al menos 2 conjuntos de anuncios y varios creativos por conjunto; registra resultados antes de declarar un ganador.")
        if st.button("Guardar público POTUS"):
            rows=read_list(KEY); rows.append({"type":"potus","product":product,"location":location,"age":age,"interests":interests,"purpose":purpose,"objective":objective,"tactic":tactic,"uniqueness":uniqueness,"segmentation":segmentation,"score":score,"created_at":now_iso()}); save_list(KEY,rows); st.success("Público guardado.")
    with tabs[2]:
        st.subheader("Laboratorio de copy")
        hook_type=st.selectbox("Tipo de hook",HOOKS); hook=st.text_input("Gancho"); benefit=st.text_area("Beneficio para el cliente"); proof=st.text_area("Prueba / característica que sostiene el beneficio"); cta=st.text_input("CTA")
        st.info("Estructura sugerida: GANCHO → beneficio → prueba → CTA. El copy debe partir del buyer persona y la propuesta de valor, no solo de características.")
    with tabs[3]:
        st.subheader("Mapa multicanal")
        selected=st.multiselect("Canales activos",CHANNELS)
        st.write("Online y offline pueden convivir. Define la función de cada canal y evita estar presente sin objetivo ni indicador.")
        for channel in selected: st.text_input(f"Objetivo de {channel}",key=f"channel_goal_{channel}")
    with tabs[4]:
        st.subheader("Reporte mensual de indicadores")
        month=st.selectbox("Mes",["ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO","SEPT","OCT","NOV","DIC"])
        c1,c2,c3=st.columns(3); followers=c1.number_input("Total seguidores",min_value=0); gained=c2.number_input("Seguidores ganados",min_value=0); posts=c3.number_input("Publicaciones",min_value=0)
        c1,c2,c3=st.columns(3); reach=c1.number_input("Alcance",min_value=0); views=c2.number_input("Visualizaciones",min_value=0); profile=c3.number_input("Visitas al perfil",min_value=0)
        c1,c2,c3,c4=st.columns(4); likes=c1.number_input("Me gusta",min_value=0); comments=c2.number_input("Comentarios",min_value=0); saves=c3.number_input("Guardados",min_value=0); shares=c4.number_input("Compartidos",min_value=0)
        interactions=likes+comments+saves+shares; metrics=kpis({"followers":followers,"interactions":interactions,"posts":posts})
        a,b,c=st.columns(3); a.metric("Interacciones",interactions); b.metric("Engagement",f"{metrics['engagement']:.2f}%"); c.metric("Interacciones/publicación",f"{metrics['interactions_per_post']:.2f}")
        if st.button("Guardar indicadores"):
            rows=read_list(KEY); rows.append({"type":"kpi_month","month":month,"followers":followers,"gained":gained,"posts":posts,"reach":reach,"views":views,"profile_visits":profile,"likes":likes,"comments":comments,"saves":saves,"shares":shares,"interactions":interactions,**metrics,"created_at":now_iso()}); save_list(KEY,rows); st.success("Indicadores guardados.")
