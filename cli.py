#!/usr/bin/env python3
import sys
import argparse
import json

from library.book import BookManager
from library.shelf import ShelfManager
from library.borrow import BorrowManager
from library.sort import SortManager
from library.statistics import StatisticsManager
from library.config import RESERVATION_AREA_CODE


def cmd_scan_return(args):
    book_mgr = BookManager()
    borrow_mgr = BorrowManager(book_mgr, None)
    sort_mgr = SortManager()

    rfids = args.rfids if args.rfids else []
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rfids.append(line)

    if not rfids:
        print("错误: 请提供RFID标签，使用 --rfids 或 --file 参数")
        return 1

    print(f"共扫描到 {len(rfids)} 本书，正在生成归位指令...\n")

    return_results = []
    failed_books = []

    for rfid in rfids:
        book = book_mgr.get_book(rfid)
        if not book:
            failed_books.append({
                "rfid": rfid,
                "error": "图书不存在，请确认RFID是否正确"
            })
            continue

        proper_location = book.get("proper_location")
        if proper_location is None:
            failed_books.append({
                "rfid": rfid,
                "title": book.get("title", ""),
                "call_number": book.get("call_number", ""),
                "error": "无有效应有位置，可能为未采购大类或旧版索书号"
            })
            continue

        success, result = borrow_mgr.return_book(rfid)
        if not success:
            failed_books.append({
                "rfid": rfid,
                "title": book.get("title", ""),
                "error": result
            })
            continue

        return_results.append(result)

    sort_result = sort_mgr.generate_return_instructions(return_results)

    print("=" * 60)
    print("归位路径指令")
    print("=" * 60)

    for inst in sort_result["instructions"]:
        if inst["type"] == "zone_change":
            print(f"\n[步骤 {inst['step']}] → {inst['description']}")
        else:
            status = "【预约书】" if inst.get("is_reserved") else ""
            print(f"  步骤 {inst['step']}: {status}《{inst['title']}》 → {inst['location']}")

    print(f"\n{'=' * 60}")
    print("统计汇总")
    print(f"{'=' * 60}")
    print(f"  总书数: {sort_result['summary']['total_books']}")
    print(f"  可归位: {sort_result['summary']['valid_books']}")
    print(f"  预约书: {sort_result['summary']['reserved_books']}")
    print(f"  异常书: {sort_result['summary']['invalid_books'] + len(failed_books)}")

    if failed_books or sort_result.get("invalid_books"):
        print(f"\n{'=' * 60}")
        print("异常图书列表")
        print(f"{'=' * 60}")
        all_failed = failed_books + sort_result.get("invalid_books", [])
        for i, book in enumerate(all_failed, 1):
            print(f"  {i}. RFID: {book.get('rfid', '未知')}")
            print(f"     原因: {book.get('error', book.get('error_type', '未知错误'))}")
            if book.get("title"):
                print(f"     书名: {book.get('title')}")

    return 0 if not failed_books else 0


def cmd_check_consistency(args):
    book_mgr = BookManager()
    borrow_mgr = BorrowManager(book_mgr, None)

    print("正在检查预约数据一致性...\n")
    issues = borrow_mgr.check_reservation_consistency()

    if not issues:
        print("✓ 预约数据一致，未发现异常")
        return 0

    print(f"发现 {len(issues)} 处不一致：\n")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. RFID: {issue['rfid']}")
        print(f"   问题: {issue['issue']}")
        if issue.get("book_status"):
            print(f"   图书状态: {issue['book_status']}")
        if issue.get("title"):
            print(f"   书名: {issue['title']}")

    if args.fix:
        print("\n正在自动修复...")
        for issue in issues:
            success, msg = borrow_mgr.fix_reservation_consistency(issue["rfid"])
            status = "✓" if success else "✗"
            print(f"  {status} {issue['rfid']}: {msg}")

    return 0


def cmd_stats(args):
    book_mgr = BookManager()
    borrow_mgr = BorrowManager(book_mgr, None)
    stats_mgr = StatisticsManager(book_mgr, borrow_mgr, None)

    if args.type == "summary":
        report = stats_mgr.get_summary_report()
        print("=" * 60)
        print("图书馆统计总览")
        print("=" * 60)
        print(f"  藏书总数: {report['overview']['total_books']}")
        print(f"  在馆: {report['overview']['in_library']}")
        print(f"  借出: {report['overview']['borrowed']}")
        print(f"  借阅率: {report['overview']['borrow_rate']}%")
        print(f"\n  错位率: {report['misplacement']['overall_rate']}%")
        if report['misplacement']['data_quality']['warning']:
            print(f"    注意: {report['misplacement']['data_quality']['warning']}")

    elif args.type == "monthly":
        months = stats_mgr.get_monthly_borrow_stats(args.months)
        print("=" * 60)
        print(f"近 {args.months} 个月借阅统计")
        print("=" * 60)
        print(f"{'月份':<12} {'借出':>8} {'归还':>8} {'净变化':>8} {'数据质量':<10}")
        print("-" * 60)
        for m in months:
            quality = m['data_quality']['status']
            warning = ""
            if quality != "normal":
                warning = f" ({m['data_quality']['warning']})"
            print(f"{m['month']:<12} {m['borrow_count']:>8} {m['return_count']:>8} {m['net_change']:>+8} {quality:<10}{warning}")

    elif args.type == "popular":
        books = stats_mgr.get_popular_books(args.top)
        print("=" * 60)
        print(f"热门图书 TOP {args.top}")
        print("=" * 60)
        for i, book in enumerate(books, 1):
            print(f"{i:>2}. 《{book['title']}》 - 借阅 {book['borrow_count']} 次")
            print(f"    索书号: {book['call_number']}")

    elif args.type == "cold":
        books = stats_mgr.get_cold_books(args.days)
        print("=" * 60)
        print(f"冷门图书（{args.days}天以上未借阅）")
        print("=" * 60)
        for i, book in enumerate(books[:args.top], 1):
            last = book['last_borrow_date']
            print(f"{i:>2}. 《{book['title']}》 - 上次借阅: {last}")
            print(f"    索书号: {book['call_number']}")

    elif args.type == "misplacement":
        stats = stats_mgr.get_misplacement_rate()
        print("=" * 60)
        print("错位统计")
        print("=" * 60)
        print(f"  总错位率: {stats['overall_rate']}%")
        print(f"  抽检总数: {stats['total_checked']}")
        print(f"  错位总数: {stats['total_misplaced']}")
        if stats['data_quality']['warning']:
            print(f"  注意: {stats['data_quality']['warning']}")

        if stats['zone_rates']:
            print(f"\n  各区域错位率:")
            for zone in stats['zone_rates']:
                level = zone['warning_level']
                marker = "🔴" if level == "high" else "🟡" if level == "medium" else "🟢"
                print(f"    {marker} {zone['zone']}: {zone['misplacement_rate']}%")

        if args.analysis:
            analysis = stats_mgr.analyze_misplacement_causes()
            print(f"\n{'=' * 60}")
            print("错位根因分析")
            print(f"{'=' * 60}")
            for cause in analysis['causes']:
                print(f"  • {cause['description']}: {cause['count']}例 ({cause['percentage']}%)")
                print(f"    建议: {cause['suggestion']}")
            if analysis['suggestions']:
                print(f"\n  综合建议:")
                for s in analysis['suggestions']:
                    print(f"    - {s}")

    return 0


