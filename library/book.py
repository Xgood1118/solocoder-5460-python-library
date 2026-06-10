from .config import BOOKS_FILE, CATEGORY_MAP_FILE, load_json, save_json
from .utils import parse_call_number, format_location_code


class BookManager:
    def __init__(self):
        self._cache = {}
        self._category_map = load_json(CATEGORY_MAP_FILE, {})
        self._load_books()

    def _load_books(self):
        books = load_json(BOOKS_FILE, [])
        self._cache = {}
        for book in books:
            self._cache[book["rfid"]] = book

    def _save_books(self):
        books = list(self._cache.values())
        save_json(BOOKS_FILE, books)

    def get_book(self, rfid):
        return self._cache.get(rfid)

    def get_book_by_call_number(self, call_number):
        for book in self._cache.values():
            if book.get("call_number") == call_number:
                return book
        return None

    def add_book(self, book_data):
        rfid = book_data["rfid"]
        if rfid in self._cache:
            return False, "图书已存在"
        call_number = book_data.get("call_number", "")
        category, number, suffix = parse_call_number(call_number)
        proper_location = self._calculate_proper_location(call_number)
        book_data["category"] = category or ""
        book_data["proper_location"] = proper_location
        book_data["status"] = book_data.get("status", "在馆")
        book_data["current_location"] = book_data.get("current_location", proper_location)
        self._cache[rfid] = book_data
        self._save_books()
        return True, "添加成功"

    def update_book(self, rfid, updates):
        if rfid not in self._cache:
            return False, "图书不存在"
        self._cache[rfid].update(updates)
        if "call_number" in updates:
            call_number = updates["call_number"]
            category, _, _ = parse_call_number(call_number)
            self._cache[rfid]["category"] = category or ""
            self._cache[rfid]["proper_location"] = self._calculate_proper_location(call_number)
        self._save_books()
        return True, "更新成功"

    def delete_book(self, rfid):
        if rfid not in self._cache:
            return False, "图书不存在"
        del self._cache[rfid]
        self._save_books()
        return True, "删除成功"

    def update_status(self, rfid, status):
        if rfid not in self._cache:
            return False, "图书不存在"
        self._cache[rfid]["status"] = status
        self._save_books()
        return True, "状态更新成功"

    def _calculate_proper_location(self, call_number):
        if not call_number:
            return None
        category, number, suffix = parse_call_number(call_number)
        if not category:
            return None

        available_categories = self._category_map.get("available_categories", [])
        if category not in available_categories:
            return None

        prefix = category + number if number else category
        prefix_locations = self._category_map.get("prefix_locations", {})

        matched_prefix = None
        for p in sorted(prefix_locations.keys(), key=len, reverse=True):
            if call_number.startswith(p):
                matched_prefix = p
                break

        if matched_prefix:
            loc = prefix_locations[matched_prefix]
            return format_location_code(
                loc["floor"], loc["zone"], loc["row"], loc["level"], loc["start_position"]
            )

        category_locations = self._category_map.get("category_locations", {})
        cat_loc = category_locations.get(category)
        if cat_loc:
            return format_location_code(
                cat_loc["floor"], cat_loc["zone"], 1, 1, 1
            )

        return None

    def list_books(self, status=None, category=None):
        result = list(self._cache.values())
        if status:
            result = [b for b in result if b.get("status") == status]
        if category:
            result = [b for b in result if b.get("category") == category]
        return result

    def get_all_rfids(self):
        return list(self._cache.keys())

    def is_available_category(self, category):
        available = self._category_map.get("available_categories", [])
        return category in available

    def get_available_categories(self):
        return self._category_map.get("available_categories", [])

    def reload(self):
        self._category_map = load_json(CATEGORY_MAP_FILE, {})
        self._load_books()

    def check_old_call_number(self, call_number):
        category, number, suffix = parse_call_number(call_number)
        if not category:
            return True
        proper_loc = self._calculate_proper_location(call_number)
        if proper_loc is None and category in self.get_available_categories():
            return True
        return False
