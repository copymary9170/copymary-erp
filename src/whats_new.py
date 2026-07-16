"""Novedades para CopyMary ERP.

Lista visible dentro de la app de los módulos y mejoras nuevos, para que se
puedan encontrar sin tener que revisar el historial de commits o el
README. Cada entrada tiene un botón que lleva directo al módulo nuevo.

Se actualiza a mano al agregar cambios significativos — no es un historial
automático, es una guía para el usuario. Está pensada para ser eliminada o
recortada cuando las novedades dejen de serlo (típicamente después de
2-3 meses de uso).
"""

from __future__ import annotations

import streamlit as st

from src import app_shell
from src.components import render_info_card, render_page_header


WHATS_NEW = (
    {
        "title": "Nivel de tinta actual por impresora, con foto",
        "target": "Ficha técnica de impresoras",
        "category": "Nuevo",
        "description": "Nueva pestaña 'Nivel de tinta actual' dentro de la Ficha técnica de cada impresora: registra el porcentaje de tinta por color (K/C/M/Y), con una foto del tanque/panel o una captura del software de la impresora. A propósito NO se acumula historial: cada foto nueva reemplaza a la anterior del mismo tipo (Tanque o Software), así el respaldo general nunca se llena de fotos viejas. Avisa cuando algún color baja de 15% según la lectura más reciente.",
    },
    {
        "title": "Historial de mantenimiento y repuestos instalados por activo",
        "target": "Activos",
        "category": "Nuevo",
        "description": "Cada activo tiene ahora un desplegable 'Mantenimiento y repuestos instalados' para registrar el momento real en que se cambió una pieza (cuchilla, tapete, cabezal) — distinto de solo tenerla disponible en Inventario. Si el repuesto salió de una existencia registrada ahí, se descuenta de verdad al confirmar el mantenimiento, con el mismo mecanismo que ya usan Producción y los módulos de acabado. Nota: para mantenimiento preventivo con fechas de vencimiento y recordatorios ya existe el módulo 'Mantenimiento de máquinas' — este historial es para el evento puntual de reemplazo, no un calendario de mantenimiento.",
    },
    {
        "title": "Patrimonio total (Activos + Inventario) y categoría para accesorios",
        "target": "Activos",
        "category": "Nuevo",
        "description": "Activos ahora muestra el 'Patrimonio total': el valor en libros de tus equipos (ya con la depreciación descontada) más el valor de lo que tienes en Inventario ahora mismo, en un solo número. También se agregó la categoría 'Accesorio o herramienta menor' para registrar cosas de bajo costo (kits, extensiones, herramientas de corte) sin forzar todo el detalle de compra — basta con nombre, categoría y costo; el resto de campos son opcionales.",
    },
    {
        "title": "Registrar equipos ya existentes, sin costo de compra",
        "target": "Activos",
        "category": "Nuevo",
        "description": "Antes, registrar un activo exigía un costo de compra mayor que cero — imposible para un equipo que ya se tenía (heredado, regalado, comprado hace tiempo sin factura). Ahora hay una casilla 'Este equipo ya se tenía / no hay costo de compra registrado' que permite guardarlo en $0 sin bloquear el formulario, dejándolo disponible para cotizar igual (con depreciación en cero, a menos que se ponga un valor estimado).",
    },
    {
        "title": "Casilla para marcar si un equipo pagó aranceles",
        "target": "Activos",
        "category": "Nuevo",
        "description": "Al registrar un equipo, el campo de aranceles/derechos de importación ahora viene con una casilla 'Pagó aranceles' que hay que marcar explícitamente — muchos equipos comprados localmente no pagan aranceles, y antes el campo en 0 no distinguía entre 'no aplica' y 'no se llenó'. Si la casilla no está marcada, el detalle de la compra muestra 'No aplica' en vez de un 0.00 ambiguo.",
    },
    {
        "title": "Costo de compra detallado en Activos",
        "target": "Activos",
        "category": "Nuevo",
        "description": "Registrar un equipo ya no pide solo un 'costo de adquisición' suelto. Ahora pide proveedor, moneda de la compra, tasa de cambio usada (sugerida automáticamente, editable), método de pago, fecha de compra, N° de factura, garantía, y el costo del equipo, envío/flete/aduana, aranceles de importación e impuestos pagados (ej. IVA) por separado. El costo de adquisición que usa el ERP para la depreciación se calcula solo, convirtiendo todo eso a la moneda base del ERP — mismo criterio que ya se usa en el costo de compra detallado de Inventario. El detalle completo queda visible en un desplegable por cada equipo.",
    },
    {
        "title": "IVA conectado a ventas, redondeo a 2 decimales e historial de tasas",
        "target": "Configuración General",
        "category": "Nuevo",
        "description": "Tres mejoras juntas: (1) el IVA ya se aplica de verdad en Venta rápida y Comercial con una casilla manual 'Esta venta cobra IVA' — se suma al total que paga el cliente, y la comisión del medio de pago/IGTF se calculan sobre ese total ya con IVA, porque es el monto real que se procesa. (2) Todos los montos de dinero en el desglose de ventas (subtotal, IVA, comisión, IGTF, neto) se redondean a 2 decimales — las tasas de cambio y costos unitarios internos conservan más precisión a propósito, el redondeo aplica al precio final. (3) Cada vez que se guarda Configuración General queda una foto en el historial (quién y cuándo), visible en un desplegable dentro de la misma página, para poder responder '¿a qué tasa se guardó tal día?' sin depender de la memoria.",
    },
    {
        "title": "Tasa BCV Euro agregada",
        "target": "Configuración General",
        "category": "Nuevo",
        "description": "Faltaba: Configuración General ya guarda también la tasa oficial del BCV para el euro (VES por 1 EUR), aparte de la tasa BCV en dólares — visible en el resumen, en la franja de tasas siempre visible, y accesible para cualquier módulo vía payment_fees.exchange_rate('BCV (EUR)').",
    },
    {
        "title": "Franja de tasas y comisiones siempre visible",
        "target": "Cualquier área",
        "category": "Nuevo",
        "description": "Debajo del encabezado de cada área (excepto en Configuración General, donde ya se ve el detalle completo) aparece ahora una franja compacta con BCV, Binance, Kontigo (entrada/salida, tasa y comisión), IVA, IGTF, pago móvil y punto de venta — para no tener que entrar a Configuración General solo para recordar qué tasa está vigente. El punto de color al inicio de la franja se pone verde si las tasas se confirmaron hoy, y rojo si no.",
    },
    {
        "title": "Aviso cuando las tasas de cambio no se han actualizado hoy",
        "target": "Configuración General",
        "category": "Nuevo",
        "description": "Cada vez que se guarda Configuración General se registra la fecha y hora. Si pasa un día sin volver a guardar (o revisar) las tasas BCV, Binance o Kontigo, aparece un aviso — tanto dentro de Configuración General (con cuántos días llevan sin actualizarse) como un banner visible en cualquier otra área del sistema, para no tener que entrar a revisar manualmente si ya se cuadraron las tasas del día.",
    },
    {
        "title": "Comisiones e IGTF conectados a Venta rápida y Comercial",
        "target": "Venta rápida de mostrador",
        "category": "Nuevo",
        "description": "Las tasas y comisiones de Configuración General ya no son solo números guardados: Venta rápida de mostrador y Comercial ahora calculan automáticamente cuánto queda realmente después de la comisión del medio de pago (pago móvil, punto de venta, Kontigo). El IGTF, en cambio, queda siempre a decisión manual con una casilla en cada venta — se sugiere marcada para pagos en divisas/cripto (Zelle, Binance, Kontigo), pero no se aplica solo, porque hay operaciones que quedan exentas según el caso. El cliente sigue pagando el mismo total; lo que cambia es que ahora cada venta guarda también cuánto llegó neto, para que cuadre con lo que realmente entra a caja/banco. Cualquier otro módulo puede usar el mismo cálculo importando `src.payment_fees`.",
    },
    {
        "title": "Tasas de cambio y comisiones en Configuración General",
        "target": "Configuración General",
        "category": "Nuevo",
        "description": "Configuración General ahora guarda las tasas BCV, Binance/paralelo y Kontigo (entrada y salida, porque son distintas por el spread), la comisión propia de Kontigo por entrada y por salida (aparte de la tasa de cambio), además del IVA, el IGTF y las comisiones de pago móvil y punto de venta/tarjeta. De paso se corrigió un bug real que impedía restaurar cualquier respaldo: el validador del respaldo general se había quedado con el esquema viejo de Configuración General (antes de que se conectara con Activos), así que 'Restaurar respaldo' fallaba siempre con 'La configuración general no tiene la estructura esperada'. Ahora sigue el esquema actual y, además, los campos que falten (como estas tasas nuevas en un respaldo viejo) se completan con su valor por defecto en vez de romper la restauración.",
    },
    {
        "title": "Costo de compra detallado en Inventario",
        "target": "Inventario",
        "category": "Nuevo",
        "description": "Al registrar un artículo o una nueva entrada, Inventario ahora pide el detalle real de la compra: proveedor, moneda, tasa de cambio usada, método de pago, costo del material, envío/flete e impuestos por separado. El costo unitario se calcula automáticamente sobre ese total real (\"landed cost\"), no solo el precio de lista. También se puede registrar el contenido físico de cada unidad (cm², g o ml) para calcular merma más adelante en Plastificado, Corte en Cameo y Sublimado.",
    },
    {
        "title": "Confirmar trabajo impreso y enviarlo a acabado",
        "target": "Análisis y costeo de impresión",
        "category": "Nuevo",
        "description": "\"Análisis y costeo de impresión\" ya no es solo una cotización: al confirmar un trabajo, descuenta el papel real de Inventario y suma el uso en el contador de páginas de la impresora en Activos. Desde ahí puede enviarse directo a las nuevas colas de Plastificado, Corte en Cameo o Sublimado, que también descuentan su material (laminado, vinil, blancos) y registran el uso de la máquina correspondiente, sin retipear nada.",
    },
    {
        "title": "Venta rápida de mostrador",
        "target": "Venta rápida de mostrador",
        "category": "Nuevo",
        "description": "Cobra fotocopias, impresiones y ventas sueltas sin registrar cliente. Tarifario configurable ya cargado con precios típicos de papelería (fotocopia B/N y color, impresión, escaneo, plastificado, anillado). Las ventas aparecen automáticamente en el Estado de Resultados, flujo de caja y comisiones.",
    },
    {
        "title": "Estado de Resultados (P&L)",
        "target": "Estado de Resultados",
        "category": "Nuevo",
        "description": "Reporte gerencial mensual consolidado: ingresos − costo de ventas − gastos operativos − nómina = utilidad neta. Con margen bruto/neto, desglose de gastos por categoría, y tendencia de 6 meses.",
    },
    {
        "title": "Flujo de caja proyectado",
        "target": "Flujo de caja proyectado",
        "category": "Nuevo",
        "description": "Posición de efectivo esperada a 30, 60 y 90 días. Combina cuentas por cobrar (con vencimientos), cuentas por pagar, gastos recurrentes y nómina activa. Alerta si algún horizonte muestra caja negativa.",
    },
    {
        "title": "RRHH y nómina",
        "target": "RRHH y nómina",
        "category": "Nuevo",
        "description": "Registro de empleados y recibos de pago por período (salario + bonos − deducciones = neto), con cierre de período y bitácora de auditoría. No calcula prestaciones sociales ni retenciones de ley — eso lo valida el contador.",
    },
    {
        "title": "Mantenimiento preventivo de máquinas",
        "target": "Mantenimiento preventivo",
        "category": "Nuevo",
        "description": "Calendario de mantenimiento por máquina (sublimadora, plotter, impresoras). Alerta de atrasados y próximos a vencer. Al registrar un mantenimiento realizado se reprograma automáticamente la próxima fecha.",
    },
    {
        "title": "Base de datos PostgreSQL",
        "target": None,
        "category": "Infraestructura",
        "description": "El sistema ahora puede correr sobre PostgreSQL además de SQLite. Se activa con la variable de entorno COPYMARY_DATABASE_URL. Ver README.md y DEPLOY.md.",
    },
    {
        "title": "Despliegue self-hosted con Docker",
        "target": None,
        "category": "Infraestructura",
        "description": "Guía completa (DEPLOY.md) para poner el sistema en producción en un VPS propio: Docker + PostgreSQL + HTTPS automático + respaldos diarios, sin depender de ningún proveedor específico.",
    },
    {
        "title": "Bloqueo temporal por intentos de login fallidos",
        "target": None,
        "category": "Seguridad",
        "description": "Tras 5 intentos fallidos consecutivos, la cuenta se bloquea 15 minutos para prevenir ataques de fuerza bruta.",
    },
    {
        "title": "Suite de pruebas automáticas",
        "target": None,
        "category": "Calidad",
        "description": "Más de 240 pruebas automáticas cubriendo la lógica de negocio central: autenticación, base de datos, costeo, inventario, producción, comisiones, caja, conciliación, nómina, estado de resultados, flujo de caja y mantenimiento.",
    },
)


def render_whats_new() -> None:
    render_page_header("Novedades", "Módulos y mejoras recientes agregados al sistema.")
    st.caption("Toca 'Abrir' en cada tarjeta para ir directo al módulo nuevo.")

    categories = {}
    for item in WHATS_NEW:
        categories.setdefault(item["category"], []).append(item)

    category_order = ("Nuevo", "Infraestructura", "Seguridad", "Calidad")
    for category in category_order:
        items = categories.get(category, ())
        if not items:
            continue
        st.markdown(f"### {category}")
        for item in items:
            with st.container(border=True):
                cols = st.columns([5, 1])
                cols[0].markdown(f"**{item['title']}**")
                cols[0].write(item["description"])
                if item.get("target"):
                    if cols[1].button("Abrir", key=f"open_{item['title']}", use_container_width=True):
                        app_shell.go_to(item["target"])

    render_info_card(
        "Sobre esta página",
        "Se actualiza a mano cuando se agregan cambios significativos. Cuando las novedades ya no lo sean, esta página se puede recortar o eliminar.",
        "GUÍA",
    )


app_shell.FUNCTIONAL_MODULES["Novedades"] = render_whats_new
