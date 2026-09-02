"""Seed the database by running the real workflow end to end.

    create tables -> bootstrap -> import the sample workbook -> free slots
    -> automated scheduling -> confirm -> import evaluations

Run:  python -m scripts.seed [--reset] [--no-schedule]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine, session_scope  # noqa: E402
from app.core.logging_config import configure_logging, get_logger  # noqa: E402
from app.models import Base  # noqa: E402
from app.schemas.scheduling import GenerateScheduleRequest  # noqa: E402
from app.services.bootstrap import bootstrap_database  # noqa: E402
from app.services.excel_service import ExcelService  # noqa: E402
from app.services.free_slot_service import FreeSlotService  # noqa: E402
from app.services.scheduling_service import SchedulingService  # noqa: E402
from scripts.generate_samples import SAMPLES_DIR, main as generate_samples  # noqa: E402

logger = get_logger("seed")


def import_file(db, path: Path) -> dict:
    service = ExcelService(db)
    upload = service.store_upload(filename=path.name, content=path.read_bytes())
    return service.import_upload(upload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the interview system")
    parser.add_argument("--reset", action="store_true",
                        help="Drop every table before seeding")
    parser.add_argument("--no-schedule", action="store_true",
                        help="Import data but do not run the scheduler")
    parser.add_argument("--no-evaluations", action="store_true",
                        help="Skip importing the sample evaluations")
    args = parser.parse_args()

    configure_logging()
    if args.reset:
        logger.info("Dropping all tables")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    if not (SAMPLES_DIR / "interview_data.xlsx").exists():
        generate_samples()

    with session_scope() as db:
        bootstrap_database(db)

        result = import_file(db, SAMPLES_DIR / "interview_data.xlsx")
        logger.info("Imported workbook: %s created, %s updated, %s failed",
                    result["total_created"], result["total_updated"],
                    result["total_failed"])

        stats = FreeSlotService(db).recalculate()
        logger.info("Free slots: %s row(s) for %s faculty",
                    stats["slots_created"], stats["faculty_processed"])

        if not args.no_schedule:
            service = SchedulingService(db)
            preview = service.generate_preview(GenerateScheduleRequest())
            logger.info("Scheduling run %s: %s scheduled, %s unscheduled, "
                        "success rate %s%%", preview["run_code"],
                        len(preview["scheduled"]), len(preview["unscheduled"]),
                        preview["success_rate"])
            confirmation = service.confirm(preview["run_id"])
            logger.info("Confirmed: %s interview(s) created",
                        confirmation["interviews_created"])

        if not args.no_evaluations:
            evaluation_result = import_file(db, SAMPLES_DIR / "evaluations.xlsx")
            logger.info("Imported evaluations: %s created, %s updated",
                        evaluation_result["total_created"],
                        evaluation_result["total_updated"])

    print("\nSeeding complete. Sign in with the bootstrap administrator:")
    print("  email:    admin@example.com")
    print("  password: admin123")


if __name__ == "__main__":
    main()
