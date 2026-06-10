from .config import BORROW_RECORDS_FILE, load_json, save_json, RESERVATION_AREA_CODE
from .utils import get_current_time


class BorrowManager:
    def __init__(self, book_manager=None, shelf_manager=None):
        self._records = []
        self._active_reservations = {}
        self._book_manager = book_manager
        self._shelf_manager = shelf_manager
        self._load_records()

    def _load_records(self):
        data = load_json(BORROW_RECORDS_FILE, {"records": [], "active_reservations": {}})
        self._records = data.get("records", [])
        self._active_reservations = data.get("active_reservations", {})

    def _save_records(self):
        data = {
            "records": self._records,
            "active_reservations": self._active_reservations
        }
        save_json(BORROW_RECORDS_FILE, data)

    def set_managers(self, book_manager, shelf_manager):
        self._book_manager = book_manager
        self._shelf_manager = shelf_manager

    def _add_record(self, record_type, rfid, reader_id=None, **kwargs):
        record = {
            "id": len(self._records) + 1,
            "type": record_type,
            "rfid": rfid,
            "reader_id": reader_id,
            "timestamp": get_current_time(),
        }
        record.update(kwargs)
        self._records.append(record)
        self._save_records()
        return record

    def borrow_book(self, rfid, reader_id):
        if not self._book_manager:
            return False, "Book manager not set"
        book = self._book_manager.get_book(rfid)
        if not book:
            return False, "图书不存在"
        if book["status"] != "在馆":
            return False, f"图书状态为{book['status']}，无法借出"

        self._book_manager.update_status(rfid, "借出")

        if self._shelf_manager:
            current_loc = self._shelf_manager.find_book_location(rfid)
            if current_loc:
                self._shelf_manager.remove_book(current_loc, rfid)

        self._add_record("borrow", rfid, reader_id)
        return True, "借出成功"

    def return_book(self, rfid):
        if not self._book_manager:
            return False, "Book manager not set"
        book = self._book_manager.get_book(rfid)
        if not book:
            return False, "图书不存在"

        is_reserved = self.is_book_reserved(rfid)
        proper_location = book.get("proper_location")

        if is_reserved:
            self._book_manager.update_status(rfid, "预约")
            target_location = RESERVATION_AREA_CODE
            location_description = "预约保留区"
        else:
            self._book_manager.update_status(rfid, "在馆")
            target_location = proper_location
            location_description = proper_location or "（位置待确定）"

        if self._shelf_manager and target_location:
            self._shelf_manager.place_book(target_location, rfid)

        self._add_record("return", rfid, is_reserved=is_reserved, target_location=target_location)

        result = {
            "rfid": rfid,
            "title": book.get("title", ""),
            "call_number": book.get("call_number", ""),
            "is_reserved": is_reserved,
            "target_location": target_location,
            "location_description": location_description,
            "proper_location": proper_location
        }
        return True, result

    def reserve_book(self, rfid, reader_id):
        if not self._book_manager:
            return False, "Book manager not set"
        book = self._book_manager.get_book(rfid)
        if not book:
            return False, "图书不存在"

        if rfid in self._active_reservations:
            return False, "该书已被预约"

        self._active_reservations[rfid] = {
            "reader_id": reader_id,
            "reserve_time": get_current_time()
        }

        if book["status"] == "在馆":
            self._book_manager.update_status(rfid, "预约")

        self._add_record("reserve", rfid, reader_id)
        self._save_records()
        return True, "预约成功"

    def cancel_reservation(self, rfid):
        if rfid not in self._active_reservations:
            return False, "该书没有被预约"

        reservation = self._active_reservations.pop(rfid)
        reader_id = reservation.get("reader_id")

        if self._book_manager:
            book = self._book_manager.get_book(rfid)
            if book and book["status"] == "预约":
                self._book_manager.update_status(rfid, "在馆")

        if self._shelf_manager:
            self._shelf_manager.remove_book(RESERVATION_AREA_CODE, rfid)

        self._add_record("cancel_reserve", rfid, reader_id)
        self._save_records()
        return True, "取消预约成功"

    def pick_up_reserved(self, rfid, reader_id):
        if rfid not in self._active_reservations:
            return False, "该书没有被预约"

        reservation = self._active_reservations[rfid]
        if reservation.get("reader_id") != reader_id:
            return False, "预约人不匹配"

        del self._active_reservations[rfid]

        if self._book_manager:
            self._book_manager.update_status(rfid, "借出")

        if self._shelf_manager:
            self._shelf_manager.remove_book(RESERVATION_AREA_CODE, rfid)

        self._add_record("pick_up", rfid, reader_id)
        self._save_records()
        return True, "取书成功"

    def is_book_reserved(self, rfid):
        return rfid in self._active_reservations

    def get_reservation_info(self, rfid):
        return self._active_reservations.get(rfid)

    def list_reservations(self):
        results = []
        for rfid, info in self._active_reservations.items():
            book_info = {}
            if self._book_manager:
                book = self._book_manager.get_book(rfid)
                if book:
                    book_info = {
                        "title": book.get("title", ""),
                        "call_number": book.get("call_number", ""),
                        "status": book.get("status", "")
                    }
            results.append({
                "rfid": rfid,
                "reader_id": info.get("reader_id"),
                "reserve_time": info.get("reserve_time"),
                **book_info
            })
        return results

    def check_reservation_consistency(self):
        inconsistencies = []
        if not self._book_manager:
            return inconsistencies

        for rfid, _ in self._active_reservations.items():
            book = self._book_manager.get_book(rfid)
            if book and book.get("status") not in ["预约", "借出"]:
                inconsistencies.append({
                    "rfid": rfid,
                    "issue": "有预约记录但图书状态不是预约/借出",
                    "book_status": book.get("status")
                })

        all_books = self._book_manager.list_books()
        for book in all_books:
            if book.get("status") == "预约" and book["rfid"] not in self._active_reservations:
                inconsistencies.append({
                    "rfid": book["rfid"],
                    "issue": "图书状态为预约但无预约记录",
                    "title": book.get("title", "")
                })

        return inconsistencies

    def fix_reservation_consistency(self, rfid):
        book = self._book_manager.get_book(rfid) if self._book_manager else None
        if not book:
            return False, "图书不存在"

        has_reservation_record = rfid in self._active_reservations
        book_status_is_reserved = book.get("status") == "预约"

        if has_reservation_record and not book_status_is_reserved:
            self._book_manager.update_status(rfid, "预约")
            return True, "已将图书状态更新为预约"

        if not has_reservation_record and book_status_is_reserved:
            self._book_manager.update_status(rfid, "在馆")
            return True, "已清除图书预约状态"

        return False, "数据一致，无需修复"

    def get_records(self, rfid=None, record_type=None, limit=None):
        records = self._records
        if rfid:
            records = [r for r in records if r.get("rfid") == rfid]
        if record_type:
            records = [r for r in records if r.get("type") == record_type]
        if limit:
            records = records[-limit:]
        return records

    def get_borrow_count_for_book(self, rfid):
        return len([r for r in self._records if r.get("type") == "borrow" and r.get("rfid") == rfid])

    def reload(self):
        self._load_records()
