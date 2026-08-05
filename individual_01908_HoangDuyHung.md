# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                       |
| --------------- | ---------------------------------------------- |
| Họ và tên       | Hoàng Duy Hưng                                 |
| MSSV            | 01908                                          |
| Khóa/Lớp        | K4                                             |
| Vai trò chính   | Thành viên 1 — Decision & Control (điều phối, policy, verifier) |
| Ngày hoàn thành | 2026-08-05                                     |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Bản Pydantic contract đầu tiên | `src/ec_dispute/schemas.py` (sau tách thành `contracts/`) | Schema output trong README §6 | Model cho input, artifact T1–T6, envelope A2A | Hoàn thành |
| Policy engine (A5) | `src/ec_dispute/policy_engine.py` — `decide`, `_primary_issue`, `_secondary_issues`, `_responsible_parties`, `_refund`, `_actions`, `_confidence` | `OrderFacts`, `CustomerContext`, `PaymentReconciliation`, `DeliveryAnalysis` | `Verdict` | Hoàn thành |
| Verifier gate (A7) | `src/ec_dispute/verifier.py` — `verify` | `CandidateOutput`, danh sách envelope upstream, `DataStore` | `ValidationResult` kèm `blamed_agent` | Hoàn thành |
| Orchestrator | `src/ec_dispute/orchestrator.py` — `run_case` | `CaseInput` | `CandidateOutput`, ghi trace | Hoàn thành |
| LLM client + coordinator | `src/ec_dispute/llm_client.py`, `src/ec_dispute/agents/coordinator.py`, `agents/base.py` | Prompt + `ModelSpec` | Envelope T1, client OpenAI-compatible | Hoàn thành |
| Cấu hình model + runtime | `src/ec_dispute/config.py` | — | `MODEL_REGISTRY`, `metadata_document()` | Hoàn thành |
| Prompt A0/A5/A7 | `prompts/A0_coordinator.md`, `A5_policy.md`, `A7_verifier.md` | — | Prompt từng agent | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Chuyển hạ tầng model từ Ollama local sang OpenRouter | Cả nhóm | `config.py` + `.env.example` dùng model ID của OpenRouter, thêm `scripts/test_llm_api.py` để thử key trước khi chạy thật |
| Định nghĩa `A2AEnvelope` với type `AgentName`/`Stage`/`PayloadType` | TV2 (agent A1/A2/A6 dùng lại) | Envelope sai producer hoặc sai stage bị chặn ngay lúc tạo |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | -------------------------- | ---------------- | ------------- |
| Áp `EC_POLICY_V2` theo thứ tự ưu tiên 6 nhánh | `policy_engine.decide` | Verdict cho cả 50 case | `python run.py` rồi đếm phân bố primary issue |
| Cổng kiểm chứng trước khi ghi file | `verifier.verify` + `output_writer.write_output` | Không case nào ghi ra `output/` khi chưa pass | `pytest tests/test_decision_control.py` |
| Wiring toàn pipeline | `orchestrator.run_case`, `run.py` | 50 file JSON + `logging/trace.jsonl` | `ls output/*.json \| wc -l` → 50 |
| Khai báo model đúng ràng buộc đề bài | `config.MODEL_REGISTRY`, `assert_parameter_ceiling` | 8 agent, model lớn nhất 8.2B | Gọi `assert_parameter_ceiling()` — không raise |

Nêu một output cụ thể mà phần việc của tôi tạo ra hoặc giúp xác minh:

`policy_engine.decide` sinh verdict cho 50 case với phân bố: 10 `late_delivery_seller`, 10 `late_delivery_logistics`, 8 `canceled_order_paid`, 8 `unsupported_late_claim`, 8 `valid_split_payment`, 6 `unavailable_order_paid`. Cả 6 nhánh của bảng luật đều được kích hoạt, không case nào rơi ra ngoài bảng — nghĩa là hàm phân nhánh phủ hết miền dữ liệu thật chứ không có nhánh chết.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi trả lời câu hỏi cuối cùng của mỗi case: dựa trên các bằng chứng đã thu thập, lỗi thuộc về ai, hoàn bao nhiêu tiền, và làm gì tiếp theo. Đồng thời phải bảo đảm không có kết quả sai định dạng nào lọt được ra file nộp.

