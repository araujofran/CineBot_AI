import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

def duration_seconds(value):
    if not value:
        return None
    try:
        number = float(value)
        if math.isfinite(number) and number >= 0:
            return max(1, math.ceil(number))
    except (ValueError, TypeError):
        pass
    pieces = re.findall(r'(\d+(?:\.\d+)?)(ms|d|h|m|s)', str(value).lower())
    if pieces and re.fullmatch(r'(?:\d+(?:\.\d+)?(?:ms|d|h|m|s))+', str(value).lower()):
        factors = {'ms':0.001,'s':1,'m':60,'h':3600,'d':86400}
        return max(1, math.ceil(sum(float(n)*factors[unit] for n,unit in pieces)))
    return None

def retry_delay(response):
    value = response.headers.get('retry-after')
    delay = duration_seconds(value)
    if delay is not None:
        return delay, False
    if value:
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(1, math.ceil((dt-datetime.now(timezone.utc)).total_seconds())), False
        except (ValueError, TypeError, OverflowError):
            pass
    resets = []
    for kind in ('requests','tokens'):
        if response.headers.get(f'x-ratelimit-remaining-{kind}') == '0':
            delay = duration_seconds(response.headers.get(f'x-ratelimit-reset-{kind}'))
            if delay is not None:
                resets.append(delay)
    if resets:
        return max(resets), False
    try:
        text = response.json().get('error',{}).get('message','')
        match = re.search(r'try again in\s+([0-9.dhms]+)', text, re.I)
        if match:
            delay = duration_seconds(match.group(1).rstrip('.'))
            if delay is not None:
                return delay, False
    except (ValueError, AttributeError):
        pass
    return 60, True
