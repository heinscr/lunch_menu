"""Exercise the native app's Python-compatible logic with mocked Pixlet modules."""
import builtins
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


class Cache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ttl_seconds=60):
        self.values[key] = value


class Response:
    def __init__(self, data=None, status_code=200):
        self.status_code = status_code
        self.data = data

    def json(self):
        return self.data


class HTTP:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.data, self.status_code)


class Text:
    def __init__(self, text, **kwargs):
        self.text = text
        self.kwargs = kwargs

    def size(self):
        return (len(self.text) * 4, 6)


class Clock:
    def __init__(self, weekday, date):
        self.weekday = weekday
        self.date = date

    def in_location(self, timezone):
        return self

    def format(self, layout):
        return self.weekday if layout == "Mon" else self.date


def day(date, *names):
    items = [
        {"is_station_header": True, "text": "American Classics", "food": None},
    ]
    for name in names:
        if name:
            items.append({"food": {"name": name}})
    items.extend([
        {"is_station_header": True, "text": "2Mato", "food": None},
        {"food": {"name": "Classic Cheese Pizza"}},
    ])
    return {
        "date": date,
        "menu_items": items,
    }


def sample_week():
    return {
        "days": [
            day("2026-10-25", "Sunday Breakfast"),
            day("2026-10-26", "Beef Hot Dog", "Classic Cheese Pizza", None),
            day("2026-10-27", "Chicken Bowl"),
            day("2026-10-28", "Chicken Parmesan"),
            day("2026-10-29", "Philly Cheese Steak"),
            day("2026-10-30", "Chicken & Mozzarella Sticks"),
            day("2026-10-31", "Saturday Snack"),
        ],
    }


def load_app(data=None, status_code=200, weekday="Mon", date="2026-10-26"):
    http = HTTP(data if data is not None else sample_week(), status_code)
    cache = Cache()
    render = SimpleNamespace(
        Text=lambda text, **kwargs: Text(text, **kwargs),
        Marquee=lambda **kwargs: kwargs,
        Box=lambda **kwargs: kwargs,
        Row=lambda **kwargs: kwargs,
        Column=lambda **kwargs: kwargs,
        Animation=lambda **kwargs: kwargs,
        Sequence=lambda **kwargs: kwargs,
        Root=lambda **kwargs: kwargs,
    )

    def starlark_type(value):
        name = builtins.type(value).__name__
        return "string" if name == "str" else name

    env = {
        "http": http,
        "cache": cache,
        "json": SimpleNamespace(encode=json.dumps, decode=json.loads),
        "time": SimpleNamespace(now=lambda: Clock(weekday, date)),
        "render": render,
        "type": starlark_type,
    }
    source = Path("tronbyt") / "lunch_schedule.star"
    lines = source.read_text(encoding="utf-8").splitlines()
    source_text = "\n".join(line for line in lines if not line.startswith("load("))
    exec(compile(source_text, str(source), "exec"), env)
    return env, http


