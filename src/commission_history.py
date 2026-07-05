import streamlit as st
from src.components import render_page_header
from src.money import format_money

def _rows(key):
    return [dict(x) for x in st.session_state.get(key, []) if isinstance(x, dict)]

def _amount(x):
    value = float(x.get('commission_value_snapshot', 0.0))
    if x.get('commission_mode_snapshot') == 'Monto por venta':
        return value
    return float(x.get('sale_total_snapshot', 0.0)) * value / 100

def render_commission_history():
    render_page_header('Historial de comisiones', 'Consulta los valores guardados por asignación.')
    items = _rows('commission_assignments')
    members = {str(x.get('member_id', '')): x for x in _rows('team_members')}
    sales = {str(x.get('sale_id', '')): x for x in _rows('sales_registry')}
    cols = st.columns(3)
    cols[0].metric('Asignaciones', str(len(items)))
    cols[1].metric('Activas', str(sum(1 for x in items if x.get('active', True))))
    cols[2].metric('Total histórico', format_money(sum(_amount(x) for x in items if x.get('active', True))))
    for item in reversed(items):
        member = members.get(str(item.get('member_id', '')), {})
        sale = sales.get(str(item.get('sale_id', '')), {})
        with st.container(border=True):
            st.markdown(f"### {member.get('name', 'Sin colaborador')} · {item.get('sale_description_snapshot', 'Venta')}")
            c = st.columns(4)
            c[0].metric('Venta guardada', format_money(float(item.get('sale_total_snapshot', 0.0))))
            c[1].metric('Tipo', str(item.get('commission_mode_snapshot', 'Porcentaje')))
            c[2].metric('Valor', str(item.get('commission_value_snapshot', 0.0)))
            c[3].metric('Comisión', format_money(_amount(item)))
            if sale and abs(float(sale.get('total', 0.0)) - float(item.get('sale_total_snapshot', 0.0))) > 0.0001:
                st.warning('La venta cambió, pero el cálculo histórico permanece igual.')
