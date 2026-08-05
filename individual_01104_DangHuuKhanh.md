# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                            |
| --------------- | --------------------------------------------------- |
| Họ và tên       | Đặng Hữu Khanh                                      |
| MSSV            | 2A202601104                                               |
| Khóa/Lớp        | K4 / D305                                           |
| Vai trò chính   | Data & Entities (tầng dữ liệu, thực thể, bằng chứng) |
| Ngày hoàn thành | 2026-08-05                                          |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Tách và freeze contract | `src/ec_dispute/contracts/output_schema.py`, `contracts/envelope.py` | `schemas.py` bản đầu của TV1 | Contract đóng băng + `POLICY_RULES` + builder evidence ID | Hoàn thành |
| Tầng đọc CSV | `src/ec_dispute/data_store.py` — `DataStore`, `key_exists`, `get_store` | 7/9 file CSV | Lookup có index, key index cho A7 | Hoàn thành |
| Tool tra cứu | `src/ec_dispute/tools/lookups.py` — `build_order_facts`, `build_customer_context`, 2 hàm provenance | `claimed_order_id`, `customer_id` | `OrderFacts`, `CustomerContext`, provenance | Hoàn thành |
| Agent A1, A2, A6 | `agents/order_product.py`, `agents/customer.py`, `agents/evidence.py` | Case input, artifact upstream | Envelope T2, T3, T5 | Hoàn thành |
| Bộ test tầng dữ liệu | `tests/test_lookups.py`, `tests/test_contracts_envelope.py`, `tests/test_contracts_output_schema.py` | — | 72 test | Hoàn thành |
| Tài liệu kiến trúc | `architecture.md`, `docs/team_workboard.md` | — | Sơ đồ agent, ma trận quyền, luồng handoff, bảng chia việc | Hoàn thành |
| Harness A/B | `variant.py` | Flag cách hiểu | Sinh lại `output/` + zip cho từng biến thể | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Dựng khung thư mục và stub cho toàn repo | Cả nhóm | 22 file có sẵn docstring, chữ ký hàm và tên chủ sở hữu, ai cũng biết viết vào đâu |
| Resolve conflict rebase ở `agents/base.py` | TV1 | Giữ typing của TV1, thêm `__init__(store, llm)` và `check_tools()`; `allowed_tools` rỗng nghĩa là chưa khai báo nên `CoordinatorAgent` không gãy |
| Adapter `assemble_candidate_output` | TV1 | Khớp đúng chữ ký `orchestrator.run_case` đang gọi, orchestrator không phải sửa |
| Truy vết 2 lỗi làm mất điểm sau khi có kết quả chấm | Cả nhóm | Bỏ action `verify_refund_completion` thừa ở 20 case, chuẩn hoá `-0.0` ở 6 case |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | -------------------------- | ---------------- | ------------- |
| Đóng băng contract và chứng minh không chặn nhầm | `contracts/` | 43 test contract (cả âm lẫn dương) | Dựng output tất định cho 50 case rồi đẩy qua contract: 50/50 pass, 0 rejection |
| Dựng fact base cho mọi case | `build_order_facts` | `OrderFacts` cho 50/50 case | `pytest tests/test_lookups.py` |
| Sinh evidence ID không bịa | `agents/evidence.py`, `unsupported_evidence` | Evidence cho 50 case | `store.missing_references(evidence_ids)` trả rỗng ở cả 50 case |
| Bác bỏ giả thuyết tên category tiếng Anh | `data_store.CATEGORY_NAMES_TRANSLATED` | Chốt dùng tên gốc tiếng Bồ | Nộp thử biến thể tiếng Anh lên trình chấm: 0 điểm |

Nêu một output cụ thể mà phần việc của tôi tạo ra hoặc giúp xác minh:

Chạy A1 → A2 → A6 trên toàn bộ 50 case và đối chiếu mọi `evidence_ids` ngược lại key index của `DataStore`: **0 ID không truy được về một dòng CSV có thật**. Đây là chỉ số tôi quan tâm nhất vì theo README §5, evidence không tồn tại trong CSV bị tính là false positive.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi là nền dữ liệu: đọc CSV, dựng thực thể của case, và bảo đảm mọi ID xuất hiện trong file nộp đều truy được về một dòng dữ liệu có thật. Nếu tầng này sai thì mọi phân tích phía sau đều sai theo mà không ai phát hiện.