def cmd_book(args):
    book_mgr = BookManager()

    if args.action == "get":
        book = book_mgr.get_book(args.rfid)
        if not book:
            print(f"图书不存在: {args.rfid}")
            return 1
        print(json.dumps(book, ensure_ascii=False, indent=2))
    elif args.action == "add":
        data = json.loads(args.data) if args.data else {}
        if not data.get("rfid"):
            data["rfid"] = args.rfid
        success, msg = book_mgr.add_book(data)
        print(f"{msg}")
        if success:
            print(json.dumps(book_mgr.get_book(data["rfid"]), ensure_ascii=False, indent=2))
    elif args.action == "list":
        books = book_mgr.list_books(status=args.status, category=args.category)
        print(f"共 {len(books)} 本")
        for book in books:
            print(f"  {book['rfid']}: 《{book.get('title', '')}》 - {book.get('call_number', '')} - {book.get('status', '')}")

    return 0


def cmd_custom_path(args):
    sort_mgr = SortManager()

    if args.action == "list":
        paths = sort_mgr.list_custom_paths()
        overrides = sort_mgr.list_path_overrides()
        print("自定义路径:")
        if not paths:
            print("  （无）")
        for i, p in enumerate(paths, 1):
            print(f"  {i}. {p['prefix']} - {p['description']} (优先级: {p['priority']})")
        print(f"\n路径覆盖: {len(overrides)} 条")
    elif args.action == "add":
        success = sort_mgr.add_custom_path(args.prefix, args.description, args.priority)
        print("添加成功" if success else "添加失败")
    elif args.action == "remove":
        success = sort_mgr.remove_custom_path(args.prefix)
        print("删除成功" if success else "删除失败")

    return 0


def main():
    parser = argparse.ArgumentParser(description="图书馆自动化归档系统 CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    scan_parser = subparsers.add_parser("scan", help="扫描归还图书并生成归位指令")
    scan_parser.add_argument("--rfids", nargs="+", help="RFID标签列表")
    scan_parser.add_argument("--file", help="从文件读取RFID列表，每行一个")
    scan_parser.set_defaults(func=cmd_scan_return)

    consistency_parser = subparsers.add_parser("consistency", help="检查预约数据一致性")
    consistency_parser.add_argument("--fix", action="store_true", help="自动修复不一致问题")
    consistency_parser.set_defaults(func=cmd_check_consistency)

    stats_parser = subparsers.add_parser("stats", help="统计报表")
    stats_parser.add_argument("type", choices=["summary", "monthly", "popular", "cold", "misplacement"],
                             help="统计类型")
    stats_parser.add_argument("--months", type=int, default=12, help="月度统计的月数")
    stats_parser.add_argument("--top", type=int, default=10, help="热门/冷门图书数量")
    stats_parser.add_argument("--days", type=int, default=365, help="冷门图书判定天数")
    stats_parser.add_argument("--analysis", action="store_true", help="显示错位根因分析")
    stats_parser.set_defaults(func=cmd_stats)

    book_parser = subparsers.add_parser("book", help="图书管理")
    book_parser.add_argument("action", choices=["get", "add", "list"], help="操作")
    book_parser.add_argument("--rfid", help="图书RFID")
    book_parser.add_argument("--data", help="图书数据(JSON格式，用于add)")
    book_parser.add_argument("--status", help="按状态筛选")
    book_parser.add_argument("--category", help="按大类筛选")
    book_parser.set_defaults(func=cmd_book)

    path_parser = subparsers.add_parser("path", help="自定义路径管理")
    path_parser.add_argument("action", choices=["list", "add", "remove"], help="操作")
    path_parser.add_argument("--prefix", help="路径前缀")
    path_parser.add_argument("--description", help="路径描述")
    path_parser.add_argument("--priority", type=int, default=0, help="优先级（数字越小越优先）")
    path_parser.set_defaults(func=cmd_custom_path)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
