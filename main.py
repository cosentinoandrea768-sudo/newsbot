# ==============================
# INDICATORS
# ==============================
print("Controllo Economic Indicators...")

feed = feedparser.parse(RSS_INDICATORS)
print("Indicatori trovati:", len(feed.entries))

for item in feed.entries:
    title = item.title

    # Filtro valuta
    if "[USD]" not in title and "[EUR]" not in title:
        continue

    # Filtro impatto
    if "High Impact" not in title:
        continue

    title_it = safe_translate(title)
    date = parse_date(item).strftime("%Y-%m-%d %H:%M UTC")

    previous = getattr(item, "previous", "-")
    forecast = getattr(item, "forecast", "-")
    actual = getattr(item, "actual", "-")

    impact, _ = evaluate_impact(title, actual, forecast)

    msg = (
        f"📊 *ECONOMIC INDICATOR*\n\n"
        f"🏷 {title_it}\n"
        f"🕒 {date}\n\n"
        f"Previous: {previous}\n"
        f"Forecast: {forecast}\n"
        f"Actual: {actual}\n\n"
        f"📈 Impacto stimato: {impact}"
    )

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=msg,
            parse_mode="Markdown"
        )
        await asyncio.sleep(1.5)
    except Exception as e:
        print("Errore indicatori:", e)
