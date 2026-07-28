"""
Pipeline dlt : extraction incrémentale des mesures Pioupiou vers Postgres (Neon).

Prérequis :
    pip install dlt[postgres]

Config :
    Renseigner .dlt/secrets.toml (voir secrets.toml.example) avec la
    connection string Neon.

Usage :
    python pipeline.py                 # lance un run incrémental
    python pipeline.py --backfill 2025-01-01   # premier chargement depuis une date

dlt gère automatiquement :
    - l'état incrémental (dernier timestamp chargé, stocké dans son état interne)
    - la détection de dérive de schéma (nouvelle colonne, changement de type)
    - le staging avant merge dans Postgres
"""

import argparse
from datetime import datetime, timedelta, timezone

import dlt
import requests

STATION_ID = 2176
API_BASE = "https://api.pioupiou.fr/v1/archive"
MAX_WINDOW_DAYS = 31


@dlt.source
def pioupiou_source(start_date: str = None):
    @dlt.resource(
        name="measurements",
        write_disposition="merge",
        primary_key=["station_id", "time"],
         columns={"pressure": {"data_type": "text", "nullable": True}},
    )
    def measurements(
        # dlt.sources.incremental gère automatiquement la reprise depuis
        # le dernier point ingéré lors des runs suivants.
        # "time" est le nom réel du champ temporel dans le payload API
        # (voir "legend" dans la réponse), pas "timestamp".
        updated_at=dlt.sources.incremental(
            "time",
            initial_value=start_date or (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),
        ),
    ):
        start = datetime.fromisoformat(updated_at.last_value)
        stop = datetime.now(timezone.utc)

        current = start
        while current < stop:
            chunk_stop = min(current + timedelta(days=MAX_WINDOW_DAYS), stop)

            params = {
                "start": current.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stop": chunk_stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "format": "json",
            }
            resp = requests.get(f"{API_BASE}/{STATION_ID}", params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()

            # Format réel confirmé par test manuel (curl) : un objet avec
            # "legend" (noms de colonnes, dans l'ordre) et "data" (une liste
            # de lignes, chaque ligne étant une liste de valeurs dans ce
            # même ordre). Ce n'est pas une liste de dicts nommés.
            legend = payload.get("legend", [])
            rows = payload.get("data", [])

            for row in rows:
                record = dict(zip(legend, row))
                record["station_id"] = STATION_ID
                yield record

            current = chunk_stop

    return measurements


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backfill",
        help="Date de départ pour un premier chargement complet (YYYY-MM-DD). "
        "Sans cette option, dlt reprend automatiquement depuis le dernier run.",
        default=None,
    )
    args = parser.parse_args()

    pipeline = dlt.pipeline(
        pipeline_name="pioupiou_2176",
        destination="postgres",
        dataset_name="raw_pioupiou",
    )

    start_iso = None
    if args.backfill:
        start_iso = datetime.strptime(args.backfill, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ).isoformat()

    load_info = pipeline.run(pioupiou_source(start_date=start_iso))
    print(load_info)


if __name__ == "__main__":
    main()
