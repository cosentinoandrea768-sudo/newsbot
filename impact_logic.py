def parse_number(value):
    if value is None:
        return None
    try:
        value = str(value).replace("%","").replace(",","").strip()
        if "K" in value:
            return float(value.replace("K",""))*1000
        if "M" in value:
            return float(value.replace("M",""))*1_000_000
        return float(value)
    except:
        return None

def calculate_surprise(actual, forecast):
    actual = parse_number(actual)
    forecast = parse_number(forecast)
    if actual is None or forecast is None or forecast == 0:
        return 0
    return ((actual - forecast)/abs(forecast))*100

POSITIVE_WHEN_HIGHER = [
    "GDP","CPI","Core CPI","Retail Sales","Non Farm Payrolls",
    "PMI","Interest Rate","Industrial Production"
]

POSITIVE_WHEN_LOWER = [
    "Unemployment Rate","Jobless Claims","Initial Jobless Claims"
]

def evaluate_impact(event_name, actual, forecast):
    actual_num = parse_number(actual)
    forecast_num = parse_number(forecast)
    if actual_num is None or forecast_num is None:
        return "⚪ Neutro", 0

    surprise = calculate_surprise(actual, forecast)
    abs_surprise = abs(surprise)

    category = "higher"
    for key in POSITIVE_WHEN_LOWER:
        if key.lower() in event_name.lower():
            category = "lower"
            break

    direction = 1
    if category == "higher":
        direction = 1 if actual_num > forecast_num else -1
    else:
        direction = 1 if actual_num < forecast_num else -1

    if actual_num == forecast_num:
        return "⚪ Neutro", 0

    if abs_surprise > 2:
        strength = 2
        label = "🟢 STRONG POSITIVE" if direction>0 else "🔴 STRONG NEGATIVE"
    else:
        strength = 1
        label = "🟢 Mild Positive" if direction>0 else "🔴 Mild Negative"

    score = strength * direction
    return label, score
