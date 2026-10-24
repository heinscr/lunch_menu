"""Medway Middle School weekday lunch menus for Tronbyt."""
load("render.star", "render")
load("http.star", "http")
load("cache.star", "cache")
load("encoding/json.star", "json")
load("time.star", "time")
load("schema.star", "schema")

API_DOMAIN = "https://medwayschools.api.nutrislice.com"
MENU_ORIGIN = "https://medwayschools.nutrislice.com"
SCHOOL_SLUG = "medway-middle-school"
MENU_TYPE_SLUG = "lunch"
FIRST_SCREEN = [["M", 0], ["T", 1], ["W", 2]]
SECOND_SCREEN = [["Th", 3], ["Fr", 4], ["", -1]]

def get_schema():
    return schema.Schema(version = "1", fields = [
        schema.Text(id = "timezone", name = "School timezone", desc = "IANA timezone used to choose the school week.", default = "US/Eastern", icon = "gear"),
        schema.Text(id = "display_time_seconds", name = "Display Time Seconds", desc = "Match Tronbyt's display time. Split evenly between the two menu screens.", default = "60", icon = "gear"),
    ])

def pad2(value):
    text = str(value)
    return "0" + text if len(text) < 2 else text

def add_days(date, count):
    parts = date.split("-")
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])
    for unused in range(count):
        day += 1
        if month == 2:
            month_days = 29 if year % 400 == 0 or (year % 4 == 0 and year % 100 != 0) else 28
        elif month == 4 or month == 6 or month == 9 or month == 11:
            month_days = 30
        else:
            month_days = 31
        if day > month_days:
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1
    return str(year) + "-" + pad2(month) + "-" + pad2(day)

def monday_of_school_week(today, weekday):
    if weekday == "Sat":
        return add_days(today, 2)
    if weekday == "Sun":
        return add_days(today, 1)
    return today

def menu_url(monday):
    parts = monday.split("-")
    return API_DOMAIN + "/menu/api/weeks/school/" + SCHOOL_SLUG + "/menu-type/" + MENU_TYPE_SLUG + "/" + str(int(parts[0])) + "/" + str(int(parts[1])) + "/" + str(int(parts[2])) + "/"

def failed(key, message):
    cache.set(key, message, ttl_seconds = 900)
    return {"error": message}

def fetch_week(monday):
    key = "medway-lunch-v4:" + monday
    saved = cache.get(key)
    if saved:
        return json.decode(saved)
    failure_key = "medway-lunch-error:" + monday
    previous_error = cache.get(failure_key)
    if previous_error:
        return {"error": previous_error}
    cache.set(failure_key, "Retry in 15m", ttl_seconds = 900)
    response = http.get(menu_url(monday), headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "x-nutrislice-origin": MENU_ORIGIN,
    }, ttl_seconds = 0)
    if response.status_code != 200:
        return failed(failure_key, "Menu API " + str(response.status_code))
    payload = response.json()
    if type(payload) != "dict" or type(payload.get("days")) != "list":
        return failed(failure_key, "Invalid menu data")
    menus = {}
    for day in payload["days"]:
        if type(day) != "dict" or type(day.get("menu_items")) != "list":
            continue
        date = day.get("date")
        if type(date) != "string" or not date:
            continue
        meal = ""
        next_is_american_classics_item = False
        for entry in day["menu_items"]:
            if type(entry) != "dict":
                next_is_american_classics_item = False
                continue
            if entry.get("is_station_header") == True:
                next_is_american_classics_item = (entry.get("text") or "").lower() == "american classics"
                continue
            if next_is_american_classics_item:
                next_is_american_classics_item = False
                food = entry.get("food")
                if type(food) == "dict" and type(food.get("name")) == "string" and food.get("name"):
                    meal = food["name"]
                break
        menus[date] = meal
    cache.set(key, json.encode(menus), ttl_seconds = 14400)
    cache.set(failure_key, "", ttl_seconds = 1)
    return menus

def error_screen(message):
    return render.Root(child = render.Column(children = [
        render.Text("LUNCH MENU", font = "5x8", color = "#80e5b4"),
        render.Text("CHECK WIFI", font = "5x8", color = "#ffd080"),
        render.Text(message[:12], font = "5x8", color = "#ffffff"),
        render.Text("TRY LATER", font = "5x8", color = "#82949f"),
    ]))

def menu_line(name, width):
    text = render.Text(name, font = "CG-pixel-3x5-mono", height = 6, color = "#ffffff")
    if text.size()[0] > width:
        return render.Marquee(width = width, child = text, delay = 20, offset_end = 0)
    return text

def day_row(label, meal):
    label_text = render.Text(label + ":", font = "CG-pixel-3x5-mono", height = 6, color = "#ffd080")
    meal_text = menu_line(meal or "No menu", 54)
    return render.Box(width = 64, height = 8, child = render.Row(
        children = [render.Box(width = 10, height = 8, child = label_text), meal_text],
        expanded = True,
        main_align = "start",
    ))

def menu_screen(menus, monday, weekdays):
    rows = []
    for weekday in weekdays:
        label = weekday[0]
        weekday_index = weekday[1]
        if weekday_index >= 0:
            date = add_days(monday, weekday_index)
            rows.append(day_row(label, menus.get(date, "")))
        else:
            rows.append(render.Box(width = 64, height = 8, child = render.Text("", font = "CG-pixel-3x5-mono", height = 6)))
    return render.Column(children = [
        render.Text("Lunch", font = "5x8", color = "#80e5b4"),
    ] + rows)

def main(config):
    duration = str(config.get("display_time_seconds") or "60")
    invalid_duration = not duration
    for pos in range(len(duration)):
        if duration[pos] not in "0123456789":
            invalid_duration = True
    if invalid_duration or int(duration) < 2:
        return error_screen("Bad duration")

    now = time.now().in_location(config.get("timezone") or "US/Eastern")
    today = now.format("2006-01-02")
    monday = monday_of_school_week(today, now.format("Mon"))
    menus = fetch_week(monday)
    if type(menus) == "dict" and menus.get("error"):
        return error_screen(menus["error"])

    meals = {}
    for index in range(5):
        date = add_days(monday, index)
        meals[date] = menus.get(date, "")
    first_screen = menu_screen(meals, monday, FIRST_SCREEN)
    second_screen = menu_screen(meals, monday, SECOND_SCREEN)
    total_ticks = int(duration) * 10
    first_ticks = total_ticks // 2
    second_ticks = total_ticks - first_ticks
    sequence = render.Sequence(children = [
        render.Animation(children = [first_screen] * first_ticks),
        render.Animation(children = [second_screen] * second_ticks),
    ])
    return render.Root(child = sequence, delay = 100, max_age = 180, show_full_animation = True)
