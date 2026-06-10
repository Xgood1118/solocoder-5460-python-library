from library.book import BookManager
from library.shelf import ShelfManager
from library.borrow import BorrowManager
from library.sort import SortManager
from library.statistics import StatisticsManager

book_mgr = BookManager()
shelf_mgr = ShelfManager()
borrow_mgr = BorrowManager(book_mgr, shelf_mgr)
sort_mgr = SortManager()
stats_mgr = StatisticsManager(book_mgr, borrow_mgr, shelf_mgr)

results = []

results.append("=== 1. 中图法大类边界 ===")
for cat in ["A", "B", "C", "D", "E", "I", "TP", "Z"]:
    status = "已采购" if book_mgr.is_available_category(cat) else "未采购"
    results.append(f"  {cat}类: {status}")

results.append("")
results.append("=== 2. 旧版索书号兼容 ===")
old_book = book_mgr.get_book("RFID0022")
if old_book:
    results.append(f"  索书号: {old_book.get('call_number')}")
    results.append(f"  应有位置: {old_book.get('proper_location')}")
    results.append(f"  是否旧版: {book_mgr.check_old_call_number(old_book.get('call_number', ''))}")

results.append("")
results.append("=== 3. 预约一致性 ===")
book_mgr.update_book("RFID0003", {"status": "预约"})
issues = borrow_mgr.check_reservation_consistency()
results.append(f"  注入不一致后异常数: {len(issues)}")
borrow_mgr.fix_reservation_consistency("RFID0003")
issues2 = borrow_mgr.check_reservation_consistency()
results.append(f"  修复后异常数: {len(issues2)}")

results.append("")
results.append("=== 4. 统计数据质量 ===")
monthly = stats_mgr.get_monthly_borrow_stats(months=3)
for m in monthly:
    quality = m["data_quality"]["status"]
    warning = m["data_quality"]["warning"] or "正常"
    results.append(f"  {m['month']}: 借出{m['borrow_count']} 归还{m['return_count']} - {quality} ({warning})")

results.append("")
results.append("=== 5. 空位置排序 ===")
test_books = [
    {"rfid": "R1", "title": "书1", "target_location": "2-C-3-4-1"},
    {"rfid": "R2", "title": "旧书", "target_location": None},
    {"rfid": "R3", "title": "书3", "target_location": "1-D-2-1-1"},
]
result = sort_mgr.sort_books(test_books)
results.append(f"  总数: {result['total_count']}, 有效: {result['valid_count']}, 无效: {result['invalid_count']}")
for b in result["invalid_books"]:
    results.append(f"    无效: {b['rfid']} - {b['error']}")

results.append("")
results.append("=== 6. 错位根因分析 ===")
analysis = stats_mgr.analyze_misplacement_causes()
results.append(f"  总记录: {analysis['total_records']}")
for cause in analysis["causes"]:
    results.append(f"    {cause['description']}: {cause['count']}例 ({cause['percentage']}%)")
for s in analysis["suggestions"]:
    results.append(f"    建议: {s}")

results.append("")
results.append("=== 7. 自定义路径 ===")
sort_mgr.add_custom_path("2-C", "文学区优先", 0)
sort_mgr.add_custom_path("4-B", "计算机区次之", 1)
paths = sort_mgr.list_custom_paths()
results.append(f"  自定义路径数: {len(paths)}")
for p in paths:
    results.append(f"    - {p['prefix']}: {p['description']}")

results.append("")
results.append("=== 8. 预约图书归位测试 ===")
borrow_mgr.reserve_book("RFID0005", "R001")
return_info = borrow_mgr.return_book("RFID0005")
results.append(f"  预约书归位位置: {return_info[1].get('target_location') if return_info[0] else '失败'}")
results.append(f"  是否预约区: {return_info[1].get('is_reserved') if return_info[0] else '失败'}")

with open("test_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))

print("测试完成，结果写入 test_results.txt")
