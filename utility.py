import math


def format_human_number(value):
    if math.isnan(value):
        return ""
    val, abs_val = float(value), abs(value)
    if abs_val < 1000:
        return f"{val:,.2f}"
    idx = min(int(math.log10(abs_val) // 3), 3)
    return f"{val / (10 ** (idx * 3)):.2f}{['', 'K', 'M', 'B'][idx]}"

def format_percentage(value):
    if math.isnan(value):
        return "n/a"
    return f"{value:.2%}"
