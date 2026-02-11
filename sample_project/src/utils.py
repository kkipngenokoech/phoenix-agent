"""Utility functions with intentional code smells:
- Long parameter lists
- Magic numbers
- Complex conditionals
"""


def calculate_shipping_cost(
    weight, length, width, height, origin_zip, dest_zip,
    is_fragile, is_express, is_insured, insurance_value
):
    """Calculate shipping cost - too many parameters!"""
    volume = length * width * height

    # Magic numbers everywhere
    if weight < 1:
        base_cost = 5.99
    elif weight < 5:
        base_cost = 12.99
    elif weight < 20:
        base_cost = 24.99
    elif weight < 50:
        base_cost = 49.99
    else:
        base_cost = 89.99

    # Volume surcharge with magic numbers
    if volume > 5000:
        base_cost += 15.0
    elif volume > 2000:
        base_cost += 8.50
    elif volume > 1000:
        base_cost += 4.25

    # Distance calculation (simplified)
    distance_factor = abs(int(origin_zip[:3]) - int(dest_zip[:3])) / 999.0
    distance_surcharge = distance_factor * 25.0

    total = base_cost + distance_surcharge

    if is_fragile:
        total += 7.50

    if is_express:
        total *= 1.75

    if is_insured:
        total += max(insurance_value * 0.02, 3.99)

    return round(total, 2)


def format_user_display(user_data, include_email=True, include_phone=True,
                         include_address=True, include_age=True,
                         max_name_length=50, date_format="%Y-%m-%d"):
    """Format user data for display - too many parameters and complex logic."""
    parts = []

    name = user_data.get("username", "Unknown")
    if len(name) > max_name_length:
        name = name[:max_name_length - 3] + "..."
    parts.append(f"Name: {name}")

    if include_email and user_data.get("email"):
        email = user_data["email"]
        # Mask email for privacy
        at_pos = email.find("@")
        if at_pos > 2:
            masked = email[0] + "*" * (at_pos - 2) + email[at_pos - 1:]
        else:
            masked = email
        parts.append(f"Email: {masked}")

    if include_phone and user_data.get("phone"):
        phone = user_data["phone"]
        # Mask phone
        if len(phone) > 4:
            masked_phone = "*" * (len(phone) - 4) + phone[-4:]
        else:
            masked_phone = phone
        parts.append(f"Phone: {masked_phone}")

    if include_address and user_data.get("address"):
        parts.append(f"Address: {user_data['address']}")

    if include_age and user_data.get("age"):
        parts.append(f"Age: {user_data['age']}")

    if user_data.get("created_at"):
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(user_data["created_at"])
            parts.append(f"Joined: {dt.strftime(date_format)}")
        except (ValueError, TypeError):
            pass

    return " | ".join(parts)


def categorize_value(value, thresholds=None):
    """Categorize a numeric value into buckets - nested conditionals."""
    if thresholds is None:
        thresholds = {
            "critical": 90,
            "high": 70,
            "medium": 40,
            "low": 10,
        }

    if value is None:
        return "unknown"

    try:
        num = float(value)
    except (ValueError, TypeError):
        return "invalid"

    if num < 0:
        return "negative"
    elif num >= thresholds.get("critical", 90):
        return "critical"
    elif num >= thresholds.get("high", 70):
        return "high"
    elif num >= thresholds.get("medium", 40):
        return "medium"
    elif num >= thresholds.get("low", 10):
        return "low"
    else:
        return "minimal"
