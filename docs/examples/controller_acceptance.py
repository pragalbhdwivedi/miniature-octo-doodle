def clamp(value, lower, upper):
    """
    Clamps value to the inclusive interval [lower, upper].
    
    Args:
        value: The value to clamp.
        lower: The lower bound.
        upper: The upper bound.
        
    Returns:
        lower if value < lower, upper if value > upper, otherwise value.
        
    Raises:
        ValueError: If lower > upper.
    """
    if lower > upper:
        raise ValueError(f"lower bound ({lower}) cannot be greater than upper bound ({upper})")
    
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value