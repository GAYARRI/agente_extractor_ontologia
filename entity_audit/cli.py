#!/usr/bin/env python3
import argparse
from pathlib import Path

from .export import export_audit_buckets, export_by_class, export_summary
from .io_utils import load_entities
from .metrics import compute_audit


def print_section(title: str) -> None:
    print("=" * 100)
    print(title)
    print("=" * 100)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audita entidades: deduplicación, clases más precisas, "
            "rescates de clases genéricas, conflictos y exportación por clase."
        )
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="entities.json",
        help="Ruta al archivo JSON (por defecto: entities.json)",
    )
    parser.add_argument(
        "--export-dir",
        help="Directorio opcional para exportar JSONs de auditoría",
    )
    parser.add_argument(
        "--multi-class",
        action="store_true",
        help="Cuenta todas las clases válidas por entidad en vez de solo la clase principal",
    )
    args = parser.parse_args()

    json_path = Path(args.json_file)
    data = load_entities(json_path)

    audit = compute_audit(data, multi_class=args.multi_class)
    summary = audit["summary"]
    stats_by_class = audit["stats_by_class"]
    ambiguous_pair_counter = audit["ambiguous_pair_counter"]

    print_section("RESUMEN GENERAL")
    print(f"Entidades detectadas (raw):                {summary['total_raw_entities']}")
    print(f"Entidades únicas estimadas:                {summary['total_unique_entities_estimated']}")
    print(f"Duplicados estimados:                      {summary['duplicate_entities_estimated']}")
    print(f"Grupos duplicados:                         {summary['duplicate_groups']}")
    print(f"Entidades con imagen:                      {summary['with_image']}")
    print(f"Entidades con coordenadas:                 {summary['with_coordinates']}")
    print()

    quality = summary["primary_class_quality"]
    print_section("CALIDAD DE CLASIFICACIÓN")
    print(f"Clase primaria específica:                 {quality.get('specific', 0)}")
    print(f"Clase primaria genérica:                   {quality.get('generic', 0)}")
    print(f"Clase primaria ausente (SIN_TIPO):         {quality.get('missing', 0)}")
    print(f"Conflictos entre class y types:            {summary['class_conflicts']}")
    print(f"Entidades ambiguas (>=2 clases específicas): {summary['ambiguous_entities']}")
    print(f"Entidades rescatadas por reglas:           {summary['rescued_entities']}")
    print(f"Entidades con campos esperados incompletos: {summary['entities_with_missing_expected_fields']}")
    print()

    print_section("DESGLOSE POR CLASE")
    print(
        f"{'Clase':30} {'Total':>8} {'Img':>8} {'Coords':>8} "
        f"{'Prim.gen':>10} {'Rescatadas':>12} {'Faltan campos':>15}"
    )
    print("-" * 100)

    for cls, stats in sorted(
        stats_by_class.items(),
        key=lambda item: (-item[1]["total"], item[0].lower())
    ):
        print(
            f"{cls:30} "
            f"{stats['total']:>8} "
            f"{stats['with_image']:>8} "
            f"{stats['with_coordinates']:>8} "
            f"{stats['generic_primary']:>10} "
            f"{stats['rescued_primary']:>12} "
            f"{stats['missing_expected_fields']:>15}"
        )

    if ambiguous_pair_counter:
        print()
        print_section("PARES DE CLASES MÁS AMBIGUOS")
        print(f"{'Par de clases':50} {'Casos':>8}")
        print("-" * 100)
        for pair, count in ambiguous_pair_counter.most_common(10):
            print(f"{' / '.join(pair):50} {count:>8}")

    if args.export_dir:
        export_dir = Path(args.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        export_by_class(export_dir, audit["entities_by_class"])
        export_audit_buckets(export_dir, audit["audit_buckets"])
        export_summary(export_dir, summary)

        print()
        print(f"Export de auditoría generado en: {export_dir.resolve()}")


if __name__ == "__main__":
    main()