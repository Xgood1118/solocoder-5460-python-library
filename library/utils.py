import re
from datetime import datetime


def parse_call_number(call_number):
    match = re.match(r'^([A-Z])(\d+(?:\.\d+)?)(.*)$', call_number.strip())
    if not match:
        return None, None, None
    category = match.group(1)
    number = match.group(2)
    suffix = match.group(3).strip()
    return category, number, suffix


def parse_location_code(location_code):
    if not location_code:
        return None
    parts = location_code.split("-")
    if len(parts) != 5:
        return None
    try:
        floor = int(parts[0])
        zone = parts[1]
        row = int(parts[2])
        level = int(parts[3])
        position = int(parts[4])
        return {
            "floor": floor,
            "zone": zone,
            "row": row,
            "level": level,
            "position": position
        }
    except (ValueError, IndexError):
        return None


def format_location_code(floor, zone, row, level, position):
    return f"{floor}-{zone}-{row}-{level}-{position}"


def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_month_key(date_str=None):
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    else:
        dt = datetime.now()
    return dt.strftime("%Y-%m")
