# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                          |
| --------------- | ------------------------------------------------- |
| Họ và tên       | Sẻ Thế Hưng                                       |
| MSSV            | 01822                                             |
| Khóa/Lớp        | K4                                                |
| Vai trò chính   | Thành viên 3 — Analysis (đối soát thanh toán, phân tích giao vận) |
| Ngày hoàn thành | 2026-08-05                                        |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | ------------------ | -------------- | --------------- | ---------- |
| Đối soát thanh toán | `src/ec_dispute/tools/calculations.py` — `build_payment_reconciliation` | `OrderFacts` + các dòng payment | `PaymentReconciliation` | Hoàn thành |
| Phân tích giao vận | `src/ec_dispute/tools/calculations.py` — `build_delivery_analysis`, `_parse_time` | `OrderFacts` | `DeliveryAnalysis` + `seller_handoff_analysis` | Hoàn thành |
| Agent A3 | `src/ec_dispute/agents/payment.py` — `PaymentAgent` | Envelope `order_facts` | Envelope `payment_reconciliation` (T3) | Hoàn thành |
| Agent A4 | `src/ec_dispute/agents/delivery.py` — `DeliveryAgent` | Envelope `order_facts` | Envelope `delivery_analysis` (T3) | Hoàn thành |
| Cổng hồi quy và nộp bài | `src/ec_dispute/qa/golden_check.py` — `assert_submission_complete`, `assert_rerun_is_identical` | Thư mục `output/` | Khẳng định đủ 50 file và chạy lại giống hệt | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Xác nhận `OrderFacts` mang đủ dữ liệu để tính toán | TV2 | `seller_shipping_limits` chứa mốc sớm nhất theo từng seller, A4 không phải tự suy lại từ danh sách item |
| Khai `payment:<order_id>:<seq>` vào provenance | TV2 (A6) | A6 dựng được `affected_entities.payment_ids` mà không cần quyền đọc CSV |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | -------------------------- | ---------------- | ------------- |
| Tính `expected_total_brl`, `difference_brl`, `reconciled` | `build_payment_reconciliation` | Đối soát cho 44 case có item; `null` cho 6 case không có item | So với ví dụ README §6: EC_002 ra 194.0 / 18.27 / 212.27, khớp từng số |
| Tính `delivery_variance_hours` và handoff variance | `build_delivery_analysis` | Phân tích giao vận cho 50 case | EC_002 ra 87.39 giờ và 1.04 giờ, khớp ví dụ README |
| Xử lý dữ liệu thiếu | `_parse_time` + nhánh null | 14 case null ngày giao, 13 case null ngày bàn giao carrier | Không case nào bị gán `late_handoff=true` khi variance là `null` |
| Cổng kiểm tra trước khi nộp | `qa/golden_check.py` | `assert_submission_complete`, `assert_rerun_is_identical` | `missing_case_ids()` trả rỗng sau khi chạy `run.py` |

Nêu một output cụ thể mà phần việc của tôi tạo ra hoặc giúp xác minh:

`output/EC_002.json` — mục `delivery_analysis` và `payment_reconciliation` do tôi sinh ra trùng khớp **từng con số** với ví dụ mẫu trong README §6 (delivered 2018-03-31 15:23:33, estimated 2018-03-28 00:00:00, variance 87.39; shipping limit 2018-03-15 20:31:15, handoff variance 1.04, late true; item 194.0, freight 18.27, expected 212.27, payment 212.27, difference 0.0, reconciled true). Đây là bằng chứng trực tiếp cho thấy hai công thức tính đã đúng.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi trả lời hai câu hỏi định lượng của mỗi case: khách đã trả đúng số tiền chưa, và hàng có giao trễ không — trễ do seller giao chậm cho đơn vị vận chuyển hay do đơn vị vận chuyển. Hai nhóm trường này chiếm 30% tổng điểm.

### Cách triển khai