### Cách triển khai

**Cắt quyền đọc như một cơ chế, không phải một lời dặn.** `DataStore` chỉ nạp 7/9 file CSV. `reviews` và `geolocation` bị bỏ hẳn vì `EC_POLICY_V2` không dùng tới, và grammar evidence ID cũng không có dạng nào biểu diễn được chúng. Không nạp thì agent không thể kéo dữ liệu không liên quan vào lập luận. Bỏ luôn file `geolocation` 1 triệu dòng cũng giúp thời gian nạp còn 0.65 giây.

**Facts giữ nguyên vẹn, cắt ở khâu lắp ráp.** `OrderFacts` không áp trần mảng, dù output chỉ cho tối đa 5 item. Lý do: A3 cộng `price_brl` trên toàn bộ item để đối soát thanh toán, cắt ở đây sẽ làm sai tổng tiền một cách âm thầm. Việc cắt theo `LIMITS` dồn hết về A6 — nơi các mảng được chấm điểm thực sự sinh ra.

**Provenance dùng chung grammar với evidence.** Mỗi agent khai báo những dòng nó thực sự đọc, theo đúng 5 dạng của evidence ID cộng thêm `customer:` và `product:` chỉ dành cho provenance. Nhờ vậy phép kiểm của A7 rút gọn còn một phép bao hàm tập hợp: ID nào không nằm trong provenance thì bị chặn.

**Ràng buộc chéo giữa A1 và A3.** A3 không được cấp quyền đọc `order_items`, buộc phải lấy tổng tiền hàng từ artifact của A1. Nếu A1 sai, sai lệch lộ ra ngay ở khâu đối soát thay vì hai agent che lấp cho nhau.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `claimed_order_id` từ `input/EC_*.json`; `customer_id` nhận qua handoff từ A1 |
| Output | `OrderFacts`, `CustomerContext`, `CandidateOutput` + `evidence_ids`, kèm provenance |
| Module phụ thuộc | `contracts/` (schema, `LIMITS`, builder ID), `data/*.csv` |
| Module sử dụng output | A3/A4 (TV3) dùng `OrderFacts`; A5 (TV1) dùng cả 4 artifact; A7 dùng provenance |
| Điều kiện lỗi cần xử lý | Order không tồn tại → raise `KeyError`; 6 case không có item row → `has_items=false` và mảng rỗng; 610/32951 product có category trống → trả `None` chứ không phải chuỗi rỗng; thiếu provenance `payment:` → raise kèm tên A3 |

### Cách xác minh

```bash
.venv/bin/python -m pytest -q
```

