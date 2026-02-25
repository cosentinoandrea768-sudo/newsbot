def parse_number(value):
    if value is None:
        return None
    try:
        value = str(value).replace("%", "").replace(",", "")
        return float(value)
    except:
        return None


POSITIVE_WHEN_HIGHER = [
    "GDP",
    "CPI",
    "Core CPI",
    "Retail Sales",
    "Non Farm Payrolls",
    "PMI",
    "Interest Rate",
    "Industrial Production"
]

POSITIVE_WHEN_LOWER = [
    "Unemployment Rate",
    "Jobless Claims",
    "Initial Jobless Claims"
]


def evaluate_impact(event_name, actual, forecast):
    actual = parse_number(actual)
    forecast = parse_number(forecast)

    if actual is None or forecast is None:
        return "⚪ Neutro"

    category = None

    for key in POSITIVE_WHEN_HIGHER:
        if key.lower() in event_name.lower():
            category = "higher"
            break

    for key in POSITIVE_WHEN_LOWER:
        if key.lower() in event_name.lower():
            category = "lower"
            break

    if category is None:
        category = "higher"

    if category == "higher":
        if actual > forecast:
            return "🟢 Positivo"
        elif actual < forecast:
            return "🔴 Negativo"
        else:
            return "⚪ Neutro"

    if category == "lower":
        if actual < forecast:
            return "🟢 Positivo"
        elif actual > forecast:
            return "🔴 Negativo"
        else:
            return "⚪ Neutro"
