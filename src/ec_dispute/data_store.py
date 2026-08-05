"""Read-only CSV access layer.

OWNER: Thanh vien 2 (Data & Entities)

Loads the 9 Olist CSVs once and exposes indexed lookups. reviews and geolocation are
deliberately NOT loaded: EC_POLICY_V2 never uses them and no evidence id can cite them,
so leaving them out removes a whole class of false positives.

Contract: every accessor returns rows in stable source order.
"""

from __future__ import annotations

from ec_dispute.paths import DATA_DIR


class DataStore:
    """Indexed, read-only view over the Olist CSVs."""

    def __init__(self, data_dir=DATA_DIR) -> None:
        self.data_dir = data_dir
        raise NotImplementedError("TODO(TV2): load orders/items/payments/customers/products/sellers/categories")

    def order(self, order_id: str) -> dict | None:
        raise NotImplementedError

    def items_for(self, order_id: str) -> list[dict]:
        """Sorted by order_item_id."""
        raise NotImplementedError

    def payments_for(self, order_id: str) -> list[dict]:
        """Sorted by payment_sequential."""
        raise NotImplementedError

    def customer(self, customer_id: str) -> dict | None:
        raise NotImplementedError

    def orders_for_unique_customer(self, customer_unique_id: str) -> list[str]:
        raise NotImplementedError

    def product(self, product_id: str) -> dict | None:
        raise NotImplementedError

    def key_exists(self, reference: str) -> bool:
        """A7 uses this to prove an evidence id maps to a real row (existence only, no values)."""
        raise NotImplementedError
