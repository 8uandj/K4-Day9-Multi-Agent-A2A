"""A2 - identity resolution and order history.

OWNER: Thanh vien 2 (Data & Entities)

Sees only order_id/customer_id columns, so it cannot opine on delivery.
"""

from __future__ import annotations

from ec_dispute.agents.base import Agent


class _TodoAgent(Agent):
    """TODO: implement per docs/architecture.md section 3."""
