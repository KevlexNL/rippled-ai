"""Tests for surfacing_audit user_id column (WO-3).

Validates:
  - ORM model has user_id column with correct constraints
  - SurfacingAudit creation requires user_id
  - surfacing_runner passes user_id when creating audit rows
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


class TestSurfacingAuditSchema:
    """Verify surfacing_audit ORM model has user_id with correct constraints."""

    def test_user_id_column_exists(self):
        from app.models.orm import SurfacingAudit

        table = SurfacingAudit.__table__
        assert "user_id" in table.columns, "user_id column missing from surfacing_audit"

    def test_user_id_is_not_nullable(self):
        from app.models.orm import SurfacingAudit

        col = SurfacingAudit.__table__.columns["user_id"]
        assert col.nullable is False, "user_id should be NOT NULL"

    def test_user_id_has_fk_to_users(self):
        from app.models.orm import SurfacingAudit

        col = SurfacingAudit.__table__.columns["user_id"]
        fks = list(col.foreign_keys)
        assert len(fks) == 1, "user_id should have exactly one FK"
        assert "users.id" in str(fks[0].target_fullname)

    def test_user_id_fk_cascades_on_delete(self):
        from app.models.orm import SurfacingAudit

        col = SurfacingAudit.__table__.columns["user_id"]
        fk = list(col.foreign_keys)[0]
        assert fk.ondelete == "CASCADE"

    def test_user_id_is_indexed(self):
        from app.models.orm import SurfacingAudit

        col = SurfacingAudit.__table__.columns["user_id"]
        assert col.index is True, "user_id should be indexed"


class TestSurfacingRunnerPassesUserId:
    """Verify surfacing_runner.py includes user_id when creating SurfacingAudit rows."""

    def test_audit_row_includes_user_id(self):
        """Parse the surfacing_runner source to verify user_id is set on SurfacingAudit."""
        import inspect
        from app.services import surfacing_runner

        source = inspect.getsource(surfacing_runner.run_surfacing_sweep)
        # Check that user_id=commitment.user_id is passed in SurfacingAudit constructor
        assert "user_id=commitment.user_id" in source, (
            "surfacing_runner must pass user_id=commitment.user_id when creating SurfacingAudit"
        )


class TestSkipEndpointPassesUserId:
    """Verify the skip_commitment endpoint passes user_id to SurfacingAudit."""

    def test_skip_audit_includes_user_id(self):
        import inspect
        from app.api.routes import commitments

        source = inspect.getsource(commitments)
        # The skip endpoint creates SurfacingAudit with user_id=user_id
        assert "user_id=user_id" in source, (
            "skip_commitment must pass user_id when creating SurfacingAudit"
        )