### Cách triển khai

Bảng luật `EC_POLICY_V2` được mã hoá thành dữ liệu (`POLICY_RULES` trong contract) thay vì viết thành chuỗi `if/else` rải rác. Mỗi dòng gồm: action chính, cause code hạng 1, loại bên chịu trách nhiệm, ID cố định nếu có, cơ sở tính hoàn tiền, và `case_status`. `decide` chỉ làm hai việc: chọn `primary_issue` theo đúng thứ tự ưu tiên, rồi tra bảng để dựng phần còn lại. Cách này khiến việc sửa luật là sửa dữ liệu, không phải sửa luồng điều khiển.

Thứ tự ưu tiên phải giữ đúng như đề: `canceled` và `unavailable` xét trước, vì một đơn đã huỷ mà vẫn giao trễ thì vấn đề chính vẫn là đã thu tiền của đơn huỷ.

Verifier chạy sau cùng và có quyền ghi `output/` duy nhất. Nó validate lại `CandidateOutput` từ dạng JSON (chứ không tin object đang có trong bộ nhớ), đối chiếu từng `evidence_ids` với provenance của các envelope phía trên, rồi kiểm tra từng ID có thật trong key index của `DataStore`. Các kiểm tra về trần mảng, quy tắc null và định dạng timestamp đã được contract chặn ngay từ lúc khởi tạo model nên verifier không lặp lại.

`_confidence` dùng rubric cố định thay vì để model tự đoán: trừ 0.10 khi thiếu timestamp giao hàng hoặc bàn giao, trừ 0.10 khi đơn không có item row, trừ 0.05 khi `difference_brl` sát ngưỡng 0.10, kẹp trong `[0.30, 0.98]`.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `OrderFacts`, `CustomerContext`, `PaymentReconciliation`, `DeliveryAnalysis` và `payment_row_count` |
| Output | `Verdict` (case assessment, root cause, financial resolution, resolution actions); `ValidationResult` từ verifier |
| Module phụ thuộc | `contracts.POLICY_RULES`, `tools/lookups.py` (TV2), `tools/calculations.py` (TV3) |
| Module sử dụng output | `agents/evidence.py` (A6) nhận `Verdict`; `output_writer.write_output` nhận `ValidationResult` |
| Điều kiện lỗi cần xử lý | Thiếu artifact ở barrier T3; `freight_total_brl` là `None` với đơn không có item; evidence không có trong provenance; `key_exists` trả false |

### Cách xác minh

```bash
.venv/bin/python -m pytest -q
.venv/bin/python run.py
```

