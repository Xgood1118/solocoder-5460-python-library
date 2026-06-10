from flask import Flask, jsonify, request

from library.book import BookManager
from library.shelf import ShelfManager
from library.borrow import BorrowManager
from library.sort import SortManager
from library.statistics import StatisticsManager
from library.config import HTTP_PORT, RESERVATION_AREA_CODE


def create_app():
    app = Flask(__name__)

    book_mgr = BookManager()
    shelf_mgr = ShelfManager()
    borrow_mgr = BorrowManager(book_mgr, shelf_mgr)
    sort_mgr = SortManager()
    stats_mgr = StatisticsManager(book_mgr, borrow_mgr, shelf_mgr)

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok", "service": "library-archive-system"})

    @app.route("/api/books/<rfid>", methods=["GET"])
    def get_book(rfid):
        book = book_mgr.get_book(rfid)
        if not book:
            return jsonify({"error": "图书不存在"}), 404

        proper_location = book.get("proper_location")
        is_old_format = book_mgr.check_old_call_number(book.get("call_number", ""))
        is_available = book_mgr.is_available_category(book.get("category", ""))

        result = {
            "book": book,
            "location_available": proper_location is not None,
            "is_old_call_number_format": is_old_format,
            "category_available": is_available
        }

        if proper_location is None and book.get("call_number"):
            result["warning"] = "该书索书号无对应位置映射，请确认是否为图书馆采购大类"

        return jsonify(result)

    @app.route("/api/books", methods=["GET"])
    def list_books():
        status = request.args.get("status")
        category = request.args.get("category")
        books = book_mgr.list_books(status=status, category=category)
        return jsonify({"count": len(books), "books": books})

    @app.route("/api/books", methods=["POST"])
    def add_book():
        data = request.get_json()
        if not data or "rfid" not in data:
            return jsonify({"error": "缺少必要参数 rfid"}), 400

        call_number = data.get("call_number", "")
        if call_number:
            from library.utils import parse_call_number
            cat, _, _ = parse_call_number(call_number)
            if cat and not book_mgr.is_available_category(cat):
                return jsonify({
                    "error": f"中图法大类 {cat} 不在图书馆采购范围内",
                    "available_categories": book_mgr.get_available_categories()
                }), 400

        success, msg = book_mgr.add_book(data)
        if not success:
            return jsonify({"error": msg}), 400
        return jsonify({"message": msg, "book": book_mgr.get_book(data["rfid"])})

    @app.route("/api/books/<rfid>/location", methods=["GET"])
    def get_book_location(rfid):
        book = book_mgr.get_book(rfid)
        if not book:
            return jsonify({"error": "图书不存在"}), 404

        proper_location = book.get("proper_location")
        current_location = shelf_mgr.find_book_location(rfid)

        result = {
            "rfid": rfid,
            "title": book.get("title", ""),
            "call_number": book.get("call_number", ""),
            "proper_location": proper_location,
            "current_location": current_location,
            "status": book.get("status", "")
        }

        if proper_location is None:
            result["warning"] = "无有效应有位置，请检查索书号格式或中图法大类"
            result["error_type"] = "no_proper_location"

        return jsonify(result)

    @app.route("/api/borrow/return", methods=["POST"])
    def return_book():
        data = request.get_json()
        if not data or "rfid" not in data:
            return jsonify({"error": "缺少必要参数 rfid"}), 400

        rfid = data["rfid"]
        book = book_mgr.get_book(rfid)
        if not book:
            return jsonify({"error": "图书不存在，请确认RFID是否正确"}), 404

        proper_location = book.get("proper_location")
        call_number = book.get("call_number", "")

        if proper_location is None:
            is_old = book_mgr.check_old_call_number(call_number)
            warning = "该书索书号无对应位置映射"
            if is_old:
                warning += "，可能为旧版索书号格式"
            return jsonify({
                "error": "无法生成有效归位指令",
                "warning": warning,
                "book": book,
                "suggestion": "请人工确认图书分类后手动处理"
            }), 422

        success, result = borrow_mgr.return_book(rfid)
        if not success:
            return jsonify({"error": result}), 400

        if result.get("is_reserved"):
            result["note"] = "该书已被预约，请放置到预约保留区"

        return jsonify(result)

    @app.route("/api/borrow/return/batch", methods=["POST"])
    def batch_return():
        data = request.get_json()
        if not data or "rfids" not in data:
            return jsonify({"error": "缺少必要参数 rfids"}), 400

        rfids = data["rfids"]
        return_results = []
        books_for_sort = []
        failed_books = []

        for rfid in rfids:
            book = book_mgr.get_book(rfid)
            if not book:
                failed_books.append({
                    "rfid": rfid,
                    "error": "图书不存在"
                })
                continue

            success, result = borrow_mgr.return_book(rfid)
            if not success:
                failed_books.append({
                    "rfid": rfid,
                    "error": result,
                    "title": book.get("title", "")
                })
                continue

            return_results.append(result)
            books_for_sort.append(result)

        sort_result = sort_mgr.generate_return_instructions(books_for_sort)

        return jsonify({
            "total": len(rfids),
            "success": len(return_results),
            "failed": len(failed_books) + len(sort_result.get("invalid_books", [])),
            "instructions": sort_result["instructions"],
            "total_steps": sort_result["total_steps"],
            "failed_books": failed_books + sort_result.get("invalid_books", []),
            "summary": sort_result["summary"]
        })

    @app.route("/api/sort/return-path", methods=["POST"])
    def get_return_path():
        data = request.get_json()
        if not data or "books" not in data:
            return jsonify({"error": "缺少必要参数 books"}), 400

        books = data["books"]
        result = sort_mgr.generate_return_instructions(books)
        return jsonify(result)

    @app.route("/api/reservations", methods=["GET"])
    def list_reservations():
        reservations = borrow_mgr.list_reservations()
        return jsonify({"count": len(reservations), "reservations": reservations})

    @app.route("/api/reservations/consistency", methods=["GET"])
    def check_reservation_consistency():
        issues = borrow_mgr.check_reservation_consistency()
        return jsonify({
            "inconsistent_count": len(issues),
            "issues": issues
        })

    @app.route("/api/reservations/consistency/fix", methods=["POST"])
    def fix_reservation_consistency():
        data = request.get_json()
        if not data or "rfid" not in data:
            return jsonify({"error": "缺少必要参数 rfid"}), 400

        success, msg = borrow_mgr.fix_reservation_consistency(data["rfid"])
        if not success:
            return jsonify({"error": msg}), 400
        return jsonify({"message": msg})

    @app.route("/api/statistics/summary", methods=["GET"])
    def get_stats_summary():
        report = stats_mgr.get_summary_report()
        return jsonify(report)

    @app.route("/api/statistics/misplacement", methods=["GET"])
    def get_misplacement_stats():
        return jsonify(stats_mgr.get_misplacement_rate())

    @app.route("/api/statistics/misplacement/analysis", methods=["GET"])
    def get_misplacement_analysis():
        return jsonify(stats_mgr.analyze_misplacement_causes())

    @app.route("/api/statistics/monthly", methods=["GET"])
    def get_monthly_stats():
        months = request.args.get("months", 12, type=int)
        return jsonify({"months": stats_mgr.get_monthly_borrow_stats(months)})

    @app.route("/api/statistics/popular", methods=["GET"])
    def get_popular_books():
        top_n = request.args.get("top", 10, type=int)
        books = stats_mgr.get_popular_books(top_n)
        return jsonify({"count": len(books), "books": books})

    @app.route("/api/statistics/cold", methods=["GET"])
    def get_cold_books():
        days = request.args.get("days", 365, type=int)
        top_n = request.args.get("top", 10, type=int)
        books = stats_mgr.get_cold_books(days)
        return jsonify({"count": len(books[:top_n]), "books": books[:top_n]})

    @app.route("/api/inspections", methods=["POST"])
    def add_inspection():
        data = request.get_json()
        if not data or "records" not in data:
            return jsonify({"error": "缺少必要参数 records"}), 400

        results = []
        for item in data["records"]:
            rfid = item.get("rfid")
            result_type = item.get("result")
            if not rfid or result_type not in ("correct", "misplaced"):
                results.append({"rfid": rfid, "success": False, "error": "参数无效"})
                continue

            if result_type == "misplaced":
                record = stats_mgr.add_inspection_record(
                    rfid=rfid,
                    result="misplaced",
                    actual_location=item.get("actual_location"),
                    proper_location=item.get("proper_location"),
                    inspector=item.get("inspector")
                )
            else:
                record = stats_mgr.add_inspection_record(
                    rfid=rfid,
                    result="correct",
                    location=item.get("location"),
                    inspector=item.get("inspector")
                )
            results.append({"rfid": rfid, "success": True, "record_id": record["id"]})

        return jsonify({"count": len(results), "results": results})

    @app.route("/api/config/categories", methods=["GET"])
    def get_categories():
        from library.config import CATEGORY_MAP_FILE, load_json
        cat_map = load_json(CATEGORY_MAP_FILE, {})
        return jsonify({
            "available_categories": cat_map.get("available_categories", []),
            "all_categories": cat_map.get("category_locations", {})
        })

    @app.route("/api/config/custom-paths", methods=["GET"])
    def get_custom_paths():
        return jsonify({
            "custom_paths": sort_mgr.list_custom_paths(),
            "path_overrides": sort_mgr.list_path_overrides()
        })

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)
