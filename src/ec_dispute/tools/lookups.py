"""Deterministic lookup tools for A1 and A2.

OWNER: Thanh vien 2 (Data & Entities)

Builds OrderFacts and CustomerContext. No LLM in here: the agent decides which tool to
call and how to read the result, the tool does the retrieval.
"""

from __future__ import annotations

from ec_dispute.contracts import CustomerContext, OrderFacts
from ec_dispute.data_store import DataStore


def build_order_facts(store: DataStore, order_id: str) -> OrderFacts:
    """A1. Remember: 6/50 cases have no item row -> has_items=False and empty lists."""
    raise NotImplementedError("TODO(TV2)")


def build_customer_context(store: DataStore, customer_id: str, claimed_order_id: str) -> CustomerContext:
    """A2. related_order_ids excludes the claimed order and never leaks into affected_entities."""
    raise NotImplementedError("TODO(TV2)")