- **Kết quả mong đợi:** toàn bộ test xanh, trong đó có các test âm chặn ID sai định dạng, evidence bịa, và order lịch sử lọt vào `affected_entities`.
- **Kết quả thực tế:** 76 passed (72 test do tôi viết, 3 của TV1, 1 có sẵn).
- **Artifact/log:** `output/EC_001.json` … `output/EC_050.json`; `submission_baseline.zip` là bản đạt 67.4696 trên trình chấm.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `affected_entities.payment_ids` cần `payment_sequential` của từng dòng thanh toán, nhưng `PaymentReconciliation` là một mục được chấm điểm nên chỉ chứa các con số tổng, không mang sequential. A6 lại không có quyền đọc CSV.
- **Các phương án đã cân nhắc:** (1) Thêm trường `payment_sequentials` vào `PaymentReconciliation` — nhưng đó là mục được chấm, thêm trường lạ là phá schema output; (2) Cấp cho A6 quyền đọc bảng payment — phá nguyên tắc least privilege và mở lại đường bịa ID; (3) Suy ra từ provenance mà A3 đã khai.
- **Phương án đã chọn:** phương án 3.
- **Lý do:** provenance vốn được thiết kế để ghi lại "agent này đã đọc những dòng nào", nên đây là dùng đúng công dụng chứ không phải lách. Giữ được cả schema output lẫn ranh giới quyền, không phải nới cái nào.
- **Bằng chứng quyết định phù hợp:** `payment_ids` dựng đúng ở cả 50 case; và khi thiếu provenance thì A6 raise kèm tên A3 thay vì trả mảng rỗng — mảng rỗng sẽ mất trọn 15% "affected entities" của case đó mà không ai biết.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `AssertionError: assert 'qwen/qwen3-8b' == 'qwen3:8b'` tại `tests/test_lookups.py::test_a1_emits_a_valid_t2_envelope`, xuất hiện ngay sau khi rebase lên nhánh của TV1.
- **Lệnh hoặc bước tái hiện:** `git rebase origin/main && .venv/bin/python -m pytest -q`.
- **Nguyên nhân gốc:** test của tôi khẳng định cứng tên tag model. Khi TV1 chuyển hạ tầng từ Ollama sang OpenRouter, cùng một model đổi tên từ `qwen3:8b` thành `qwen/qwen3-8b`. Lỗi nằm ở chỗ tôi kiểm thứ không phải ràng buộc thật của đề bài — đề ràng buộc **kích thước** model, không ràng buộc tên tag.
- **Cách xử lý:** đọc tên từ `MODEL_BY_AGENT` thay vì viết cứng, và thêm khẳng định `spec.parameters_b <= PARAMETER_CEILING_B`.
- **Cách xác minh sau khi sửa:** `pytest -q` → 76 passed; đổi provider không còn làm đỏ test.
- **Điều học được:** một test khẳng định giá trị cấu hình thay vì bất biến nghiệp vụ sẽ hỏng mỗi lần đổi hạ tầng, và tệ hơn là nó không hề bảo vệ điều mình tưởng nó đang bảo vệ.

## 7. Hiểu biết về luồng end-to-end

> Ghi chú: mục này trong mẫu hỏi về Crossref, vector index và freshness monitoring — nội dung của một bài lab RAG khác. Tôi trả lời theo pipeline thực tế của bài Day 9 này.

**Câu trả lời:**

1. **Dữ liệu đi từ nguồn tới kết quả:** `DataStore` nạp 7 CSV và dựng index (order, item theo `order_item_id`, payment theo `payment_sequential`, customer, product, seller, và map `customer_unique_id → các order`). A1 dựng `OrderFacts` đầy đủ. A2 phân giải danh tính và lịch sử mua. A3, A4 tính tiền và giờ. A5 phán quyết. A6 lắp ráp và cắt theo `LIMITS`. A7 kiểm chứng rồi ghi `output/`.

2. **Tập đánh giá và ID tham chiếu:** 50 case cố định trong `input/`. Vai trò "ground truth ID" do `evidence_ids` đảm nhiệm — mỗi ID phải dựng được trực tiếp từ CSV, và được đối chiếu hai lớp: nằm trong provenance của agent nào đó, và tồn tại thật trong key index.

3. **Kiểm tra chất lượng khác giám sát ở điểm nào:** contract chặn ở mức từng bản ghi ngay lúc khởi tạo và không cho đi tiếp. Verifier chặn ở mức cả case và giữ quyền ghi file. Trace thì không chặn gì — nó chỉ ghi lại để truy vết. Nhầm lẫn ba tầng này sẽ dẫn tới việc tưởng đã có bảo vệ trong khi thực ra chỉ đang ghi log.

4. **Vì sao dùng cùng một tập test cho mọi biến thể:** tôi viết `variant.py` để bật/tắt từng cách hiểu và đo xem mỗi flag đổi bao nhiêu case. Nếu tập case thay đổi giữa các lần thì chênh lệch điểm không quy được về biến nào. Giữ nguyên 50 case là điều kiện để so sánh có nghĩa.

5. **Căn cứ để coi là thành công:** verifier pass cả 50 case, chạy lại ra file giống hệt từng byte, và điểm trên trình chấm. Hiện đạt 67.4696 với phân rã 7 nhóm gần bằng nhau (65.95–68.44) — một dấu hiệu cho thấy khoảng một phần ba số case đang bị mất điểm toàn diện chứ không phải một trường cụ thể sai, và nhóm chưa xác định được nguyên nhân trước khi hết giờ.

**Họ và tên:** Đặng Hữu Khanh
**Ngày xác nhận:** 2026-08-05