**Đối soát thanh toán.** Cộng `payment_value` của mọi dòng payment (đã sắp theo `payment_sequential`), so với tổng `price` cộng `freight_value` lấy từ artifact của A1. `reconciled` là `abs(difference) <= 0.10`, trong đó giá trị biên 0.10 được tính là đạt. Với đơn không có dòng item nào, cả `item_total`, `freight_total`, `expected_total`, `difference` và `reconciled` đều trả `null` chứ không phải `0.0` — vì `0.0` mang nghĩa "đã tính ra bằng không", còn ở đây là "không tính được".

**Phân tích giao vận.** `delivery_variance_hours` là hiệu giữa ngày giao thực tế và ngày dự kiến, đổi ra giờ. Với từng seller, `handoff_variance_hours` so ngày carrier nhận hàng với mốc `shipping_limit_date` **sớm nhất** của seller đó — đó mới là hạn thực sự ràng buộc họ. `late_handoff` chỉ đúng khi variance dương.

**Quy tắc quan trọng nhất: thiếu dữ liệu không phải bằng chứng vi phạm.** Nếu thiếu ngày giao hoặc ngày bàn giao carrier thì variance là `null` và `late_handoff` là `false`. Không được suy ra là trễ. Đây là nhánh gặp nhiều nhất trong dữ liệu: 14/50 case thiếu ngày giao, 13/50 thiếu ngày bàn giao carrier. Contract cũng chặn cứng trường hợp `late_handoff=true` khi variance là `null`, nên nếu tôi viết sai thì chương trình dừng ngay chứ không âm thầm cho ra kết quả sai.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `OrderFacts` từ A1 (item kèm `price_brl`, `freight_value_brl`, mốc shipping limit theo seller, 4 timestamp của đơn); các dòng payment từ `DataStore` |
| Output | `PaymentReconciliation` (8 trường), `DeliveryAnalysis` (gồm `seller_handoff_analysis` và `late_handoff_seller_ids`) |
| Module phụ thuộc | `tools/lookups.py` (TV2) cung cấp `OrderFacts`; `contracts/` quy định kiểu và quy tắc null |
| Module sử dụng output | A5 `policy_engine.decide` (TV1) dùng để chọn nhánh policy; A6 lắp vào output cuối |
| Điều kiện lỗi cần xử lý | Timestamp rỗng hoặc sai định dạng → `_parse_time` trả `None`; đơn không có item row; đơn không có seller nào (danh sách handoff rỗng); `difference` sát ngưỡng 0.10 |

### Cách xác minh

```bash
.venv/bin/python run.py
.venv/bin/python -m pytest -q
```