class NativeLunchTests(unittest.TestCase):
    def test_fetches_real_week_endpoint_and_reduces_food_items(self):
        env, http = load_app()
        result = env["fetch_week"]("2026-10-26")
        self.assertEqual(
            http.calls[0][0],
            "https://medwayschools.api.nutrislice.com/menu/api/weeks/"
            "school/medway-middle-school/menu-type/lunch/2026/10/26/",
        )
        self.assertEqual(
            http.calls[0][1]["headers"]["x-nutrislice-origin"],
            "https://medwayschools.nutrislice.com",
        )
        self.assertEqual(result["2026-10-26"], "Beef Hot Dog")
        self.assertEqual(result["2026-10-27"], "Chicken Bowl")
        self.assertNotIn("Classic Cheese Pizza", result.values())
        self.assertEqual(env["fetch_week"]("2026-10-26"), result)
        self.assertEqual(len(http.calls), 1)

    def test_ignores_cached_full_menus_from_previous_app_version(self):
        env, http = load_app()
        env["cache"].set(
            "medway-lunch-v3:2026-10-26",
            json.dumps({"2026-10-26": "Beef Hot Dog"}),
        )
        result = env["fetch_week"]("2026-10-26")
        self.assertEqual(result["2026-10-26"], "Beef Hot Dog")
        self.assertEqual(len(http.calls), 1)

    def test_cached_week_contains_thursday_and_friday_featured_items(self):
        env, _ = load_app()
        meals = env["fetch_week"]("2026-10-26")
        self.assertEqual(meals["2026-10-29"], "Philly Cheese Steak")
        self.assertEqual(meals["2026-10-30"], "Chicken & Mozzarella Sticks")
        self.assertEqual(
            json.loads(env["cache"].get("medway-lunch-v4:2026-10-26")),
            meals,
        )

    def test_only_uses_the_item_immediately_after_american_classics(self):
        env, _ = load_app()
        result = env["fetch_week"]("2026-10-26")
        self.assertEqual(result["2026-10-26"], "Beef Hot Dog")

        env, _ = load_app(data={
            "days": [{
                "date": "2026-10-26",
                "menu_items": [
                    {"is_station_header": True, "text": "American Classics"},
                    {"text": "Menu item unavailable", "food": None},
                    {"food": {"name": "This is not the item directly below"}},
                ],
            }],
        })
        result = env["fetch_week"]("2026-10-26")
        self.assertEqual(result["2026-10-26"], "")

    def test_week_summary_shows_only_top_american_classics_item(self):
        env, _ = load_app()
        rows = []
        env["day_row"] = lambda label, meal: rows.append((label, meal)) or (label, meal)
        result = env["main"]({"timezone": "US/Eastern", "display_time_seconds": "60"})
        self.assertEqual(
            rows,
            [
                ("M", "Beef Hot Dog"),
                ("T", "Chicken Bowl"),
                ("W", "Chicken Parmesan"),
                ("Th", "Philly Cheese Steak"),
                ("Fr", "Chicken & Mozzarella Sticks"),
            ],
        )
        pages = result["child"]["children"]
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages[0]["children"]), 300)
        self.assertEqual(len(pages[1]["children"]), 300)
        self.assertEqual(pages[0]["children"][0]["children"][0].text, "Lunch")
        self.assertEqual(pages[1]["children"][0]["children"][0].text, "Lunch")
        self.assertNotEqual(pages[0]["children"][0], pages[1]["children"][0])
        self.assertEqual(result["delay"], 100)
        self.assertTrue(result["show_full_animation"])

    def test_screens_use_full_width_rows_in_requested_groups(self):
        env, _ = load_app()
        rows = []
        env["day_row"] = lambda label, meal: rows.append((label, meal)) or ("row", label, meal)
        first = env["menu_screen"](
            {date: date for date in ("2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30")},
            "2026-10-26",
            env["FIRST_SCREEN"],
        )
        self.assertEqual(rows, [("M", "2026-10-26"), ("T", "2026-10-27"), ("W", "2026-10-28")])
        self.assertEqual(len(first["children"]), 4)
        rows.clear()
        second = env["menu_screen"](
            {date: date for date in ("2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30")},
            "2026-10-26",
            env["SECOND_SCREEN"],
        )
        self.assertEqual(
            rows,
            [("Th", "2026-10-29"), ("Fr", "2026-10-30")],
        )
        self.assertEqual(len(second["children"]), 4)

    def test_each_meal_row_uses_entire_display_width(self):
        env, _ = load_app()
        row = env["day_row"]("M", "Beef Hot Dog")
        self.assertEqual(row["width"], 64)
        label, meal = row["child"]["children"]
        self.assertEqual(label["width"], 10)
        self.assertEqual(meal.text, "Beef Hot Dog")
        self.assertGreater(meal.size()[0], 0)

    def test_long_meal_marquee_returns_to_visible_start(self):
        env, _ = load_app()
        marquee = env["menu_line"]("A meal name long enough to scroll across the display", 54)
        self.assertEqual(marquee["offset_end"], 0)
        self.assertEqual(marquee["delay"], 20)

    def test_weekend_uses_upcoming_monday(self):
        for weekday, date in (("Sat", "2026-10-24"), ("Sun", "2026-10-25")):
            with self.subTest(weekday=weekday):
                env, http = load_app(weekday=weekday, date=date)
                env["main"]({"timezone": "US/Eastern", "display_time_seconds": "60"})
                self.assertIn("/2026/10/26/", http.calls[0][0])

    def test_invalid_display_duration_is_reported(self):
        env, http = load_app()
        result = env["main"]({"display_time_seconds": "1"})
        self.assertEqual(http.calls, [])
        self.assertEqual(result["child"]["children"][2].text, "Bad duration")

    def test_monday_calculation_handles_month_and_leap_year_boundaries(self):
        env, _ = load_app()
        self.assertEqual(env["add_days"]("2026-12-31", 1), "2027-01-01")
        self.assertEqual(env["add_days"]("2028-02-28", 1), "2028-02-29")
        self.assertEqual(env["add_days"]("2027-02-28", 1), "2027-03-01")

    def test_api_failure_is_visible_and_throttled(self):
        env, http = load_app(status_code=503)
        first = env["fetch_week"]("2026-10-26")
        second = env["fetch_week"]("2026-10-26")
        self.assertEqual(first, {"error": "Menu API 503"})
        self.assertEqual(second, first)
        self.assertEqual(len(http.calls), 1)


if __name__ == "__main__":
    unittest.main()
