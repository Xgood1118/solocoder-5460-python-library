from .config import (
    SHELVES_FILE, FLOORS, ZONES_PER_FLOOR, ROWS_PER_ZONE,
    LEVELS_PER_ROW, BOOKS_PER_LEVEL, ZONE_LABELS, RESERVATION_AREA_CODE,
    load_json, save_json
)
from .utils import parse_location_code, format_location_code


class ShelfManager:
    def __init__(self):
        self._shelves = {}
        self._occupied = {}
        self._load_shelves()

    def _load_shelves(self):
        data = load_json(SHELVES_FILE, {"shelves": {}, "occupied": {}})
        self._shelves = data.get("shelves", {})
        self._occupied = data.get("occupied", {})
        if not self._shelves:
            self._initialize_shelves()

    def _save_shelves(self):
        data = {
            "shelves": self._shelves,
            "occupied": self._occupied
        }
        save_json(SHELVES_FILE, data)

    def _initialize_shelves(self):
        self._shelves = {}
        self._occupied = {}
        for floor in range(1, FLOORS + 1):
            for zone_idx in range(ZONES_PER_FLOOR):
                zone = ZONE_LABELS[zone_idx]
                for row in range(1, ROWS_PER_ZONE + 1):
                    for level in range(1, LEVELS_PER_ROW + 1):
                        for pos in range(1, BOOKS_PER_LEVEL + 1):
                            code = format_location_code(floor, zone, row, level, pos)
                            self._shelves[code] = {
                                "floor": floor,
                                "zone": zone,
                                "row": row,
                                "level": level,
                                "position": pos,
                                "capacity": 1,
                                "description": f"{floor}楼{zone}区第{row}排第{level}层第{pos}位"
                            }
        self._shelves[RESERVATION_AREA_CODE] = {
            "floor": 0,
            "zone": "RES",
            "row": 0,
            "level": 0,
            "position": 0,
            "capacity": 999,
            "description": "预约保留区"
        }
        self._save_shelves()

    def get_shelf(self, location_code):
        return self._shelves.get(location_code)

    def is_valid_location(self, location_code):
        return location_code in self._shelves

    def get_book_at(self, location_code):
        return self._occupied.get(location_code)

    def place_book(self, location_code, rfid):
        if not self.is_valid_location(location_code):
            return False, "位置不存在"
        if location_code == RESERVATION_AREA_CODE:
            if location_code not in self._occupied:
                self._occupied[location_code] = []
            self._occupied[location_code].append(rfid)
            self._save_shelves()
            return True, "已放入预约保留区"
        if location_code in self._occupied:
            return False, "该位置已被占用"
        self._occupied[location_code] = rfid
        self._save_shelves()
        return True, "放置成功"

    def remove_book(self, location_code, rfid=None):
        if location_code == RESERVATION_AREA_CODE:
            if location_code in self._occupied and rfid in self._occupied[location_code]:
                self._occupied[location_code].remove(rfid)
                if not self._occupied[location_code]:
                    del self._occupied[location_code]
                self._save_shelves()
                return True, "移除成功"
            return False, "预约区无此书"
        if location_code not in self._occupied:
            return False, "该位置没有书"
        if rfid and self._occupied[location_code] != rfid:
            return False, "位置上的书不匹配"
        del self._occupied[location_code]
        self._save_shelves()
        return True, "移除成功"

    def find_book_location(self, rfid):
        for loc, book_rfid in self._occupied.items():
            if loc == RESERVATION_AREA_CODE:
                if rfid in book_rfid:
                    return loc
            else:
                if book_rfid == rfid:
                    return loc
        return None

    def get_zone_statistics(self, floor, zone):
        total = 0
        occupied = 0
        for row in range(1, ROWS_PER_ZONE + 1):
            for level in range(1, LEVELS_PER_ROW + 1):
                for pos in range(1, BOOKS_PER_LEVEL + 1):
                    code = format_location_code(floor, zone, row, level, pos)
                    if code in self._shelves:
                        total += 1
                        if code in self._occupied:
                            occupied += 1
        return {
            "floor": floor,
            "zone": zone,
            "total": total,
            "occupied": occupied,
            "available": total - occupied
        }

    def list_all_zones(self):
        zones = []
        for floor in range(1, FLOORS + 1):
            for zone in ZONE_LABELS:
                zones.append(self.get_zone_statistics(floor, zone))
        return zones

    def get_reservation_books(self):
        return self._occupied.get(RESERVATION_AREA_CODE, [])

    def clear_location(self, location_code):
        if location_code in self._occupied:
            del self._occupied[location_code]
            self._save_shelves()
            return True
        return False

    def get_all_locations(self):
        return list(self._shelves.keys())

    def get_occupied_count(self):
        count = 0
        for loc, val in self._occupied.items():
            if loc == RESERVATION_AREA_CODE:
                count += len(val)
            else:
                count += 1
        return count

    def reload(self):
        self._load_shelves()
