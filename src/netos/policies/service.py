"""Business service for storing policies without applying them."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from netos.persistence.database import Database
from netos.policies.model import Policy, PolicyData
from netos.policies.repository import PolicyRepository


class PolicyValidationError(ValueError):
    """Raised when policy data does not satisfy the domain contract."""


class PolicyNotFoundError(LookupError):
    """Raised when a requested policy does not exist."""


class PolicyConflictError(ValueError):
    """Raised when a policy conflicts with an existing persisted policy."""


class PolicyService:
    def __init__(
        self,
        database: Database,
        repository: PolicyRepository | None = None,
    ) -> None:
        self.repository = repository or PolicyRepository(database)

    def create(self, data: PolicyData | dict[str, object]) -> Policy:
        validated = self._validate(data)
        now = datetime.now(timezone.utc)
        policy = Policy(
            id=str(uuid4()),
            **validated.model_dump(),
            created_at=now,
            updated_at=now,
        )
        try:
            return self.repository.create(policy)
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: policies.name" in str(exc):
                raise PolicyConflictError("policy name already exists") from exc
            raise

    def get(self, policy_id: str) -> Policy:
        policy = self.repository.get(policy_id)
        if policy is None:
            raise PolicyNotFoundError("policy not found")
        return policy

    def list(self) -> list[Policy]:
        return self.repository.list()

    def update(self, policy_id: str, data: PolicyData | dict[str, object]) -> Policy:
        current = self.get(policy_id)
        validated = self._validate(data)
        policy = Policy(
            id=current.id,
            **validated.model_dump(),
            created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        try:
            updated = self.repository.update(policy)
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: policies.name" in str(exc):
                raise PolicyConflictError("policy name already exists") from exc
            raise
        if updated is None:
            raise PolicyNotFoundError("policy not found")
        return updated

    def delete(self, policy_id: str) -> None:
        if not self.repository.delete(policy_id):
            raise PolicyNotFoundError("policy not found")

    @staticmethod
    def _validate(data: PolicyData | dict[str, object]) -> PolicyData:
        try:
            return data if isinstance(data, PolicyData) else PolicyData.model_validate(data)
        except ValidationError as exc:
            raise PolicyValidationError(str(exc)) from exc
