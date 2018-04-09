from datetime import datetime


def strOrNone(data):
    return str(data) if data is not None else None


def intOrNone(data):
    return int(data) if data is not None else None


def floatOrNone(data):
    return float(data) if data is not None else None


def strptimeOrNone(data):
    return datetime.strptime(str(data)[0:19], "%Y-%m-%d %H:%M:%S") if data is not None else None


def utcfromtimestampOrNone(data):
    return datetime.utcfromtimestamp(data) if data is not None else None
