def clamp(value, lower, upper):
    if lower > upper:
        raise ValueError("lower must be less than or equal to upper")
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value
