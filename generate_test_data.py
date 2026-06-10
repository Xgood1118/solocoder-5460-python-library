#!/usr/bin/env python3
"""生成测试数据，用于验证图书馆归档系统"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from library.config import (
    BOOKS_FILE, BORROW_RECORDS_FILE, MISPLACEMENT_RECORDS_FILE,
    SHELVES_FILE, DATA_DIR
)
from library.book import BookManager
from library.shelf import ShelfManager
from library.borrow import BorrowManager
from library.sort import SortManager
from library.statistics import StatisticsManager
from library.utils import get_current_time


SAMPLE_BOOKS = [
    {"rfid": "RFID0001", "call_number": "I247.57", "title": "平凡的世界", "author": "路遥"},
    {"rfid": "RFID0002", "call_number": "I247.5", "title": "活着", "author": "余华"},
    {"rfid": "RFID0003", "call_number": "I246.5", "title": "骆驼祥子", "author": "老舍"},
    {"rfid": "RFID0004", "call_number": "I21", "title": "鲁迅全集", "author": "鲁迅"},
    {"rfid": "RFID0005", "call_number": "F275", "title": "卓有成效的管理者", "author": "德鲁克"},
    {"rfid": "RFID0006", "call_number": "F230", "title": "会计学原理", "author": "xxx"},
    {"rfid": "RFID0007", "call_number": "TP311.1", "title": "Python编程从入门到实践", "author": "Eric Matthes"},
    {"rfid": "RFID0008", "call_number": "TP393", "title": "计算机网络", "author": "谢希仁"},
    {"rfid": "RFID0009", "call_number": "H319", "title": "新概念英语", "author": "亚历山大"},
    {"rfid": "RFID0010", "call_number": "G250", "title": "图书馆学概论", "author": "吴慰慈"},
    {"rfid": "RFID0011", "call_number": "R161", "title": "健康饮食指南", "author": "xxx"},
    {"rfid": "RFID0012", "call_number": "K20", "title": "中国通史", "author": "吕思勉"},
    {"rfid": "RFID0013", "call_number": "O13", "title": "高等数学", "author": "同济大学"},
    {"rfid": "RFID0014", "call_number": "P15", "title": "天文学导论", "author": "xxx"},
    {"rfid": "RFID0015", "call_number": "X32", "title": "环境科学概论", "author": "xxx"},
    {"rfid": "RFID0016", "call_number": "Z228", "title": "百科全书", "author": "xxx"},
    {"rfid": "RFID0017", "call_number": "B21", "title": "中国哲学简史", "author": "冯友兰"},
    {"rfid": "RFID0018", "call_number": "D90", "title": "法理学", "author": "张文显"},
    {"rfid": "RFID0019", "call_number": "J228", "title": "中国美术史", "author": "xxx"},
    {"rfid": "RFID0020", "call_number": "C93", "title": "管理学原理", "author": "xxx"},
    {"rfid": "RFID0021", "call_number": "E892", "title": "孙子兵法", "author": "孙武"},
    {"rfid": "RFID0022", "call_number": "OLD001", "title": "旧版索书号测试书", "author": "测试"},
]

READERS = ["R001", "R002", "R003", "R004", "R005"]


def generate_test_data():
    print("正在生成测试数据...")

    if BOOKS_FILE.exists():
        print("  图书数据已存在，跳过")
    else:
        book_mgr = BookManager()
        for book_data in SAMPLE_BOOKS:
            book_data.setdefault("status", "在馆")
            success, msg = book_mgr.add_book(book_data)
            if not success:
                print(f"  警告: {book_data['rfid']} - {msg}")
        print(f"  已生成 {len(SAMPLE_BOOKS)} 本图书数据")

    shelf_mgr = ShelfManager()
    book_mgr = BookManager()
    borrow_mgr = BorrowManager(book_mgr, shelf_mgr)
    stats_mgr = StatisticsManager(book_mgr, borrow_mgr, shelf_mgr)

    if BORROW_RECORDS_FILE.exists():
        print("  借阅记录已存在，跳过")
    else:
        print("  正在生成借阅记录...")
        books = book_mgr.list_books()
        valid_books = [b for b in books if b.get("proper_location")]

        now = datetime.now()
        for i in range(60):
            book = random.choice(valid_books)
            reader = random.choice(READERS)
            days_ago = random.randint(0, 180)
            borrow_time = now - timedelta(days=days_ago, hours=random.randint(0, 23))

            record = {
                "id": i + 1,
                "type": "borrow",
                "rfid": book["rfid"],
                "reader_id": reader,
                "timestamp": borrow_time.strftime("%Y-%m-%d %H:%M:%S")
            }
            borrow_mgr._records.append(record)

            if random.random() > 0.3:
                return_days = random.randint(1, 30)
                return_time = borrow_time + timedelta(days=return_days)
                if return_time < now:
                    return_record = {
                        "id": len(borrow_mgr._records) + 1,
                        "type": "return",
                        "rfid": book["rfid"],
                        "reader_id": reader,
                        "is_reserved": False,
                        "target_location": book.get("proper_location"),
                        "timestamp": return_time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    borrow_mgr._records.append(return_record)

        borrow_mgr._save_records()
        print(f"  已生成 {len(borrow_mgr._records)} 条借阅记录")

    if MISPLACEMENT_RECORDS_FILE.exists():
        print("  错位记录已存在，跳过")
    else:
        print("  正在生成错位记录...")
        books = book_mgr.list_books()
        valid_books = [b for b in books if b.get("proper_location")]

        misplacement_examples = [
            ("floor", "楼层错位"),
            ("zone", "区域错位"),
            ("row", "排架错位"),
            ("level", "层架错位"),
            ("position", "位置偏移"),
        ]

        for i in range(25):
            book = random.choice(valid_books)
            proper = book.get("proper_location", "")
            parts = proper.split("-")
            if len(parts) != 5:
                continue

            error_type = random.choice(misplacement_examples)[0]
            actual_parts = parts.copy()

            if error_type == "floor":
                floor = int(parts[0])
                actual_parts[0] = str(max(1, min(5, floor + random.choice([-1, 1]))))
            elif error_type == "zone":
                zones = ["A", "B", "C", "D"]
                idx = zones.index(parts[1]) if parts[1] in zones else 0
                actual_parts[1] = zones[max(0, min(len(zones)-1, idx + random.choice([-1, 1])))]
            elif error_type == "row":
                row = int(parts[2])
                actual_parts[2] = str(max(1, min(6, row + random.choice([-1, 1]))))
            elif error_type == "level":
                level = int(parts[3])
                actual_parts[3] = str(max(1, min(6, level + random.choice([-1, 1]))))
            else:
                pos = int(parts[4])
                actual_parts[4] = str(max(1, min(30, pos + random.choice([1, 2]))))

            actual = "-".join(actual_parts)
            days_ago = random.randint(0, 90)
            record_time = datetime.now() - timedelta(days=days_ago)

            stats_mgr._misplacement_records.append({
                "id": i + 1,
                "rfid": book["rfid"],
                "actual_location": actual,
                "proper_location": proper,
                "inspector": random.choice(["张馆长", "李管理员", "王管理员"]),
                "timestamp": record_time.strftime("%Y-%m-%d %H:%M:%S"),
                "month": record_time.strftime("%Y-%m")
            })

        stats_mgr._save_misplacement_records()
        print(f"  已生成 {len(stats_mgr._misplacement_records)} 条错位记录")

    print("\n测试数据生成完成！")
    print(f"数据目录: {DATA_DIR}")


def test_boundary_scenarios():
    print("\n" + "=" * 60)
    print("边界场景测试")
    print("=" * 60)

    book_mgr = BookManager()
    shelf_mgr = ShelfManager()
    borrow_mgr = BorrowManager(book_mgr, shelf_mgr)
    sort_mgr = SortManager()
    stats_mgr = StatisticsManager(book_mgr, borrow_mgr, shelf_mgr)

    print("\n1. 中图法大类边界测试")
    print("-" * 40)
    test_categories = ["I", "C", "E", "L", "TP"]
    for cat in test_categories:
        is_available = book_mgr.is_available_category(cat)
        status = "✓ 已采购" if is_available else "✗ 未采购"
        print(f"  {cat} 类: {status}")

    print("\n2. 旧版索书号兼容测试")
    print("-" * 40)
    old_book = book_mgr.get_book("RFID0022")
    if old_book:
        proper = old_book.get("proper_location")
        is_old = book_mgr.check_old_call_number(old_book.get("call_number", ""))
        print(f"  索书号: {old_book.get('call_number')}")
        print(f"  应有位置: {proper}")
        print(f"  是否旧版格式: {is_old}")
        print(f"  状态: {'警告 - 无有效位置' if proper is None else '正常'}")

    print("\n3. 预约一致性测试")
    print("-" * 40)
    issues = borrow_mgr.check_reservation_consistency()
    print(f"  当前不一致数量: {len(issues)}")

    book_mgr.update_book("RFID0003", {"status": "预约"})
    issues = borrow_mgr.check_reservation_consistency()
    print(f"  注入状态不一致后: {len(issues)} 处异常")
    if issues:
        print(f"    - {issues[0]['rfid']}: {issues[0]['issue']}")

    success, msg = borrow_mgr.fix_reservation_consistency("RFID0003")
    print(f"  修复结果: {msg}")
    issues = borrow_mgr.check_reservation_consistency()
    print(f"  修复后异常数: {len(issues)}")

    print("\n4. 统计数据质量测试")
    print("-" * 40)
    monthly = stats_mgr.get_monthly_borrow_stats(months=6)
    for m in monthly[:3]:
        quality = m['data_quality']['status']
        warning = m['data_quality']['warning'] or "正常"
        print(f"  {m['month']}: 借出{m['borrow_count']} / 归还{m['return_count']} - {warning}")

    print("\n5. 空位置编码测试")
    print("-" * 40)
    test_books = [
        {"rfid": "RFID0022", "title": "旧版书", "target_location": None, "proper_location": None},
        {"rfid": "RFID0001", "title": "平凡的世界", "target_location": "2-C-3-4-1", "proper_location": "2-C-3-4-1"},
    ]
    result = sort_mgr.sort_books(test_books)
    print(f"  总书数: {result['total_count']}")
    print(f"  有效: {result['valid_count']}")
    print(f"  无效: {result['invalid_count']}")
    if result['invalid_books']:
        for b in result['invalid_books']:
            print(f"    - {b['rfid']}: {b['error']}")

    print("\n6. 自定义路径测试")
    print("-" * 40)
    paths = sort_mgr.list_custom_paths()
    print(f"  当前自定义路径数量: {len(paths)}")
    sort_mgr.add_custom_path("2-C", "文学区优先", priority=0)
    sort_mgr.add_custom_path("4-B", "计算机区次之", priority=1)
    paths = sort_mgr.list_custom_paths()
    print(f"  添加后数量: {len(paths)}")
    for p in paths:
        print(f"    - {p['prefix']}: {p['description']} (优先级: {p['priority']})")

    print("\n7. 错位根因分析测试")
    print("-" * 40)
    analysis = stats_mgr.analyze_misplacement_causes()
    print(f"  总错位记录: {analysis['total_records']}")
    print(f"  根因分类:")
    for cause in analysis['causes']:
        print(f"    - {cause['description']}: {cause['count']}例 ({cause['percentage']}%)")
    if analysis['suggestions']:
        print(f"  建议:")
        for s in analysis['suggestions']:
            print(f"    - {s}")

    print("\n" + "=" * 60)
    print("边界场景测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    generate_test_data()
    test_boundary_scenarios()
