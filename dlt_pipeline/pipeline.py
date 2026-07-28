"""
Pipeline dlt : extraction incrémentale des mesures Pioupiou vers Postgres (Neon).

Prérequis :
    pip install dlt[postgres]

Config :
    Renseigner .dlt/secrets.toml (voir secrets.toml.example) avec la
    connection string Neon.

Usage :
    python pipeline.py                          # lance un run incrémental
    python pipeline.py --backfill 2025-01-01    # premier chargement depuis une date
    python pipeline.py --log-level DEBUG        # logs détaillés (payloads, timings)

dlt gère automatiquement :
    - l'état incrémental (dernier timestamp chargé, stocké dans son état interne)
    - la détection de dérive de schéma (nouvelle colonne, changement de type)
    - le staging avant merge dans Postgres
"""

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

import dlt
import requests

STATION_ID = 2176
API_BASE = "https://api.pioupiou.fr/v1/archive"
MAX_WINDOW_DAYS = 31

logger = logging.getLogger("pioupiou_pipeline")


def configure_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s|%(levelname)s|%(name)s|%(message)s",
    )
    # dlt a son propre logger interne ("dlt"), assez verbeux en DEBUG.
    # On le laisse à INFO par défaut pour ne pas noyer nos logs métier,
    # sauf si l'appelant demande explicitement DEBUG.
    if level.upper() != "DEBUG":
        logging.getLogger("dlt").setLevel(logging.INFO)


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

        logger.info("Extraction station=%s de %s à %s", STATION_ID, start.isoformat(), stop.isoformat())

        if start >= stop:
            logger.info("Rien à récupérer : dernier point ingéré déjà >= maintenant.")
            return

        total_rows = 0
        total_chunks = 0
        current = start

        while current < stop:
            chunk_stop = min(current + timedelta(days=MAX_WINDOW_DAYS), stop)
            total_chunks += 1

            params = {
                "start": current.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stop": chunk_stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "format": "json",
            }

            logger.debug("Requête fenêtre %s -> %s (params=%s)", current, chunk_stop, params)
            t0 = time.monotonic()

            try:
                resp = requests.get(f"{API_BASE}/{STATION_ID}", params=params, timeout=30)
                resp.raise_for_status()
            except requests.RequestException:
                logger.error(
                    "Échec de requête pour la fenêtre %s -> %s", current, chunk_stop, exc_info=True
                )
                raise

            elapsed = time.monotonic() - t0
            payload = resp.json()

            # Format réel confirmé par test manuel (curl) : un objet avec
            # "legend" (noms de colonnes, dans l'ordre) et "data" (une liste
            # de lignes, chaque ligne étant une liste de valeurs dans ce
            # même ordre). Ce n'est pas une liste de dicts nommés.
            legend = payload.get("legend", [])
            rows = payload.get("data", [])

            if not legend:
                logger.warning(
                    "Pas de 'legend' dans la réponse pour %s -> %s : payload inattendu, chunk ignoré",
                    current, chunk_stop,
                )
            elif not rows:
                logger.info(
                    "Fenêtre %s -> %s : 0 mesure (station probablement inactive sur cette période, %.2fs)",
                    current, chunk_stop, elapsed,
                )
            else:
                logger.info(
                    "Fenêtre %s -> %s : %d mesures récupérées (%.2fs)",
                    current, chunk_stop, len(rows), elapsed,
                )

            for row in rows:
                record = dict(zip(legend, row))
                record["station_id"] = STATION_ID
                yield record

            total_rows += len(rows)
            current = chunk_stop

        logger.info(
            "Extraction terminée : %d mesures sur %d fenêtre(s)", total_rows, total_chunks
        )

    return measurements


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backfill",
        help="Date de départ pour un premier chargement complet (YYYY-MM-DD). "
        "Sans cette option, dlt reprend automatiquement depuis le dernier run.",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Niveau de log (défaut : INFO)",
    )
    args = parser.parse_args()

    configure_logging(args.log_level)

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
        logger.info("Backfill demandé depuis %s", start_iso)
    else:
        logger.info("Run incrémental (reprise automatique depuis le dernier état dlt)")

    run_start = time.monotonic()
    load_info = pipeline.run(pioupiou_source(start_date=start_iso))
    run_elapsed = time.monotonic() - run_start

    logger.info("Run terminé en %.2fs", run_elapsed)
    logger.info("%s", load_info)

    if load_info.has_failed_jobs:
        logger.error("Le run contient des jobs en échec : %s", load_info.load_packages)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
    
