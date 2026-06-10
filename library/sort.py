from .config import CUSTOM_PATHS_FILE, RESERVATION_AREA_CODE, load_json, save_json
from .utils import parse_location_code


class SortManager:
    def __init__(self):
        self._custom_paths = []
        self._path_overrides = {}
        self._load_custom_paths()

    def _load_custom_paths(self):
        data = load_json(CUSTOM_PATHS_FILE, {"custom_paths": [], "path_overrides": {}})
        self._custom_paths = data.get("custom_paths", [])
        self._path_overrides = data.get("path_overrides", {})

    def _save_custom_paths(self):
        data = {
            "custom_paths": self._custom_paths,
            "path_overrides": self._path_overrides
        }
        save_json(CUSTOM_PATHS_FILE, data)

    def _sort_key(self, item):
        location = item.get("target_location") or item.get("proper_location") or ""
        is_reserved = item.get("is_reserved", False)

        if is_reserved:
            return (0, 0, "", 0, 0, 0)

        parsed = parse_location_code(location)
        if not parsed:
            return (999, 999, "ZZZ", 999, 999, 999)

        return (
            1,
            parsed["floor"],
            parsed["zone"],
            parsed["row"],
            parsed["level"],
            parsed["position"]
        )

    def sort_books(self, book_list):
        valid_books = []
        invalid_books = []

        for book in book_list:
            location = book.get("target_location") or book.get("proper_location")
            is_reserved = book.get("is_reserved", False)

            if is_reserved:
                valid_books.append(book)
                continue

            if not location:
                invalid_books.append({
                    **book,
                    "error": "无有效位置编码",
                    "error_type": "missing_location"
                })
                continue

            parsed = parse_location_code(location)
            if not parsed:
                invalid_books.append({
                    **book,
                    "error": "位置编码格式无效",
                    "error_type": "invalid_location"
                })
                continue

            valid_books.append(book)

        if self._custom_paths:
            sorted_books = self._apply_custom_paths(valid_books)
        else:
            sorted_books = sorted(valid_books, key=self._sort_key)

        return {
            "sorted_books": sorted_books,
            "invalid_books": invalid_books,
            "total_count": len(book_list),
            "valid_count": len(valid_books),
            "invalid_count": len(invalid_books)
        }

    def _apply_custom_paths(self, books):
        path_order = {}
        for idx, path in enumerate(self._custom_paths):
            path_order[path["prefix"]] = idx

        def custom_sort_key(item):
            location = item.get("target_location") or item.get("proper_location") or ""
            is_reserved = item.get("is_reserved", False)

            if is_reserved:
                return (-1, 0, "", 0, 0, 0)

            path_idx = 999
            for prefix, idx in sorted(path_order.items(), key=lambda x: len(x[0]), reverse=True):
                if location.startswith(prefix):
                    path_idx = idx
                    break

            parsed = parse_location_code(location)
            if not parsed:
                return (999, 999, "ZZZ", 999, 999, 999)

            return (
                path_idx,
                parsed["floor"],
                parsed["zone"],
                parsed["row"],
                parsed["level"],
                parsed["position"]
            )

        return sorted(books, key=custom_sort_key)

    def generate_return_instructions(self, book_list):
        sort_result = self.sort_books(book_list)
        sorted_books = sort_result["sorted_books"]

        instructions = []
        current_zone = None
        step = 1

        for book in sorted_books:
            is_reserved = book.get("is_reserved", False)
            location = book.get("target_location") or book.get("proper_location", "")

            if is_reserved:
                zone_key = "预约保留区"
            else:
                parsed = parse_location_code(location)
                if parsed:
                    zone_key = f"{parsed['floor']}楼{parsed['zone']}区"
                else:
                    zone_key = "未知区域"

            if zone_key != current_zone:
                instructions.append({
                    "type": "zone_change",
                    "step": step,
                    "description": f"前往{zone_key}"
                })
                step += 1
                current_zone = zone_key

            instructions.append({
                "type": "place_book",
                "step": step,
                "rfid": book.get("rfid"),
                "title": book.get("title", ""),
                "call_number": book.get("call_number", ""),
                "location": location,
                "is_reserved": is_reserved,
                "description": f"将《{book.get('title', '未知书名')}》放在 {location}"
            })
            step += 1

        return {
            "instructions": instructions,
            "total_steps": len(instructions),
            "invalid_books": sort_result["invalid_books"],
            "summary": {
                "total_books": sort_result["total_count"],
                "valid_books": sort_result["valid_count"],
                "invalid_books": sort_result["invalid_count"],
                "reserved_books": len([b for b in sorted_books if b.get("is_reserved")])
            }
        }

    def add_custom_path(self, path_prefix, description, priority=0):
        new_path = {
            "prefix": path_prefix,
            "description": description,
            "priority": priority
        }
        self._custom_paths.append(new_path)
        self._custom_paths.sort(key=lambda x: x["priority"])
        self._save_custom_paths()
        return True

    def remove_custom_path(self, path_prefix):
        self._custom_paths = [p for p in self._custom_paths if p["prefix"] != path_prefix]
        self._save_custom_paths()
        return True

    def list_custom_paths(self):
        return self._custom_paths.copy()

    def set_path_override(self, source, target, description=""):
        self._path_overrides[source] = {
            "target": target,
            "description": description
        }
        self._save_custom_paths()
        return True

    def remove_path_override(self, source):
        if source in self._path_overrides:
            del self._path_overrides[source]
            self._save_custom_paths()
            return True
        return False

    def list_path_overrides(self):
        return self._path_overrides.copy()

    def reload(self):
        self._load_custom_paths()
