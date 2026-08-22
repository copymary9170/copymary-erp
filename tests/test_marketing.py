"""Pruebas del módulo de Marketing."""
from src import marketing, module_bootstrap, top_navigation_app

def test_marketing_summary_calculates_core_kpis():
    campaigns=[{"campaign_id":"C1","status":"Activa"},{"campaign_id":"C2","status":"Finalizada"}]
    content=[{"content_id":"P1","status":"Publicado"},{"content_id":"P2","status":"Programado"}]
    metrics=[{"impressions":1000,"clicks":50,"leads":10,"sales":2,"spend":20,"revenue":80},{"impressions":500,"clicks":25,"leads":5,"sales":1,"spend":10,"revenue":40}]
    result=marketing.marketing_summary(campaigns,content,metrics)
    assert result["active_campaigns"]==1
    assert result["published_content"]==1
    assert result["pending_content"]==1
    assert result["impressions"]==1500
    assert result["clicks"]==75
    assert result["leads"]==15
    assert result["sales"]==3
    assert result["spend"]==30
    assert result["revenue"]==120
    assert round(result["ctr"],2)==5.00
    assert round(result["cpl"],2)==2.00
    assert round(result["conversion"],2)==20.00
    assert round(result["roas"],2)==4.00

def test_marketing_summary_handles_zero_denominators():
    result=marketing.marketing_summary([],[],[])
    assert result["ctr"]==0
    assert result["cpl"]==0
    assert result["conversion"]==0
    assert result["roas"]==0

def test_marketing_taxonomy_supports_strategy_and_funnel():
    assert "Educar" in marketing.PILLARS
    assert "Vender" in marketing.PILLARS
    assert marketing.FUNNEL_STAGES[0]=="Descubrimiento"
    assert marketing.FUNNEL_STAGES[-1]=="Fidelización"

def test_marketing_is_registered_as_functional_module():
    assert ("Marketing","src.marketing","render_marketing") in module_bootstrap.MODULE_RENDERERS

def test_marketing_has_its_own_navigation_area():
    assert top_navigation_app.navigation_groups()["Marketing"]==("Marketing",)
