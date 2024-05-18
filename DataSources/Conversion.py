from datetime import datetime, timezone


def strOrNone(data):
    return str(data) if data is not None else None


def intOrNone(data):
    return int(data) if data is not None else None


def floatOrNone(data):
    return float(data) if data is not None else None


def strptimeOrNone(data):
    return datetime.strptime(str(data)[0:19], "%Y-%m-%d %H:%M:%S") if data is not None else None


def utcfromtimestampOrNone(data):
    return datetime.fromtimestamp(data, timezone.utc) if data is not None else None
