# Judge audit (M2)

Đã chạy trên bộ replay công khai, backend REPLAY nên không cần API key:

```powershell
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

`FAIL` là lớp dương (judge cần phát hiện câu trả lời lỗi). Ngưỡng chấp nhận: κ ≥ 0.6, precision ≥ 0.8, recall ≥ 0.7.

| Tiêu chí | n | κ | Precision | Recall | Ma trận (TP/FP/FN/TN) | Đạt FLOORS? | Quyết định |
|---|---:|---:|---:|---:|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24 / 4 / 6 / 66 | Có | Dùng có giám sát; giữ review người cho trường hợp mơ hồ về giọng điệu. |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 9 / 0 / 21 / 70 | Không | Loại khỏi chấm tự động; không đủ nhạy để bắt câu trả lời không hữu ích/sai nội dung. |

## Audit thủ công các bất đồng

Đã rà 10 bất đồng đầu tiên được lệnh audit in ra (5 mỗi tiêu chí). “Judge nói” là nhãn PASS/FAIL của judge; “người nói” là nhãn human trong CSV. Với các ca dưới đây, đánh giá dựa trên ghi chú trong CSV và nội dung câu trả lời.

| # | Case | Tiêu chí | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---:|---|---|---|---|---|---|
| 1 | H-008 | tone_ok | PASS | FAIL | Người | “em”, “nha”, “check giúp em” suồng sã trong giọng CSKH; judge bỏ sót. |
| 2 | H-017 | tone_ok | PASS | FAIL | Người | Cách xưng hô “bạn” và “nha” không phù hợp ngữ cảnh; judge coi là thân thiện. |
| 3 | H-029 | tone_ok | PASS | FAIL | Người | “không cần nhắn thêm” mang giọng ra lệnh; judge bị ảnh hưởng bởi lời mở đầu lịch sự. |
| 4 | H-042 | tone_ok | FAIL | PASS | Người | Câu ngắn nhưng đủ thông tin về số tiền và thời gian; judge phạt vì thiếu lời xin lỗi dù tiêu chí tone không bắt buộc xin lỗi ở mọi câu. |
| 5 | H-051 | tone_ok | FAIL | PASS | Người | “refund” được CS LogiX cho phép theo ghi chú bộ dữ liệu; judge phạt từ tiếng Anh quá cứng nhắc. |
| 6 | HL-015 | helpful | PASS | FAIL | Người | Câu báo hoàn 55.000đ nhưng nhãn ghi số đúng là 40.000đ; judge bỏ sót lỗi nội dung/số tiền. |
| 7 | HL-016 | helpful | PASS | FAIL | Người | Báo 55.000đ thay vì 35.000đ; văn phong dài và lịch sự không sửa được sai số tiền. |
| 8 | HL-020 | helpful | PASS | FAIL | Người | Báo 90.000đ thay vì 120.000đ; judge bỏ qua thông tin tiền sai. |
| 9 | HL-028 | helpful | PASS | FAIL | Người | Báo 50.000đ thay vì 35.000đ; phần xin lỗi lặp lại khiến câu dài nhưng judge vẫn cho PASS. |
| 10 | HL-035 | helpful | PASS | FAIL | Người | Báo 50.000đ thay vì 35.000đ; judge không bắt được sai lệch nội dung. |

### Điểm nhãn cần lưu ý

Ghi chú của `H-081` trong CSV nói nhãn human có thể sai: câu từ chối “Đơn O-107 chưa đủ điều kiện hoàn...” có thể đúng theo ngữ cảnh, trong khi judge gắn FAIL. Metric tone ở trên được giữ nguyên theo nhãn CSV hiện tại để khớp kết quả lệnh; không tự ý sửa nhãn nguồn trong báo cáo audit. Cần người phụ trách bộ dữ liệu xác minh trước khi dùng H-081 làm gold label.

## Kết luận

- **Dùng `tone_ok` có giám sát:** cả ba floor đều đạt trên 100 mẫu (κ=0.757, P=0.857, R=0.800). Tuy nhiên, các bất đồng cho thấy judge áp dụng quy tắc cứng về lời xin lỗi/từ tiếng Anh và bỏ sót xưng hô suồng sã hoặc câu ra lệnh. Không dùng nó làm cổng duy nhất cho quyết định nhạy cảm.
- **Loại `helpful` khỏi chấm tự động hiện tại:** recall chỉ 0.300, κ=0.375; ma trận có 21 false negative. Judge thường đánh PASS cho câu trả lời có số tiền sai. Tiền phải được kiểm tra bằng code đối chiếu ledger, không dựa vào judge ngôn ngữ.
- Kết quả chỉ đo trên replay công khai; chưa có held-out độc lập. Trước khi mở rộng dùng judge, cần thêm nhãn người mới, xử lý nhãn bất đồng như H-081, và chạy audit lại trên tập chưa dùng khi hiệu chỉnh.
