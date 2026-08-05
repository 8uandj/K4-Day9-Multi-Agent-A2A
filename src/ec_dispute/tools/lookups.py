"""Deterministic lookup tools for A1, A2 and A6.

OWNER: Thanh vien 2 (Data & Entities)

Builds ``OrderFacts`` and ``CustomerContext`` and the provenance that backs them. No LLM in
here: the agent decides which tool to call and how to read the result, the tool does the
retrieval. Every number the grader reads for entities and context originates in this file.

Ordering rules (README section 6: "các array phải giữ thứ tự ổn định theo dữ liệu nguồn"):
items follow ``order_item_id``; sellers, products and categories follow first appearance
among those items; related orders follow source CSV order.
"""

from __future__ import annotations

from ec_dispute.contracts import (
    CustomerContext,
    OrderFacts,
    OrderItemFact,
    SellerFact,
    item_evidence_id,
    order_evidence_id,
    seller_evidence_id,
)
from ec_dispute.data_store import DataStore, _clean


def build_order_facts(store: DataStore, order_id: str, *, include_product_context: bool = True) -> OrderFacts:
    """A1's fact base — the root every downstream number hangs off.

    Lists are returned COMPLETE, never truncated. Output arrays cap at 5/5/3 but A3 sums
    ``price_brl`` across every item to reconcile payments, so cutting here would silently
    corrupt the totals. Truncation belongs to A6 at assembly time.

    Raises ``KeyError`` when the claimed order does not exist — a case that cannot be
    investigated must fail loudly at the first step, not produce a confident empty answer.
    """
    order = store.order(order_id)
    if order is None:
        raise KeyError(f"claimed_order_id {order_id!r} does not exist in olist_orders_dataset.csv")

    rows = store.items_for(order_id)

    items: list[OrderItemFact] = []
    seller_ids: list[str] = []
    product_ids: list[str] = []
    category_names: list[str] = []
    #: seller_id -> earliest shipping_limit_date, the deadline that actually binds them
    earliest_limit: dict[str, str] = {}

    for row in rows:
        category = store.category_of(row["product_id"])
        items.append(
            OrderItemFact(
                order_id=order_id,
                order_item_id=int(row["order_item_id"]),
                product_id=row["product_id"],
                seller_id=row["seller_id"],
                shipping_limit_at=_clean(row["shipping_limit_date"]),
                price_brl=float(row["price"]),
                freight_value_brl=float(row["freight_value"]),
                category_name=category,
            )
        )

        if row["seller_id"] not in seller_ids:
            seller_ids.append(row["seller_id"])
        if row["product_id"] not in product_ids:
            product_ids.append(row["product_id"])
        # 610/32951 products carry a blank category — skip rather than emit an empty string.
        if category is not None and category not in category_names:
            category_names.append(category)

        limit = _clean(row["shipping_limit_date"])
        if limit is not None:
            current = earliest_limit.get(row["seller_id"])
            # Timestamps are zero-padded ISO-like strings, so lexical min == chronological min.
            if current is None or limit < current:
                earliest_limit[row["seller_id"]] = limit

    if not include_product_context:
        # Scope says the caller does not want product detail; identity of the sellers still
        # matters for the policy, so only product/category are dropped.
        product_ids = []
        category_names = []

    return OrderFacts(
        order_id=order_id,
        customer_id=_clean(order["customer_id"]),
        order_status=_clean(order["order_status"]),
        order_purchase_at=_clean(order["order_purchase_timestamp"]),
        order_approved_at=_clean(order["order_approved_at"]),
        order_delivered_carrier_at=_clean(order["order_delivered_carrier_date"]),
        order_delivered_customer_at=_clean(order["order_delivered_customer_date"]),
        order_estimated_delivery_at=_clean(order["order_estimated_delivery_date"]),
        has_items=bool(items),
        items=items,
        seller_ids=seller_ids,
        product_ids=product_ids,
        category_names=category_names,
        seller_shipping_limits=[
            SellerFact(seller_id=seller_id, shipping_limit_at=earliest_limit.get(seller_id))
            for seller_id in seller_ids
        ],
    )


def build_customer_context(
    store: DataStore,
    customer_id: str,
    claimed_order_id: str,
    *,
    include_history: bool = True,
    limit: int = 5,
) -> CustomerContext:
    """A2. Resolves identity, then finds the same human's other orders.

    README section 3 is explicit and easy to get wrong: history orders live here and here
    only. They must never reach ``affected_entities`` — the contract enforces that, but the
    cheapest place to get it right is at the source.
    """
    unique_id = store.customer_unique_id(customer_id)
    if unique_id is None:
        return CustomerContext(customer_unique_id=None, related_order_ids=[])

    if not include_history:
        return CustomerContext(customer_unique_id=unique_id, related_order_ids=[])

    related = [oid for oid in store.orders_for_unique_customer(unique_id) if oid != claimed_order_id]
    return CustomerContext(customer_unique_id=unique_id, related_order_ids=related[:limit])


# ---------------------------------------------------------------------------- provenance


def order_facts_provenance(facts: OrderFacts) -> list[str]:
    """Every row A1 actually read, in the shared reference grammar.

    A7 checks ``evidence_ids`` against the union of provenance. An id that never appears
    here cannot be cited downstream, which is what makes fabrication structurally
    impossible rather than merely discouraged.
    """
    refs = [order_evidence_id(facts.order_id)]
    refs += [item_evidence_id(facts.order_id, item.order_item_id) for item in facts.items]
    refs += [seller_evidence_id(seller_id) for seller_id in facts.seller_ids]
    refs += [f"product:{product_id}" for product_id in facts.product_ids]
    if facts.customer_id:
        refs.append(f"customer:{facts.customer_id}")
    return refs


def customer_context_provenance(customer_id: str, context: CustomerContext) -> list[str]:
    refs = [f"customer:{customer_id}"]
    refs += [order_evidence_id(order_id) for order_id in context.related_order_ids]
    return refs
