# Team Workboard - EC_POLICY_V2

File này là bảng chia việc chung. Khi ai xong hoặc bị kẹt, update trực tiếp vào đây để cả nhóm nhìn cùng một trạng thái.

## Quy tắc update

- Mỗi người chỉ sửa phần mình phụ trách, trừ khi đã thống nhất trong nhóm.
- Khi đổi schema trong `schemas.py`, báo cả nhóm trước vì đây là hợp đồng chung.
- Status dùng một trong bốn nhãn: `TODO`, `DOING`, `BLOCKED`, `DONE`.
- Mỗi lần update, thêm 1 dòng ngắn vào mục "Nhật ký tích hợp".
- Code tính toán tiền, giờ, policy nên deterministic bằng Python; LLM chỉ điều phối hoặc giải thích.

## Phân công chính

| Người | Vai trò | Phạm vi sở hữu | File/module dự kiến | Status |
| --- | --- | --- | --- | --- |
| Thành viên 1 | Lead orchestration + policy + verifier | Điều phối pipeline, schema, policy engine, output writer, validation cuối | `src/ec_dispute/schemas.py`, `src/ec_dispute/orchestrator.py`, `src/ec_dispute/policy_engine.py`, `src/ec_dispute/verifier.py`, `src/ec_dispute/output_writer.py`, `logging/` | DOING |
| Thành viên 2 | Data lookup + Order/Customer agents | Load CSV, join dữ liệu order/product/customer, tạo fact base và lịch sử khách | `src/ec_dispute/data_store.py`, `src/ec_dispute/tools/lookups.py`, `src/ec_dispute/agents/order_product.py`, `src/ec_dispute/agents/customer.py`, `tests/test_lookups.py` | TODO |
| Thành viên 3 | Payment/Delivery analytics | Tính tổng tiền, reconciliation, delivery variance, seller handoff variance | `src/ec_dispute/tools/calculations.py`, `src/ec_dispute/agents/payment.py`, `src/ec_dispute/agents/delivery.py`, `src/ec_dispute/recompute.py`, `tests/test_calculations.py` | TODO |

## Mốc tích hợp

| Mốc | Người phụ trách | Điều kiện hoàn thành | Status |
| --- | --- | --- | --- |
| M1 - Contract freeze | Thành viên 1 | `src/ec_dispute/schemas.py` import được, có schema input/output/artifact T1-T6 | DOING |
| M2 - Data lookup ready | Thành viên 2 | Lookup order, items, products, sellers, customer history chạy được với `EC_001` | TODO |
| M3 - Calculation ready | Thành viên 3 | Tính tiền và variance đúng 2 chữ số, xử lý null đúng | TODO |
| M4 - Policy ready | Thành viên 1 | 6 primary issues và secondary/action ordering khớp README | TODO |
| M5 - End-to-end 1 case | Cả nhóm | Chạy được `input/EC_001.json` ra JSON pass schema | TODO |
| M6 - End-to-end 50 cases | Cả nhóm | Sinh đủ 50 file output, verifier pass, trace có handoff | TODO |

## Checklist chi tiết

| Task | Owner | Output mong đợi | Status | Ghi chú |
| --- | --- | --- | --- | --- |
| Định nghĩa Pydantic contracts | Thành viên 1 | `src/ec_dispute/schemas.py` | DOING | Đã tạo khung schema chung |
| Viết loader CSV read-only | Thành viên 2 | `DataStore` hoặc helper tương đương | TODO | Giữ thứ tự source CSV ổn định |
| Build `OrderFacts` từ `claimed_order_id` | Thành viên 2 | `OrderFacts` artifact | TODO | Order không có item phải `has_items=false` |
| Build `CustomerContext` | Thành viên 2 | `CustomerContext` artifact | TODO | Không đưa related orders vào affected_entities |
| Build `PaymentReconciliation` | Thành viên 3 | `PaymentReconciliation` artifact | TODO | `abs(difference) <= 0.10` là reconciled |
| Build `DeliveryAnalysis` | Thành viên 3 | `DeliveryAnalysis` artifact | TODO | Thiếu timestamp thì variance null, không suy trễ |
| Viết policy engine | Thành viên 1 | `Verdict` artifact | TODO | Áp policy theo đúng thứ tự ưu tiên |
| Viết assembler output | Thành viên 1 | `CandidateOutput` | TODO | Evidence tối đa 20, đúng grammar |
| Viết verifier | Thành viên 1 | `ValidationResult` | TODO | Schema, limit, ID tồn tại, consistency |
| Chạy regression 50 case | Cả nhóm | `output/EC_001.json` đến `output/EC_050.json` | TODO | Ghi metadata model/runtime |

## Nhật ký tích hợp

| Thời điểm | Người update | Nội dung |
| --- | --- | --- |
| 2026-08-05 | Codex | Tạo `schemas.py` và workboard chia việc ban đầu. |
