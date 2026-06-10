from datetime import datetime, timedelta
from collections import defaultdict

from .config import MISPLACEMENT_RECORDS_FILE, load_json, save_json
from .utils import get_month_key, get_current_time


class StatisticsManager:
    def __init__(self, book_manager=None, borrow_manager=None, shelf_manager=None):
        self._misplacement_records = []
        self._book_manager = book_manager
        self._borrow_manager = borrow_manager
        self._shelf_manager = shelf_manager
        self._load_misplacement_records()

    def _load_misplacement_records(self):
        data = load_json(MISPLACEMENT_RECORDS_FILE, [])
        self._misplacement_records = data

    def _save_misplacement_records(self):
        save_json(MISPLACEMENT_RECORDS_FILE, self._misplacement_records)

    def set_managers(self, book_manager, borrow_manager, shelf_manager):
        self._book_manager = book_manager
        self._borrow_manager = borrow_manager
        self._shelf_manager = shelf_manager

    def add_misplacement_record(self, rfid, actual_location, proper_location, inspector=None):
        record = {
            "id": len(self._misplacement_records) + 1,
            "rfid": rfid,
            "actual_location": actual_location,
            "proper_location": proper_location,
            "inspector": inspector,
            "timestamp": get_current_time(),
            "month": get_month_key()
        }
        self._misplacement_records.append(record)
        self._save_misplacement_records()
        return record

    def get_monthly_borrow_stats(self, months=12):
        if not self._borrow_manager:
            return []

        records = self._borrow_manager.get_records(record_type="borrow")
        monthly_counts = defaultdict(int)
        monthly_returns = defaultdict(int)

        for record in records:
            month_key = get_month_key(record.get("timestamp", ""))
            monthly_counts[month_key] += 1

        return_records = self._borrow_manager.get_records(record_type="return")
        for record in return_records:
            month_key = get_month_key(record.get("timestamp", ""))
            monthly_returns[month_key] += 1

        all_months = set(list(monthly_counts.keys()) + list(monthly_returns.keys()))
        sorted_months = sorted(all_months, reverse=True)[:months]

        result = []
        for month in sorted(sorted_months):
            borrow_count = monthly_counts.get(month, 0)
            return_count = monthly_returns.get(month, 0)
            result.append({
                "month": month,
                "borrow_count": borrow_count,
                "return_count": return_count,
                "net_change": borrow_count - return_count,
                "data_quality": self._assess_data_quality(borrow_count, return_count)
            })

        return result

    def _assess_data_quality(self, borrow_count, return_count):
        if borrow_count == 0 and return_count == 0:
            return {
                "status": "no_data",
                "warning": "本月无任何借阅/归还数据"
            }
        if borrow_count < 5 or return_count < 5:
            return {
                "status": "low_volume",
                "warning": "本月数据量较少，统计结果可能不具代表性"
            }
        return {
            "status": "normal",
            "warning": None
        }

    def get_popular_books(self, top_n=10):
        if not self._book_manager or not self._borrow_manager:
            return []

        all_rfids = self._book_manager.get_all_rfids()
        borrow_counts = []

        for rfid in all_rfids:
            count = self._borrow_manager.get_borrow_count_for_book(rfid)
            book = self._book_manager.get_book(rfid)
            if book:
                borrow_counts.append({
                    "rfid": rfid,
                    "title": book.get("title", ""),
                    "call_number": book.get("call_number", ""),
                    "borrow_count": count
                })

        borrow_counts.sort(key=lambda x: x["borrow_count"], reverse=True)
        return borrow_counts[:top_n]

    def get_cold_books(self, days=365):
        if not self._book_manager or not self._borrow_manager:
            return []

        threshold_date = datetime.now() - timedelta(days=days)
        all_books = self._book_manager.list_books()
        cold_books = []

        for book in all_books:
            rfid = book["rfid"]
            records = self._borrow_manager.get_records(rfid=rfid, record_type="borrow")
            if not records:
                last_borrow_date = None
            else:
                latest_record = records[-1]
                last_borrow_date = datetime.strptime(
                    latest_record["timestamp"], "%Y-%m-%d %H:%M:%S"
                )

            if last_borrow_date is None or last_borrow_date < threshold_date:
                cold_books.append({
                    "rfid": rfid,
                    "title": book.get("title", ""),
                    "call_number": book.get("call_number", ""),
                    "last_borrow_date": last_borrow_date.strftime("%Y-%m-%d") if last_borrow_date else "从未借阅",
                    "days_not_borrowed": (datetime.now() - last_borrow_date).days if last_borrow_date else -1
                })

        cold_books.sort(key=lambda x: x["days_not_borrowed"], reverse=True)
        return cold_books

    def get_misplacement_rate(self, by_zone=True):
        if not self._misplacement_records:
            return {
                "overall_rate": 0,
                "zone_rates": [],
                "data_quality": {
                    "status": "no_data",
                    "warning": "暂无错位记录数据"
                }
            }

        monthly_rates = defaultdict(lambda: {"misplaced": 0, "total": 0})
        zone_rates = defaultdict(lambda: {"misplaced": 0, "total": 0})

        for record in self._misplacement_records:
            month = record.get("month", "")
            monthly_rates[month]["misplaced"] += 1
            monthly_rates[month]["total"] += 1

            proper_loc = record.get("proper_location", "")
            if proper_loc and len(proper_loc.split("-")) >= 2:
                zone_key = proper_loc.split("-")[0] + "-" + proper_loc.split("-")[1]
                zone_rates[zone_key]["misplaced"] += 1

        total_misplaced = len(self._misplacement_records)
        total_checked = total_misplaced
        overall_rate = total_misplaced / total_checked * 100 if total_checked > 0 else 0

        zone_stats = []
        for zone_key, data in sorted(zone_rates.items()):
            rate = data["misplaced"] / data["total"] * 100 if data["total"] > 0 else 0
            zone_stats.append({
                "zone": zone_key,
                "misplaced_count": data["misplaced"],
                "total_checked": data["total"],
                "misplacement_rate": round(rate, 2),
                "warning_level": "high" if rate > 10 else "medium" if rate > 5 else "low"
            })

        data_quality = {
            "status": "normal",
            "warning": None
        }
        if total_checked == 0:
            data_quality = {
                "status": "no_data",
                "warning": "暂无抽检数据"
            }
        elif total_checked < 20:
            data_quality = {
                "status": "low_sample",
                "warning": "抽检样本量较少，错位率仅供参考"
            }

        return {
            "overall_rate": round(overall_rate, 2),
            "total_checked": total_checked,
            "total_misplaced": total_misplaced,
            "zone_rates": zone_stats,
            "data_quality": data_quality
        }

    def analyze_misplacement_causes(self):
        if not self._misplacement_records:
            return {
                "total_records": 0,
                "causes": [],
                "suggestions": ["暂无足够数据进行根因分析"]
            }

        zone_misplacements = defaultdict(int)
        floor_misplacements = defaultdict(int)
        off_by_one = 0
        wrong_level = 0
        wrong_row = 0
        wrong_zone = 0
        wrong_floor = 0

        for record in self._misplacement_records:
            proper = record.get("proper_location", "")
            actual = record.get("actual_location", "")

            if proper and actual:
                proper_parts = proper.split("-")
                actual_parts = actual.split("-")
                if len(proper_parts) == 5 and len(actual_parts) == 5:
                    if proper_parts[0] != actual_parts[0]:
                        wrong_floor += 1
                    elif proper_parts[1] != actual_parts[1]:
                        wrong_zone += 1
                    elif proper_parts[2] != actual_parts[2]:
                        wrong_row += 1
                    elif proper_parts[3] != actual_parts[3]:
                        wrong_level += 1
                    else:
                        try:
                            pos_diff = abs(int(proper_parts[4]) - int(actual_parts[4]))
                            if pos_diff <= 2:
                                off_by_one += 1
                        except ValueError:
                            pass

            if proper and len(proper.split("-")) >= 2:
                zone_key = proper.split("-")[0] + "-" + proper.split("-")[1]
                zone_misplacements[zone_key] += 1
                floor_misplacements[proper.split("-")[0]] += 1

        total = len(self._misplacement_records)
        causes = []

        if wrong_floor > 0:
            causes.append({
                "type": "wrong_floor",
                "count": wrong_floor,
                "percentage": round(wrong_floor / total * 100, 1),
                "description": "楼层错误",
                "suggestion": "可能是管理员记错了大类所在楼层，建议加强大类位置培训"
            })

        if wrong_zone > 0:
            causes.append({
                "type": "wrong_zone",
                "count": wrong_zone,
                "percentage": round(wrong_zone / total * 100, 1),
                "description": "区域错误",
                "suggestion": "区域标识可能不清晰，建议检查区域指示牌"
            })

        if wrong_row > 0:
            causes.append({
                "type": "wrong_row",
                "count": wrong_row,
                "percentage": round(wrong_row / total * 100, 1),
                "description": "排架错误",
                "suggestion": "排号标识可能混淆，建议在每排两端增加醒目标识"
            })

        if wrong_level > 0:
            causes.append({
                "type": "wrong_level",
                "count": wrong_level,
                "percentage": round(wrong_level / total * 100, 1),
                "description": "层架错误",
                "suggestion": "层号标识可能不清，建议在每层侧面增加层号标识"
            })

        if off_by_one > 0:
            causes.append({
                "type": "position_shift",
                "count": off_by_one,
                "percentage": round(off_by_one / total * 100, 1),
                "description": "位置偏移（1-2位）",
                "suggestion": "可能是取放时的细微偏差，属于正常误差范围"
            })

        high_error_zones = sorted(zone_misplacements.items(), key=lambda x: x[1], reverse=True)[:3]

        suggestions = []
        if high_error_zones:
            suggestions.append(f"错位高发区域: {', '.join([z[0] for z in high_error_zones])}，建议重点检查这些区域的标识")
        if wrong_floor > total * 0.3:
            suggestions.append("楼层错误占比较高，建议在每楼层入口处设置大类分布图")
        if wrong_level > total * 0.2:
            suggestions.append("层架错误较多，建议在书架侧面用大号数字标注层号")

        if not suggestions:
            suggestions.append("当前错位分布较为均匀，建议持续观察")

        return {
            "total_records": total,
            "causes": sorted(causes, key=lambda x: x["count"], reverse=True),
            "high_error_zones": [{"zone": z, "count": c} for z, c in high_error_zones],
            "suggestions": suggestions
        }

    def get_summary_report(self):
        monthly_stats = self.get_monthly_borrow_stats(months=6)
        popular_books = self.get_popular_books(10)
        cold_books = self.get_cold_books(365)
        misplacement_stats = self.get_misplacement_rate()
        misplacement_analysis = self.analyze_misplacement_causes()

        total_books = len(self._book_manager.get_all_rfids()) if self._book_manager else 0
        in_library = len(self._book_manager.list_books(status="在馆")) if self._book_manager else 0
        borrowed = len(self._book_manager.list_books(status="借出")) if self._book_manager else 0

        return {
            "overview": {
                "total_books": total_books,
                "in_library": in_library,
                "borrowed": borrowed,
                "borrow_rate": round(borrowed / total_books * 100, 1) if total_books > 0 else 0
            },
            "monthly_trend": monthly_stats,
            "top_popular": popular_books,
            "top_cold": cold_books[:10],
            "misplacement": misplacement_stats,
            "misplacement_analysis": misplacement_analysis,
            "generated_at": get_current_time()
        }

    def get_misplacement_records(self, limit=100):
        return self._misplacement_records[-limit:]

    def reload(self):
        self._load_misplacement_records()
