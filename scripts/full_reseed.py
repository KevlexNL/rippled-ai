"""Full DB reset + comprehensive re-seed — WO-RIPPLED-FULL-DB-RESET-SEED-RUN.

Phases:
  1. Pre-reset backup (stats snapshot)
  2. Database reset (truncate data tables, keep source_items + schema)
  3. Full re-seed (detection pipeline on all source_items in chronological order)
  4. Candidate promotion (clarification pipeline on eligible candidates)
  5. Validation + report

Idempotent: safe to re-run. Each phase checks preconditions.

Usage:
    .venv/bin/python scripts/full_reseed.py --phase 1      # Stats only
    .venv/bin/python scripts/full_reseed.py --phase 2      # Truncate
    .venv/bin/python scripts/full_reseed.py --phase 3      # Re-seed detection
    .venv/bin/python scripts/full_reseed.py --phase 4      # Candidate promotion
    .venv/bin/python scripts/full_reseed.py --phase 5      # Validation report
    .venv/bin/python scripts/full_reseed.py --all          # Run all phases sequentially
    .venv/bin/python scripts/full_reseed.py --dry-run      # Preview phase 2 only
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, ".")

from sqlalchemy import and_, func, or_, select, text, update
from app.db.session import get_sync_session
from app.models.orm import CommitmentCandidate, SourceItem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("full_reseed")

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Data tables to truncate — ordered for clarity, CASCADE handles deps.
# source_items is EXCLUDED (we keep raw ingest records).
TRUNCATE_TABLES = [
    "surfacing_audit",
    "candidate_signal_records",
    "signal_processing_stage_runs",
    "signal_processing_runs",
    "llm_judge_runs",
    "candidate_commitments",
    "commitment_event_links",
    "commitment_signals",
    "commitment_ambiguities",
    "lifecycle_transitions",
    "clarifications",
    "signal_feedback",
    "outcome_feedback",
    "adhoc_signals",
    "detection_audit",
    "eval_run_items",
    "eval_runs",
    "eval_datasets",
    "digest_log",
    "commitment_contexts",
    "commitments",
    "commitment_candidates",
    "events",
    "normalization_runs",
    "normalized_signals",
    "raw_signal_ingests",
    "user_commitment_profiles",
]

# Tables to query for stats
STAT_TABLES = [
    "source_items",
    "normalized_signals",
    "commitments",
    "commitment_candidates",
    "raw_signal_ingests",
    "surfacing_audit",
    "lifecycle_transitions",
    "detection_audit",
]


def _query_table_counts(db, tables: list[str]) -> dict[str, int]:
    """Get row counts for a list of tables."""
    counts = {}
    for t in tables:
        try:
            result = db.execute(text(f"SELECT COUNT(*) FROM {t}"))
            counts[t] = result.scalar() or 0
        except Exception as e:
            logger.warning("Could not count %s: %s", t, e)
            counts[t] = -1
    return counts


def _query_source_type_distribution(db) -> dict[str, int]:
    """Get source_items distribution by source_type."""
    result = db.execute(text(
        "SELECT source_type, COUNT(*) FROM source_items GROUP BY source_type ORDER BY source_type"
    ))
    return {row[0]: row[1] for row in result}


def _query_lifecycle_distribution(db) -> dict[str, int]:
    """Get commitments distribution by lifecycle_state."""
    try:
        result = db.execute(text(
            "SELECT lifecycle_state, COUNT(*) FROM commitments "
            "GROUP BY lifecycle_state ORDER BY lifecycle_state"
        ))
        return {row[0]: row[1] for row in result}
    except Exception:
        return {}


# ── Phase 1: Pre-Reset Stats ──────────────────────────────────────


def phase_1_pre_reset_stats() -> dict:
    """Capture pre-reset database statistics and write report."""
    logger.info("═══ PHASE 1: PRE-RESET STATS ═══")

    with get_sync_session() as db:
        counts = _query_table_counts(db, STAT_TABLES)
        source_dist = _query_source_type_distribution(db)
        lifecycle_dist = _query_lifecycle_distribution(db)

        # Candidates stats
        promoted = db.execute(text(
            "SELECT COUNT(*) FROM commitment_candidates WHERE was_promoted = true"
        )).scalar() or 0
        discarded = db.execute(text(
            "SELECT COUNT(*) FROM commitment_candidates WHERE was_discarded = true"
        )).scalar() or 0

    # Write report
    report_path = Path(f"ops/reports/pre-reset-stats-{TODAY}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Pre-Reset Stats — {TODAY}",
        "",
        "## Table Counts",
        "",
        "| Table | Count |",
        "|-------|-------|",
    ]
    for t, c in counts.items():
        lines.append(f"| {t} | {c} |")

    lines += [
        "",
        "## Source Items by Type",
        "",
        "| Source Type | Count |",
        "|------------|-------|",
    ]
    for st, c in source_dist.items():
        lines.append(f"| {st} | {c} |")

    lines += [
        "",
        "## Lifecycle State Distribution",
        "",
        "| State | Count |",
        "|-------|-------|",
    ]
    for state, c in lifecycle_dist.items():
        lines.append(f"| {state} | {c} |")

    lines += [
        "",
        "## Candidate Stats",
        "",
        f"- Promoted: {promoted}",
        f"- Discarded: {discarded}",
        f"- Pending: {counts.get('commitment_candidates', 0) - promoted - discarded}",
        "",
        f"*Generated at {datetime.now(timezone.utc).isoformat()}*",
    ]

    report_path.write_text("\n".join(lines) + "\n")
    logger.info("Pre-reset stats written to %s", report_path)

    for t, c in counts.items():
        logger.info("  %s: %d", t, c)

    return {"counts": counts, "source_dist": source_dist, "report": str(report_path)}


# ── Phase 2: Database Reset ───────────────────────────────────────


def phase_2_reset(dry_run: bool = False) -> dict:
    """Truncate data tables (keep source_items and schema)."""
    logger.info("═══ PHASE 2: DATABASE RESET %s═══", "[DRY RUN] " if dry_run else "")

    with get_sync_session() as db:
        # Pre-truncate counts
        for t in TRUNCATE_TABLES:
            try:
                c = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                if c and c > 0:
                    logger.info("  %s: %d rows (will truncate)", t, c)
            except Exception:
                logger.warning("  %s: table not found (skipping)", t)

        source_count = db.execute(text("SELECT COUNT(*) FROM source_items")).scalar()
        logger.info("  source_items: %d rows (KEEPING)", source_count)

        if dry_run:
            logger.info("[DRY RUN] Would truncate %d tables. source_items preserved.", len(TRUNCATE_TABLES))
            db.rollback()
            return {"status": "dry_run", "tables": len(TRUNCATE_TABLES)}

        # Truncate with CASCADE — single statement for atomicity
        # Filter to only tables that exist
        existing_tables = []
        for t in TRUNCATE_TABLES:
            try:
                db.execute(text(f"SELECT 1 FROM {t} LIMIT 0"))
                existing_tables.append(t)
            except Exception:
                logger.warning("  Skipping non-existent table: %s", t)
                db.rollback()  # Clear the failed transaction

        if existing_tables:
            table_list = ", ".join(existing_tables)
            db.execute(text(f"TRUNCATE {table_list} CASCADE"))
            logger.info("Truncated %d tables.", len(existing_tables))

        # Reset seed_processed_at on all source_items so detection will re-process
        result = db.execute(text(
            "UPDATE source_items SET seed_processed_at = NULL WHERE seed_processed_at IS NOT NULL"
        ))
        logger.info("Reset seed_processed_at on %d source_items.", result.rowcount)

        # Verify truncation
        for t in existing_tables:
            c = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            if c > 0:
                logger.error("  VERIFY FAIL: %s still has %d rows!", t, c)

        remaining = db.execute(text("SELECT COUNT(*) FROM source_items")).scalar()
        logger.info("source_items preserved: %d rows", remaining)

        db.commit()

    return {
        "status": "complete",
        "tables_truncated": len(existing_tables),
        "source_items_preserved": remaining,
    }


# ── Phase 3: Full Re-Seed Detection ──────────────────────────────


def phase_3_reseed(batch_size: int = 50, pause_seconds: int = 120) -> dict:
    """Process all source_items through detection pipeline in batches."""
    logger.info("═══ PHASE 3: FULL RE-SEED DETECTION ═══")

    from app.services.detection import run_detection

    # Get all unprocessed source_items in chronological order
    with get_sync_session() as db:
        total_items = db.execute(
            select(func.count()).select_from(SourceItem).where(
                SourceItem.seed_processed_at.is_(None),
                SourceItem.is_quoted_content.is_(False),
            )
        ).scalar() or 0

        all_ids = db.execute(
            select(SourceItem.id)
            .where(
                SourceItem.seed_processed_at.is_(None),
                SourceItem.is_quoted_content.is_(False),
            )
            .order_by(SourceItem.ingested_at.asc())
        ).scalars().all()

    logger.info("Found %d unprocessed source_items to re-seed", len(all_ids))

    if not all_ids:
        logger.info("Nothing to process — all items already seeded or no items exist.")
        return {"status": "nothing_to_process", "total_items": 0}

    total_processed = 0
    total_candidates = 0
    total_errors = 0
    batch_num = 0

    # Process in batches
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i:i + batch_size]
        batch_num += 1
        batch_start = time.monotonic()
        batch_candidates = 0
        batch_errors = 0

        logger.info("── Batch %d: processing items %d–%d of %d ──",
                     batch_num, i + 1, min(i + batch_size, len(all_ids)), len(all_ids))

        for item_id in batch:
            try:
                with get_sync_session() as db:
                    result = run_detection(str(item_id), db)
                    # Mark as processed
                    db.execute(
                        update(SourceItem)
                        .where(SourceItem.id == item_id)
                        .values(seed_processed_at=func.now())
                    )
                    db.commit()
                candidates_created = len(result) if result else 0
                batch_candidates += candidates_created
                total_processed += 1
            except Exception as e:
                batch_errors += 1
                total_errors += 1
                logger.error("  Error processing item %s: %s", item_id, e)
                # Mark as processed to avoid re-processing on retry
                try:
                    with get_sync_session() as db:
                        db.execute(
                            update(SourceItem)
                            .where(SourceItem.id == item_id)
                            .values(seed_processed_at=func.now())
                        )
                        db.commit()
                except Exception:
                    pass

        total_candidates += batch_candidates
        elapsed = time.monotonic() - batch_start

        # Query running totals
        with get_sync_session() as db:
            commitment_count = db.execute(text("SELECT COUNT(*) FROM commitment_candidates")).scalar() or 0

        logger.info(
            "  Batch %d complete: %d items, %d candidates, %d errors (%.1fs). "
            "Running total: %d candidates.",
            batch_num, len(batch), batch_candidates, batch_errors, elapsed, commitment_count,
        )

        # Pause between batches (except last batch)
        if i + batch_size < len(all_ids):
            logger.info("  Pausing %ds before next batch (rate limit)...", pause_seconds)
            time.sleep(pause_seconds)

    return {
        "status": "complete",
        "total_items": len(all_ids),
        "processed": total_processed,
        "candidates_created": total_candidates,
        "errors": total_errors,
        "batches": batch_num,
    }


# ── Phase 4: Candidate Promotion ─────────────────────────────────


def phase_4_promote() -> dict:
    """Run candidate promotion (clarification pipeline) on eligible candidates."""
    logger.info("═══ PHASE 4: CANDIDATE PROMOTION ═══")

    from app.services.clarification import run_clarification

    now = datetime.now(timezone.utc)

    with get_sync_session() as db:
        candidate_ids = db.execute(
            select(CommitmentCandidate.id).where(
                and_(
                    CommitmentCandidate.was_promoted.is_(False),
                    CommitmentCandidate.was_discarded.is_(False),
                    or_(
                        CommitmentCandidate.observe_until <= now,
                        CommitmentCandidate.observe_until.is_(None),
                        CommitmentCandidate.confidence_score >= D("0.75"),
                    ),
                )
            ).order_by(CommitmentCandidate.created_at.asc())
        ).scalars().all()

    logger.info("Found %d eligible candidates for promotion", len(candidate_ids))

    promoted = 0
    deferred = 0
    skipped = 0
    errors = 0

    for cid in candidate_ids:
        try:
            with get_sync_session() as db:
                result = run_clarification(str(cid), db)

            status = result.get("status", "unknown")
            if status == "clarified":
                promoted += 1
                logger.info("  Promoted candidate %s → commitment %s", cid, result.get("commitment_id"))
            elif status == "deferred":
                deferred += 1
            elif status == "skipped":
                skipped += 1
            else:
                logger.warning("  Unexpected status for %s: %s", cid, result)
        except Exception as e:
            errors += 1
            logger.exception("  Failed to promote candidate %s: %s", cid, e)

    logger.info(
        "Promotion complete: promoted=%d deferred=%d skipped=%d errors=%d total=%d",
        promoted, deferred, skipped, errors, len(candidate_ids),
    )

    return {
        "status": "complete",
        "total_eligible": len(candidate_ids),
        "promoted": promoted,
        "deferred": deferred,
        "skipped": skipped,
        "errors": errors,
    }


# ── Phase 5: Validation Report ───────────────────────────────────


def phase_5_validate() -> dict:
    """Generate post-seed validation report."""
    logger.info("═══ PHASE 5: VALIDATION REPORT ═══")

    with get_sync_session() as db:
        counts = _query_table_counts(db, STAT_TABLES)
        source_dist = _query_source_type_distribution(db)
        lifecycle_dist = _query_lifecycle_distribution(db)

        # Candidate stats
        promoted = db.execute(text(
            "SELECT COUNT(*) FROM commitment_candidates WHERE was_promoted = true"
        )).scalar() or 0
        discarded = db.execute(text(
            "SELECT COUNT(*) FROM commitment_candidates WHERE was_discarded = true"
        )).scalar() or 0

        # Structure completeness
        try:
            structure_complete = db.execute(text(
                "SELECT COUNT(*) FROM commitments WHERE structure_complete = true"
            )).scalar() or 0
        except Exception:
            structure_complete = "N/A"

        # Proposed > 7 days
        try:
            stale_proposed = db.execute(text(
                "SELECT COUNT(*) FROM commitments "
                "WHERE lifecycle_state = 'proposed' "
                "AND created_at < NOW() - INTERVAL '7 days'"
            )).scalar() or 0
        except Exception:
            stale_proposed = "N/A"

        # Items with seed_processed_at set
        processed = db.execute(text(
            "SELECT COUNT(*) FROM source_items WHERE seed_processed_at IS NOT NULL"
        )).scalar() or 0
        unprocessed = db.execute(text(
            "SELECT COUNT(*) FROM source_items WHERE seed_processed_at IS NULL"
        )).scalar() or 0

    # Write report
    report_path = Path(f"ops/reports/post-reset-seed-{TODAY}.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total_commitments = counts.get("commitments", 0)
    pct_complete = (
        f"{(structure_complete / total_commitments * 100):.1f}%"
        if isinstance(structure_complete, int) and total_commitments > 0
        else "N/A"
    )

    lines = [
        f"# Post-Reset Seed Report — {TODAY}",
        "",
        "## Table Counts",
        "",
        "| Table | Count |",
        "|-------|-------|",
    ]
    for t, c in counts.items():
        lines.append(f"| {t} | {c} |")

    lines += [
        "",
        "## Source Items by Type",
        "",
        "| Source Type | Count |",
        "|------------|-------|",
    ]
    for st, c in source_dist.items():
        lines.append(f"| {st} | {c} |")

    lines += [
        "",
        "## Processing Status",
        "",
        f"- Source items processed: {processed}",
        f"- Source items unprocessed: {unprocessed}",
        "",
        "## Commitment Lifecycle Distribution",
        "",
        "| State | Count |",
        "|-------|-------|",
    ]
    for state, c in lifecycle_dist.items():
        lines.append(f"| {state} | {c} |")

    lines += [
        "",
        "## Quality Metrics",
        "",
        f"- Total commitments: {total_commitments}",
        f"- Structure complete: {structure_complete} ({pct_complete})",
        f"- Stale proposed (>7d): {stale_proposed}",
        "",
        "## Candidate Stats",
        "",
        f"- Total candidates: {counts.get('commitment_candidates', 0)}",
        f"- Promoted: {promoted}",
        f"- Discarded: {discarded}",
        f"- Pending: {counts.get('commitment_candidates', 0) - promoted - discarded}",
        "",
        f"*Generated at {datetime.now(timezone.utc).isoformat()}*",
    ]

    report_path.write_text("\n".join(lines) + "\n")
    logger.info("Validation report written to %s", report_path)

    # Print summary to console
    logger.info("── SUMMARY ──")
    for t, c in counts.items():
        logger.info("  %s: %d", t, c)
    logger.info("  structure_complete: %s / %d (%s)", structure_complete, total_commitments, pct_complete)

    return {
        "counts": counts,
        "source_dist": source_dist,
        "lifecycle_dist": lifecycle_dist,
        "structure_complete": structure_complete,
        "stale_proposed": stale_proposed,
        "report": str(report_path),
    }


# ── CLI ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Full DB reset + re-seed (WO-RIPPLED-FULL-DB-RESET-SEED-RUN)"
    )
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5], help="Run a specific phase")
    parser.add_argument("--all", action="store_true", help="Run all phases sequentially")
    parser.add_argument("--dry-run", action="store_true", help="Preview phase 2 truncation only")
    parser.add_argument("--batch-size", type=int, default=50, help="Items per batch in phase 3")
    parser.add_argument("--pause", type=int, default=120, help="Seconds between batches in phase 3")
    args = parser.parse_args()

    if not args.phase and not args.all and not args.dry_run:
        parser.print_help()
        sys.exit(1)

    start = datetime.now(timezone.utc)
    logger.info("Full reseed started at %s", start.isoformat())

    if args.dry_run:
        phase_2_reset(dry_run=True)
        return

    phases_to_run = [args.phase] if args.phase else [1, 2, 3, 4, 5]

    for phase in phases_to_run:
        if phase == 1:
            phase_1_pre_reset_stats()
        elif phase == 2:
            phase_2_reset()
        elif phase == 3:
            phase_3_reseed(batch_size=args.batch_size, pause_seconds=args.pause)
        elif phase == 4:
            phase_4_promote()
        elif phase == 5:
            phase_5_validate()

    end = datetime.now(timezone.utc)
    logger.info("Full reseed completed at %s (%.1fs)", end.isoformat(), (end - start).total_seconds())


if __name__ == "__main__":
    main()