- **Kết quả mong đợi:** toàn bộ test xanh; sinh đủ 50 file trong `output/`; không case nào bị verifier chặn.
- **Kết quả thực tế:** 76 passed; `ls output/*.json | wc -l` trả về 50; `write_output` không raise `PermissionError` lần nào.
- **Artifact/log:** `output/EC_001.json` … `output/EC_050.json`, `logging/trace.jsonl`, `logging/metadata.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Đề yêu cầu mỗi agent dùng model ≤10B. Ban đầu nhóm định chạy Ollama cục bộ trên máy MacBook M4 Pro.
- **Các phương án đã cân nhắc:** (1) Ollama cục bộ, tải sẵn 3 model khoảng 12.7GB; (2) Provider OpenAI-compatible qua OpenRouter, một key định tuyến được cả Qwen lẫn Llama.
- **Phương án đã chọn:** OpenRouter, giữ nguyên `LLMClient` vì cả hai đều nói giao thức OpenAI-compatible nên chỉ đổi `base_url`.
- **Lý do:** thời gian thi có 4 tiếng, riêng việc tải model đã mất 15–25 phút và chiếm băng thông chung. Đổi provider chỉ tốn một dòng cấu hình, còn tải model hỏng giữa chừng thì không cứu được.
- **Bằng chứng quyết định phù hợp:** `MODEL_REGISTRY` sau khi đổi vẫn thoả ràng buộc — model lớn nhất 8.2B, `assert_parameter_ceiling()` không raise; `metadata.json` sinh tự động từ chính registry đó nên hai nơi không thể khai khác nhau.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `orchestrator.run_case` gọi `assemble_candidate_output(case_id, facts, customer, payment, delivery, verdict)` nhưng module `agents/evidence.py` của TV2 chỉ có method `EvidenceAgent.assemble(...)` với tên khác và thứ tự tham số khác (`delivery` trước `payment`).
- **Lệnh hoặc bước tái hiện:** `python run.py EC_001` ở thời điểm vừa merge hai nhánh.
- **Nguyên nhân gốc:** tôi viết orchestrator dựa trên tên hàm tự đặt trước khi A6 tồn tại, trong khi TV2 hiện thực A6 theo dạng class. Contract chung chỉ chốt schema dữ liệu, chưa chốt chữ ký hàm giữa các module.
- **Cách xử lý:** TV2 bổ sung hàm `assemble_candidate_output` đóng vai adapter, giữ đúng thứ tự tham số mà orchestrator đang gọi và uỷ quyền vào class bên trong. Orchestrator không phải sửa.
- **Cách xác minh sau khi sửa:** `python run.py` chạy hết 50 case, không `ImportError` hay `TypeError`.
- **Điều học được:** freeze schema dữ liệu là chưa đủ. Khi hai người viết hai đầu của một lời gọi hàm, chữ ký hàm cũng là một dạng contract và cần chốt sớm như schema.

## 7. Hiểu biết về luồng end-to-end

> Ghi chú: mục này trong mẫu hỏi về Crossref, vector index và freshness monitoring — nội dung của một bài lab RAG khác. Tôi trả lời theo pipeline thực tế của bài Day 9 này.

**Câu trả lời:**

1. **Dữ liệu đi từ nguồn tới kết quả như thế nào:** 9 file CSV Olist được `DataStore` nạp và đánh index một lần. A1 dựng `OrderFacts` từ `claimed_order_id`. A2, A3, A4 nhận artifact đó và bổ sung lịch sử khách, đối soát thanh toán, phân tích giao vận. A5 nhận cả 4 artifact và ra `Verdict` mà không được đọc CSV. A6 lắp thành `CandidateOutput`. A7 kiểm chứng rồi mới cho ghi `output/`.

2. **Tập đánh giá và ID tham chiếu:** 50 file trong `input/` là tập đánh giá cố định. `evidence_ids` đóng vai trò ID tham chiếu — mỗi ID phải dựng được trực tiếp từ CSV theo 5 dạng grammar cho phép, và bị đối chiếu ngược lại key index. ID không tồn tại bị tính là false positive.

3. **Kiểm tra chất lượng khác giám sát ở điểm nào:** contract Pydantic kiểm tra từng bản ghi ngay lúc tạo (đúng kiểu, đúng trần mảng, đúng quy tắc null). Verifier kiểm tra ở mức cả case và có thẩm quyền chặn ghi file. Trace `logging/trace.jsonl` thì không chặn gì cả, nó chỉ ghi lại đã xảy ra những gì để truy vết sau.

4. **Vì sao dùng cùng một tập test cho mọi biến thể:** nhóm có chạy A/B đổi từng cách hiểu một (ví dụ tên category tiếng Bồ hay tiếng Anh). Nếu đổi tập case giữa các lần thì không biết điểm thay đổi do sửa logic hay do case khác nhau. Giữ nguyên 50 case khiến chênh lệch điểm quy được về đúng một biến đã đổi.

5. **Căn cứ để coi là thành công:** verifier trả `pass` cho cả 50 case; chạy lại sinh ra file giống hệt nhau từng byte; và điểm trên trình chấm. Lần nộp gần nhất đạt 67.4696.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hoàng Duy Hưng
**Ngày xác nhận:** 2026-08-05
