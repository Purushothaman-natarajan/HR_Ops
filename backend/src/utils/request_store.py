"""Module-level singleton for the generic request data store backed by BaseStore."""

from __future__ import annotations

from backend.src.repositories.base_store import BaseStore

request_store = BaseStore(name="request")
