"""Relación entre procesos productivos, activos y productos del catálogo."""

from __future__ import annotations

from collections.abc import Iterable


PROCESS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("printing_bw", "Impresión B/N"),
    ("printing_color", "Impresión color"),
    ("photo_printing", "Impresión fotográfica"),
    ("copying", "Copiado"),
    ("scanning", "Escaneo"),
    ("design", "Diseño"),
    ("cutting", "Corte"),
    ("laminating", "Plastificado o laminado"),
    ("foil", "Aplicación de foil"),
    ("binding", "Encuadernación"),
    ("perforating", "Perforado"),
    ("sublimation_print", "Impresión para sublimación"),
    ("heat_press", "Prensado o termofijado"),
    ("engraving", "Grabado"),
    ("finishing", "Acabado manual"),
    ("printing_3d", "Impresión 3D"),
    ("laser_engraving", "Grabado o corte láser"),
    ("pvc_card_print", "Impresión de carnets PVC"),
    ("thermal_print", "Impresión térmica (tickets/etiquetas)"),
    ("tattoo_stencil", "Esténcil de tatuaje"),
)

PROCESS_LABELS = dict(PROCESS_OPTIONS)
ACTIVE_ASSET_STATUSES = {"Activo", "Disponible"}


def normalize_process_codes(values: object) -> tuple[str, ...]:
    """Normaliza procesos guardados por versiones anteriores o datos manuales."""
    if isinstance(values, str):
        raw_values: Iterable[object] = (values,)
    elif isinstance(values, (list, tuple, set)):
        raw_values = values
    else:
        raw_values = ()
    valid = set(PROCESS_LABELS)
    return tuple(dict.fromkeys(str(value) for value in raw_values if str(value) in valid))


def process_labels(process_codes: Iterable[str]) -> list[str]:
    return [PROCESS_LABELS[code] for code in process_codes if code in PROCESS_LABELS]


def asset_is_available_for_costing(asset: object) -> bool:
    status = str(getattr(asset, "status", "Activo"))
    participates = bool(getattr(asset, "participates_in_costing", True))
    processes = normalize_process_codes(getattr(asset, "process_codes", ()))
    return status in ACTIVE_ASSET_STATUSES and participates and bool(processes)


def assets_for_processes(assets: Iterable[object], required_processes: Iterable[str]) -> list[object]:
    """Obtiene activos disponibles que pueden ejecutar al menos un proceso requerido."""
    required = set(normalize_process_codes(tuple(required_processes)))
    if not required:
        return []
    selected: list[object] = []
    for asset in assets:
        if not asset_is_available_for_costing(asset):
            continue
        asset_processes = set(normalize_process_codes(getattr(asset, "process_codes", ())))
        if required.intersection(asset_processes):
            selected.append(asset)
    return selected


def equipment_cost_for_processes(assets: Iterable[object], required_processes: Iterable[str]) -> float:
    """Suma una vez la depreciación de cada activo necesario para los procesos."""
    return sum(float(getattr(asset, "depreciation_per_unit", 0.0)) for asset in assets_for_processes(assets, required_processes))


def process_coverage(assets: Iterable[object], required_processes: Iterable[str]) -> tuple[set[str], set[str]]:
    """Devuelve procesos cubiertos y procesos sin ningún activo disponible."""
    required = set(normalize_process_codes(tuple(required_processes)))
    covered: set[str] = set()
    for asset in assets_for_processes(assets, required):
        covered.update(required.intersection(normalize_process_codes(getattr(asset, "process_codes", ()))))
    return covered, required - covered
