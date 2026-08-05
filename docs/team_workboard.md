# Team Workboard — EC_POLICY_V2

Bảng chia việc chung. Ai xong hoặc bị kẹt thì update trực tiếp vào đây để cả nhóm nhìn cùng một trạng thái.

## Quy tắc update

- Mỗi người chỉ sửa phần mình phụ trách, trừ khi đã thống nhất trong nhóm.
- **`src/ec_dispute/contracts/` đã FREEZE.** Không ai sửa một mình. Đổi contract = báo cả nhóm + thêm dòng vào "Nhật ký tích hợp".
- Status dùng một trong bốn nhãn: `TODO`, `DOING`, `BLOCKED`, `DONE`.
- Code tính tiền, giờ, policy phải deterministic bằng Python. LLM điều phối, diễn giải, phán quyết — không làm số học.
- Chạy `pytest` trước mỗi lần push. 44 test hiện đang xanh; đừng để đỏ khi merge.

## Setup

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]" && .venv/bin/python -m pytest -q
```

---

## Phân công chính

| Người | Vai trò | Sở hữu | File/module | Trọng số điểm | Status |
| --- | --- | --- | --- | ---: | --- |
| Thành viên 1 | Decision & Control | Orchestrator, policy engine, verifier, LLM client, trace, output writer | `orchestrator.py`, `policy_engine.py`, `verifier.py`, `llm_client.py`, `agents/base.py`, `agents/coordinator.py`, `run.py` | 40% | **DONE** |
| Thành viên 2 | Data & Entities | Load CSV, fact base order/product, lịch sử khách, evidence + assembly | `data_store.py`, `tools/lookups.py`, `agents/order_product.py`, `agents/customer.py`, `agents/evidence.py` | 30% | TODO |
| Thành viên 3 | Analysis | Reconciliation tiền, delivery/handoff variance, regression harness | `tools/calculations.py`, `agents/payment.py`, `agents/delivery.py`, `qa/golden_check.py` | 30% | TODO |

Trọng số điểm là phần chấm mà người đó chịu trách nhiệm trực tiếp — xem `README.md` mục 8.

## Golden set riêng

Test nhánh của mình trước, đừng chờ full run.

| Người | Case | Vì sao |
| --- | --- | --- |
| TV1 | `EC_001` `EC_002` `EC_003` `EC_004` `EC_008` `EC_012` | 6 nhánh policy, mỗi nhánh 1 case |
| TV2 | `EC_012` `EC_009` `EC_049` `EC_001` | không item row / 5 item (chạm trần) / 3 seller (chạm trần) |
| TV3 | `EC_002` `EC_003` `EC_008` `EC_004` | seller trễ / logistics trễ / split payment / null delivered |

Phân bố đầy đủ 50 case:

| Nhánh | Số case | Case ID |
| --- | ---: | --- |
| `late_delivery_seller` | 10 | 002 006 013 019 020 032 039 042 046 048 |
| `late_delivery_logistics` | 10 | 003 005 007 014 016 017 023 027 037 040 |
| `canceled_order_paid` | 8 | 004 009 011 024 026 028 030 047 |
| `unsupported_late_claim` | 8 | 001 018 021 025 038 044 045 050 |
| `valid_split_payment` | 8 | 008 010 015 022 029 036 041 049 |
| `unavailable_order_paid` | 6 | 012 031 033 034 035 043 |

Edge case đã đo trên dữ liệu thật:

| Điều kiện | Số case | Ai xử lý |
| --- | ---: | --- |
| Null `order_delivered_customer_date` | 14 | TV3 — variance `null`, **không** suy ra là trễ |
| Null `order_delivered_carrier_date` | 13 | TV3 — handoff variance `null`, `late_handoff=false` |
| Không có item row | 6 | TV2 `has_items=false` → TV3 trả `null` (không phải `0.0`) |
| Nhiều payment type | 12 | TV3 — thứ tự theo `payment_sequential` |
| Trùng payment type trong 1 order | 4 | TV3 — xem "Quyết định treo" bên dưới |
| Chạm trần mảng (5 item / 3 seller) | 2 | TV2 — `EC_009`, `EC_049`, biên an toàn = 0 |

---

## Mốc tích hợp

| Mốc | Người | Điều kiện hoàn thành | Status |
| --- | --- | --- | --- |
| M1 — Contract freeze | TV1 | `contracts/` import được, 44 test xanh, 50/50 case thật validate | **DONE** |
| M2 — Data lookup ready | TV2 | `build_order_facts` + `build_customer_context` chạy đúng với `EC_001` và `EC_012` | TODO |
| M3 — Calculation ready | TV3 | Tiền và variance đúng 2 chữ số, null đúng trên 4 case golden | TODO |
| M4 — Policy ready | TV1 | 6 primary issue + thứ tự secondary/action khớp `POLICY_RULES` | **DONE** |
| M5 — End-to-end 1 case | Cả nhóm | `EC_001` chạy hết pipeline, `CandidateOutput` validate | TODO |
| M6 — End-to-end 50 case | Cả nhóm | Đủ 50 file output, verifier pass, trace có handoff thật | TODO |
| M7 — Reproducibility | TV3 | Chạy lại 50 case ra file byte-identical | TODO |

**M5 là mốc quyết định.** Quá mốc này mà chưa chạy thông thì cắt agent yếu nhất sang deterministic, đừng cố cứu.

## Checklist chi tiết

| Task | Owner | Output | Status | Ghi chú |
| --- | --- | --- | --- | --- |
| Định nghĩa Pydantic contracts | TV1 | `contracts/envelope.py`, `contracts/output_schema.py` | **DONE** | Đã freeze, có test âm/dương |
| Scaffold module + stub | TV1 | `src/ec_dispute/**` | **DONE** | 15 stub import sạch |
| `DataStore` read-only | TV2 | `data_store.py` | TODO | Không load `reviews`/`geolocation` — policy không dùng |
| `OrderFacts` từ `claimed_order_id` | TV2 | `tools/lookups.py` | TODO | Facts **không cắt** theo trần; cắt ở A6 |
| `CustomerContext` | TV2 | `tools/lookups.py` | TODO | Related order không được lọt vào `affected_entities` |
| Evidence + assembly | TV2 | `agents/evidence.py` | TODO | Dùng `item_evidence_id()` etc., đừng nối chuỗi tay |
| `PaymentReconciliation` | TV3 | `tools/calculations.py` | TODO | `abs(difference) <= 0.10` là reconciled (biên tính là đạt) |
| `DeliveryAnalysis` | TV3 | `tools/calculations.py` | TODO | So với `shipping_limit` **sớm nhất** của từng seller |
| Policy engine | TV1 | `policy_engine.py` | **DONE** | Đọc `POLICY_RULES`, áp precedence và confidence rubric |
| LLM client + agent runtime | TV1 | `llm_client.py`, `agents/base.py` | **DONE** | OpenAI-compatible JSON client, `temperature=0`, `seed=42` |
| Verifier gate | TV1 | `verifier.py` | **DONE** | Schema/provenance/key-index/product checks, gắn `blamed_agent` |
| Regression + submission gate | TV3 | `qa/golden_check.py` | TODO | `missing_case_ids()` phải rỗng trước khi zip |
| Prompt cho từng agent | Mỗi owner | `prompts/<agent>.md` | TODO | TV1 đã có `A0_coordinator.md`, `A5_policy.md`, `A7_verifier.md`; còn TV2/TV3 |
| Báo cáo cá nhân | Mỗi người | `docs/individual/*.md` | TODO | Viết dần, đừng để 15 phút cuối |

---

## Việc phải làm ngay (P0)

1. **`ollama pull` 3 model (~12.7GB) chạy nền NGAY.** Chưa cài ollama trên máy dev. Kéo model mất 15–25 phút — đừng để nó chặn ở phút thứ 90.
   ```bash
   ollama pull qwen3:8b && ollama pull qwen3:4b-instruct && ollama pull llama3.1:8b
   ```
2. **`architecture.md` và báo cáo cá nhân đang sai vị trí.** README mục 8 ghi rõ hai file này phải **đặt ở root repo**, hiện đang nằm trong `docs/`. Sửa trước khi nộp:
   ```bash
   git mv docs/architecture.md architecture.md && git mv docs/individual/*.md .
   ```
3. **`.gitignore` đang ignore `output/*.json`.** Cân nhắc bỏ dòng đó trước khi nộp — README mục 9 yêu cầu commit toàn bộ source, và có output trong repo giúp đối chiếu khi tranh chấp điểm.

## Quyết định treo (cần chốt khi có tín hiệu từ leaderboard)

| Vấn đề | Đã chọn | Lý do | Ảnh hưởng nếu sai | Cách đổi |
| --- | --- | --- | --- | --- |
| `payment_types` có dedupe không? | **Có dedupe**, giữ thứ tự `payment_sequential` | Tên field là "types"; ví dụ trong README không phân định được | 4/50 case (`EC_010` `EC_015` `EC_016` `EC_042`), ~1.2% tổng điểm | Đổi `PAYMENT_TYPES_DEDUPED = False` trong `output_schema.py` |
| `item_total_brl`/`freight_total_brl` khi order không có item | **`null`** | README chỉ nói `expected`/`difference`/`reconciled` là null, nhưng để `0.0` sẽ mâu thuẫn với `expected = item + freight` | 6/50 case | Sửa validator `all_null_or_all_present` |
| Làm tròn | **`round()` của Python** (banker's + nhị phân) | Grader gần như chắc chắn cũng viết bằng Python | Sai lệch 0.01 rải rác | Đổi sang `Decimal` half-up trong `_round2` |

---

## Contract đã freeze — tóm tắt cho người dùng

Import từ một chỗ duy nhất:

```python
from ec_dispute.contracts import CandidateOutput, A2AEnvelope, POLICY_RULES, LIMITS
```

| Bạn cần | Dùng cái này |
| --- | --- |
| Bảng luật EC_POLICY_V2 | `POLICY_RULES[primary_issue]` → action, cause, party, refund basis, case_status |
| Thứ tự xét primary issue | `PRIMARY_ISSUE_PRECEDENCE` |
| Thứ tự secondary issue | `SECONDARY_ISSUE_ORDER` |
| Trần mảng | `LIMITS` |
| Dựng evidence ID | `order_evidence_id()`, `item_evidence_id()`, `payment_evidence_id()`, `seller_evidence_id()`, `policy_evidence_id()` |
| Dựng entity ID | `item_entity_id()`, `payment_entity_id()` |
| Bắt evidence bịa | `unsupported_evidence(evidence_ids, provenance)` |
| Ngưỡng đối soát | `RECONCILIATION_TOLERANCE_BRL` |

Contract tự động làm giúp bạn, khỏi tự xử lý:

- Làm tròn 2 chữ số mọi trường tiền và giờ.
- Chặn ID không phải hex 32 ký tự (đã verify: 100% ID trong 9 CSV đều đúng dạng này).
- Chặn `late_handoff=true` khi variance là `null`.
- Chặn action sai thứ tự, sai action chính, hoặc `verify_payment_allocation` khi primary là `valid_split_payment`.
- Chặn `related_order_ids` lọt vào `affected_entities`.
- Chặn `case_status` lệch với `recommended_refund_brl`.
- Chặn envelope sai producer hoặc sai stage.

Contract reject nghĩa là **output sai, không phải contract sai**. Đừng nới validator — sửa dữ liệu.

---

## Nhật ký tích hợp

| Thời điểm | Người update | Nội dung |
| --- | --- | --- |
| 2026-08-05 | Hoàng Hưng | Tạo `schemas.py` và workboard chia việc ban đầu. |
| 2026-08-05 | Khanh | Tách `schemas.py` → `contracts/envelope.py` + `contracts/output_schema.py` và freeze. `schemas.py` giữ lại làm shim re-export nên code cũ không gãy. Thêm `POLICY_RULES`, evidence builder, routing table, 44 test (âm + dương). Verify: 50/50 case thật đi qua contract, 0 rejection. |
| 2026-08-05 | Khanh | Scaffold 22 file: `config.py` (MODEL_REGISTRY ≤10B), `trace.py`, `output_writer.py` chạy được; 15 stub còn lại có signature + owner. Thêm `run.py`, `.env.example`, `prompts/_TEMPLATE.md`. |
| 2026-08-05 | Codex | Hoàn thành phần TV1: policy engine deterministic, verifier gate, agent envelope runtime, LLM client OpenAI-compatible, coordinator T1, run/orchestrator wiring, prompt A0/A5/A7. |
