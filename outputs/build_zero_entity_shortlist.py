from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


FAMILY_RULES = [
    ("lugar_detail", "/lugar/", "Ficha de lugar; alto potencial de falso negativo"),
    ("en_lugar_detail", "/en/lugar/", "Ficha en ingles; posible hueco de cobertura"),
    ("tipo_lugar", "/tipo-lugar/", "Listado tematico; puede requerir rescate controlado"),
    ("planifica", "/planifica-tu-viaje/", "Pagina utilitaria con recursos o POIs asociados"),
    ("institutional", "/area-profesional/", "Pagina institucional o programatica potencialmente rescatable"),
    ("ayuntamiento", "/ayuntamiento", "Pagina institucional o editorial con posible entidad valida"),
    ("evento", "/evento/", "Ficha o pagina de evento con posible falso negativo"),
]

PREFERRED_URLS = [
    "https://visitpamplonairuna.com/lugar/archivo-real-y-general-de-navarra",
    "https://visitpamplonairuna.com/lugar/catedral-de-santa-maria-la-real",
    "https://visitpamplonairuna.com/lugar/catedral-santa-maria-la-real",
    "https://visitpamplonairuna.com/lugar/capilla-de-san-fermin",
    "https://visitpamplonairuna.com/lugar/espacio-sanfermin-espazioa",
    "https://visitpamplonairuna.com/lugar/ciudadela-y-vuelta-del-castillo",
    "https://visitpamplonairuna.com/lugar/cicloturismo-eurovelo-1",
    "https://visitpamplonairuna.com/lugar/a-bardenas-reales-ribera",
    "https://visitpamplonairuna.com/en/lugar/archivo-real-y-general-de-navarra",
    "https://visitpamplonairuna.com/en/lugares",
    "https://visitpamplonairuna.com/tipo-lugar/deporte",
    "https://visitpamplonairuna.com/tipo-lugar/visitas-en-familia",
    "https://visitpamplonairuna.com/tipo-lugar/lugares-de-interes",
    "https://visitpamplonairuna.com/planifica-tu-viaje",
    "https://visitpamplonairuna.com/planifica-tu-viaje/como-llegar",
    "https://visitpamplonairuna.com/area-profesional/estrategias-y-planes-municipales",
    "https://visitpamplonairuna.com/area-profesional/estudios-e-informes",
    "https://visitpamplonairuna.com/ayuntamiento",
    "https://visitpamplonairuna.com/ayuntamiento/en-familia",
    "https://visitpamplonairuna.com/evento",
]


def load_zero_urls(page_counts_path: Path) -> list[str]:
    data = json.loads(page_counts_path.read_text(encoding="utf-8"))
    urls: list[str] = []
    for page in data.get("pages", []):
        if int(page.get("entityCount", 0) or 0) == 0:
            url = str(page.get("url") or "").strip()
            if url:
                urls.append(url)
    return urls


def classify_family(url: str) -> tuple[str, str]:
    for family, marker, rationale in FAMILY_RULES:
        if marker in url:
            return family, rationale
    path = urlparse(url).path.strip("/")
    if not path:
        return "homepage", "Portada o hub principal; revisar solo si aporta entidad canonica"
    return "other", "Caso frontera; revisar si parece detalle o listado util"


def build_shortlist(urls: list[str], limit: int = 20) -> list[dict]:
    zero_set = set(urls)
    shortlist: list[dict] = []
    seen: set[str] = set()

    for rank, url in enumerate(PREFERRED_URLS, start=1):
        if url not in zero_set or url in seen:
            continue
        family, rationale = classify_family(url)
        shortlist.append(
            {
                "priority": len(shortlist) + 1,
                "family": family,
                "url": url,
                "why_review": rationale,
                "expected": "",
                "actual": "0 entidades",
                "decision": "",
                "notes": "",
            }
        )
        seen.add(url)
        if len(shortlist) >= limit:
            return shortlist

    family_buckets: dict[str, list[str]] = {}
    for url in urls:
        family, _ = classify_family(url)
        family_buckets.setdefault(family, []).append(url)

    family_order = [
        "lugar_detail",
        "en_lugar_detail",
        "tipo_lugar",
        "planifica",
        "institutional",
        "ayuntamiento",
        "evento",
        "other",
        "homepage",
    ]
    for family in family_order:
        for url in family_buckets.get(family, []):
            if url in seen:
                continue
            _, rationale = classify_family(url)
            shortlist.append(
                {
                    "priority": len(shortlist) + 1,
                    "family": family,
                    "url": url,
                    "why_review": rationale,
                    "expected": "",
                    "actual": "0 entidades",
                    "decision": "",
                    "notes": "",
                }
            )
            seen.add(url)
            if len(shortlist) >= limit:
                return shortlist
    return shortlist


def to_markdown(rows: list[dict]) -> str:
    lines = [
        "# Shortlist de URLs sin entidades",
        "",
        "Lista priorizada para revision manual de falsos negativos potenciales.",
        "",
        "| Prioridad | Familia | URL | Motivo de revision | Esperado | Actual | Decision | Notas |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['priority']} | `{row['family']}` | {row['url']} | {row['why_review']} | {row['expected']} | {row['actual']} | {row['decision']} | {row['notes']} |"
        )
    lines.append("")
    lines.append("## Uso sugerido")
    lines.append("")
    lines.append("- Rellena `Esperado`, `Decision` y `Notas` segun tu revision manual.")
    lines.append("- Si una familia acumula varios `si deberia extraer`, la siguiente iteracion deberia atacar ese patron.")
    lines.append("- Si una familia acumula varios `correcto que no extraiga`, se puede rebajar su prioridad.")
    lines.append("")
    return "\n".join(lines)


def to_csv(rows: list[dict]) -> str:
    header = "priority,family,url,why_review,expected,actual,decision,notes"
    lines = [header]
    for row in rows:
        values = [
            str(row["priority"]),
            row["family"],
            row["url"],
            row["why_review"],
            row["expected"],
            row["actual"],
            row["decision"],
            row["notes"],
        ]
        escaped = ['"' + value.replace('"', '""') + '"' for value in values]
        lines.append(",".join(escaped))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye una shortlist de URLs sin entidades para revision manual.")
    parser.add_argument("--page-counts", default="entities_page_counts.json")
    parser.add_argument("--md-output", default="docs/zero_entity_shortlist.md")
    parser.add_argument("--csv-output", default="outputs/zero_entity_shortlist.csv")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    urls = load_zero_urls(Path(args.page_counts))
    rows = build_shortlist(urls, limit=args.limit)
    Path(args.md_output).write_text(to_markdown(rows), encoding="utf-8")
    Path(args.csv_output).write_text(to_csv(rows), encoding="utf-8")
    print(args.md_output)
    print(args.csv_output)


if __name__ == "__main__":
    main()
