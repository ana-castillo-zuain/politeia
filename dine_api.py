"""Client and normalizer for the DINE electoral results API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://resultados.mininterior.gob.ar/api"

ELECTION_TYPES = {
    1: "PASO",
    2: "GENERALES",
    3: "SEGUNDA VUELTA",
}

RECOUNT_TYPES = {
    1: "PROVISORIO",
    2: "DEFINITIVO",
}

CARGO_IDS = {
    1: "PRESIDENTE/A",
    2: "SENADOR/A NACIONAL",
    3: "DIPUTADO/A NACIONAL",
    4: "GOBERNADOR/A / JEFE/A DE GOBIERNO",
    5: "CARGO PROVINCIAL — VARÍA POR DISTRITO",
    6: "CARGO PROVINCIAL — VARÍA POR DISTRITO",
    7: "INTENDENTE/A",
    8: "PARLAMENTARIO/A MERCOSUR NACIONAL",
    9: "PARLAMENTARIO/A MERCOSUR PROVINCIAL",
    10: "CONCEJAL/A / MIEMBRO DE JUNTA COMUNAL",
}

DISTRICTS = {
    1: "CIUDAD AUTÓNOMA DE BUENOS AIRES",
    2: "BUENOS AIRES",
    3: "CATAMARCA",
    4: "CÓRDOBA",
    5: "CORRIENTES",
    6: "CHACO",
    7: "CHUBUT",
    8: "ENTRE RÍOS",
    9: "FORMOSA",
    10: "JUJUY",
    11: "LA PAMPA",
    12: "LA RIOJA",
    13: "MENDOZA",
    14: "MISIONES",
    15: "NEUQUÉN",
    16: "RÍO NEGRO",
    17: "SALTA",
    18: "SAN JUAN",
    19: "SAN LUIS",
    20: "SANTA CRUZ",
    21: "SANTA FE",
    22: "SANTIAGO DEL ESTERO",
    23: "TUCUMÁN",
    24: "TIERRA DEL FUEGO, ANTÁRTIDA E ISLAS DEL ATLÁNTICO SUR",
}


def fetch_results(
    *,
    year: int | str,
    election_type: int | str,
    category_id: int | str,
    recount_type: int | str = 1,
    district_id: int | str | None = None,
    provincial_section_id: int | str | None = None,
    section_id: int | str | None = None,
    circuit_id: int | str | None = None,
    mesa_id: int | str | None = None,
    token: str | None = None,
    timeout: int = 60,
) -> tuple[dict[str, Any], str]:
    """Fetch one totalized result and return ``(payload, request_url)``.

    ``election_type`` is 1 for PASO, 2 for general elections, and 3 for
    runoff elections. ``category_id`` is supplied by DINE and is not the
    same as the office name.
    """

    params: dict[str, str | int] = {
        "anioEleccion": year,
        "tipoRecuento": recount_type,
        "tipoEleccion": election_type,
        "categoriaId": category_id,
    }
    optional = {
        "distritoId": district_id,
        "seccionProvincialId": provincial_section_id,
        "seccionId": section_id,
        "circuitoId": circuit_id,
        "mesaId": mesa_id,
    }
    params.update({key: value for key, value in optional.items() if value is not None})
    url = f"{BASE_URL}/resultados/getResultados?{urlencode(params)}"

    headers = {"Accept": "application/json"}
    bearer = token or os.getenv("DINE_API_TOKEN")
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("DINE API returned a response that is not a JSON object")
    return payload, url


def normalize_results(
    payload: dict[str, Any],
    *,
    year: int | str,
    election_type: int | str,
    category_id: int | str,
    district_id: int | str | None = None,
    section_id: int | str | None = None,
    circuit_id: int | str | None = None,
    mesa_id: int | str | None = None,
) -> list[dict[str, Any]]:
    """Flatten one API payload into rows suitable for a long CSV table."""

    state = payload.get("estadoRecuento") or {}
    others = payload.get("valoresTotalizadosOtros") or {}
    other = others[0] if isinstance(others, list) else others
    context = {
        "year": year,
        "election_type": election_type,
        "category_id": category_id,
        "district_id": district_id,
        "section_id": section_id,
        "circuit_id": circuit_id,
        "mesa_id": mesa_id,
        "fecha_totalizacion": payload.get("fechaTotalizacion"),
        "mesas_esperadas": state.get("mesasEsperadas"),
        "mesas_totalizadas": state.get("mesasTotalizadas"),
        "mesas_totalizadas_pct": state.get("mesasTotalizadasPorcentaje"),
        "electores": state.get("cantidadElectores"),
        "votantes": state.get("cantidadVotantes"),
        "participacion_pct": state.get("participacionPorcentaje"),
    }
    rows = []
    for group in payload.get("valoresTotalizadosPositivos") or []:
        row = {**context, "vote_type": "agrupacion"}
        row.update(
            {
                "group_id": group.get("idAgrupacion"),
                "group_name": group.get("nombreAgrupacion"),
                "votes": group.get("votos"),
                "votes_pct": group.get("votosPorcentaje"),
                "blank_votes": None,
                "null_votes": None,
                "contested_votes": None,
            }
        )
        rows.append(row)

    rows.append(
        {
            **context,
            "vote_type": "otros",
            "group_id": None,
            "group_name": None,
            "votes": None,
            "votes_pct": None,
            "blank_votes": other.get("votosEnBlanco"),
            "null_votes": other.get("votosNulos"),
            "contested_votes": other.get("votosRecurridosComandoImpugnados"),
        }
    )
    return rows


def save_json(payload: dict[str, Any], path: str | Path) -> None:
    """Persist the original API payload for provenance and reproducibility."""

    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    # DINE's documented example. Replace the IDs to request another scope.
    payload, url = fetch_results(
        year=2019,
        election_type=1,
        category_id=2,
        district_id=1,
        provincial_section_id=0,
        section_id=3,
        circuit_id="000039",
        mesa_id=1244,
    )
    print(url)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