- **Kết quả mong đợi:** sinh đủ 50 file; các trường tiền và giờ làm tròn 2 chữ số; đơn thiếu dữ liệu trả `null` đúng chỗ.
- **Kết quả thực tế:** 50 file được ghi; 76 test xanh; `delivery_analysis` và `payment_reconciliation` của EC_002 trùng khớp ví dụ README §6.
- **Artifact/log:** `output/EC_002.json` (case có đủ trễ seller và split payment), `output/EC_012.json` (case `unavailable`, không có item row, mọi trường đối soát là `null`).

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** một seller có thể có nhiều dòng item trong cùng một đơn, mỗi dòng một `shipping_limit_date` khác nhau. Phải chọn mốc nào để kết luận seller đó bàn giao trễ.
- **Các phương án đã cân nhắc:** (1) lấy mốc muộn nhất — seller chỉ bị coi là trễ khi vượt hạn cuối cùng; (2) lấy mốc sớm nhất — trễ ngay khi vượt hạn đầu tiên; (3) so từng dòng item riêng.
- **Phương án đã chọn:** mốc sớm nhất của từng seller.
- **Lý do:** công thức trong README ghi rõ `handoff_variance_hours = order_delivered_carrier_date - shipping_limit_date sớm nhất của seller`. Ngoài ra điều kiện của `late_delivery_seller` là "carrier nhận hàng sau ít nhất một `shipping_limit_date`", nên lấy mốc sớm nhất mới đúng nghĩa "ít nhất một".
- **Bằng chứng quyết định phù hợp:** EC_002 cho `handoff_variance_hours = 1.04` đúng bằng con số trong ví dụ README. Phân loại toàn tập ra 10 case `late_delivery_seller` và 10 case `late_delivery_logistics` — nếu chọn mốc muộn nhất thì một số case sẽ trượt sai sang nhánh logistics.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `difference_brl` xuất hiện giá trị `-0.0` trong 6 file output (EC_002, EC_008, EC_022, EC_036, EC_048, EC_049).
- **Lệnh hoặc bước tái hiện:** `python run.py` rồi `grep -l -- "-0.0" output/*.json`.
- **Nguyên nhân gốc:** `difference = payment_total - expected_total` cho ra một số âm cực nhỏ do sai số dấu phẩy động, và `round()` của Python giữ nguyên dấu âm thành `-0.0`. Khi ghi ra JSON nó thành chuỗi `"-0.0"`, có nguy cơ bị trình chấm coi là khác `0.0`.
- **Cách xử lý:** chuẩn hoá âm-không ngay trong hàm làm tròn của contract, nên mọi trường tiền và giờ đều được xử lý một lần thay vì vá riêng từng chỗ tính.
- **Cách xác minh sau khi sửa:** chạy lại `run.py`, đếm số file chứa `-0.0` → 0; 76 test vẫn xanh.
- **Điều học được:** với số thực, kiểm tra bằng mắt trên một case là không đủ. Lỗi này không làm sai phép tính nào cả, chỉ sai ở khâu biểu diễn, nên chỉ lộ ra khi rà toàn bộ output chứ không lộ qua test đơn lẻ.

## 7. Hiểu biết về luồng end-to-end

> Ghi chú: mục này trong mẫu hỏi về Crossref, vector index và freshness monitoring — nội dung của một bài lab RAG khác. Tôi trả lời theo pipeline thực tế của bài Day 9 này.

**Câu trả lời:**

1. **Dữ liệu đi từ nguồn tới kết quả:** CSV Olist được `DataStore` nạp và đánh index. A1 dựng `OrderFacts` từ `claimed_order_id`. Phần của tôi là A3 và A4: nhận `OrderFacts`, tính tiền và tính giờ, trả về hai artifact. A5 dùng chúng để chọn nhánh policy, A6 lắp thành file cuối, A7 kiểm chứng rồi mới cho ghi `output/`.

2. **Tập đánh giá và ID tham chiếu:** 50 case trong `input/`. `evidence_ids` là các ID tham chiếu, dựng trực tiếp từ CSV. Riêng phần tôi phải khai `payment:<order_id>:<seq>` cho mọi dòng payment đã cộng, vì A6 lấy `payment_ids` từ đúng nguồn đó.

3. **Kiểm tra chất lượng khác giám sát ở điểm nào:** contract kiểm ngay lúc tạo artifact và chặn luôn — ví dụ không cho `late_handoff=true` khi variance là `null`, không cho một phần trường đối soát là `null` còn phần kia có giá trị. Verifier kiểm ở mức cả case. `golden_check` kiểm ở mức cả lượt chạy: đủ 50 file và chạy lại phải ra kết quả giống hệt. Trace chỉ ghi lại, không chặn gì.

4. **Vì sao dùng cùng một tập test cho mọi biến thể:** nhóm chạy A/B để dò các chỗ đề bài nói mơ hồ. Chỉ khi giữ nguyên 50 case thì chênh lệch điểm mới quy được về đúng cái vừa sửa.

5. **Căn cứ để coi là thành công:** với phần của tôi là hai mục `delivery_analysis` và `payment_reconciliation` khớp ví dụ chuẩn trong README, cộng với `assert_rerun_is_identical` không raise — nghĩa là không có gì bất định lọt vào phép tính. Ở mức cả nhóm là điểm trên trình chấm, hiện 67.4696.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Sẻ Thế Hưng
**Ngày xác nhận:** 2026-08-05
