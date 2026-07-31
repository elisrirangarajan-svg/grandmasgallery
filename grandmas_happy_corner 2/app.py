from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

try:
    import config
    MEMORY_FEED_URL = getattr(config, "MEMORY_FEED_URL", "")
    STATE_API_URL = getattr(config, "STATE_API_URL", "")
    STATE_API_SECRET = getattr(config, "STATE_API_SECRET", "")
    TEST_MODE = getattr(config, "TEST_MODE", False)
    TIMEZONE = getattr(config, "TIMEZONE", "UTC")
except ImportError:
    MEMORY_FEED_URL = ""
    STATE_API_URL = ""
    STATE_API_SECRET = ""
    TEST_MODE = False
    TIMEZONE = "UTC"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as error:
        raise RuntimeError(f"Missing required file: {path}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Invalid JSON in {path.name}, line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error


def load_content():
    jokes = read_json(DATA_DIR / "jokes.json")
    compliments = read_json(DATA_DIR / "compliments.json")
    quotes = read_json(DATA_DIR / "quotes.json")

    if not isinstance(jokes, list):
        raise RuntimeError("jokes.json must contain a JSON list.")
    if not isinstance(compliments, list):
        raise RuntimeError("compliments.json must contain a JSON list.")
    if not isinstance(quotes, list):
        raise RuntimeError("quotes.json must contain a JSON list.")

    for index, joke in enumerate(jokes):
        if not isinstance(joke, dict) or not joke.get("setup") or not joke.get("punchline"):
            raise RuntimeError(
                f"jokes.json item {index + 1} must contain setup and punchline."
            )

    for index, compliment in enumerate(compliments):
        if not isinstance(compliment, str) or not compliment.strip():
            raise RuntimeError(
                f"compliments.json item {index + 1} must be a non-empty string."
            )

    for index, quote in enumerate(quotes):
        if not isinstance(quote, dict) or not quote.get("quote") or not quote.get("author"):
            raise RuntimeError(
                f"quotes.json item {index + 1} must contain quote and author."
            )

    return jokes, compliments, quotes


def current_date():
    try:
        timezone = ZoneInfo(TIMEZONE)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("UTC")
    return datetime.now(timezone).date()


def today_string():
    return current_date().isoformat()


def call_state_api(action: str, **extra):
    if not STATE_API_URL:
        raise RuntimeError("STATE_API_URL has not been configured.")
    if not STATE_API_SECRET:
        raise RuntimeError("STATE_API_SECRET has not been configured.")

    payload = {
        "secret": STATE_API_SECRET,
        "action": action,
        **extra,
    }

    response = requests.post(
        STATE_API_URL,
        json=payload,
        timeout=25,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError(
            "The Google Apps Script state service returned invalid JSON."
        ) from error

    if not isinstance(data, dict) or not data.get("ok"):
        message = (
            data.get("error", "The state service failed.")
            if isinstance(data, dict)
            else "The state service returned an invalid response."
        )
        raise RuntimeError(message)

    return data


def get_daily_state():
    if TEST_MODE:
        return {
            "date": today_string(),
            "choice": "",
            "result": None,
        }

    return call_state_api(
        "status",
        date=today_string(),
    )


def reserve_daily_choice(category: str, item_count: int):
    if TEST_MODE:
        return {
            "existing": False,
            "date": today_string(),
            "choice": category,
            "item_index": 0,
        }

    return call_state_api(
        "choose",
        date=today_string(),
        category=category,
        item_count=item_count,
    )


def save_remote_result(category: str, result):
    if TEST_MODE:
        return

    call_state_api(
        "save_result",
        date=today_string(),
        category=category,
        result=result,
    )


def fetch_memories():
    if not MEMORY_FEED_URL:
        raise RuntimeError("MEMORY_FEED_URL has not been configured.")

    response = requests.get(MEMORY_FEED_URL, timeout=25)
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as error:
        raise RuntimeError(
            "The Google Drive memory feed returned invalid JSON."
        ) from error

    if isinstance(payload, dict) and not payload.get("ok", True):
        raise RuntimeError(
            payload.get("error", "The Google Drive feed returned an error.")
        )

    items = payload if isinstance(payload, list) else payload.get("memories", [])
    memories = []

    for item in items:
        if not isinstance(item, dict) or not item.get("url"):
            continue

        memories.append(
            {
                "id": str(item.get("id") or item["url"]),
                "name": str(item.get("name") or "Family memory"),
                "url": str(item["url"]),
            }
        )

    memories.sort(key=lambda memory: memory["id"])
    return memories


@app.route("/")
def home():
    return render_template("index.html", test_mode=TEST_MODE)


@app.route("/api/status")
def status():
    try:
        state = get_daily_state()
    except (requests.RequestException, RuntimeError) as error:
        return jsonify({"error": str(error)}), 502

    return jsonify(
        {
            "test_mode": TEST_MODE,
            "date": state.get("date", ""),
            "choice": state.get("choice", ""),
            "result": state.get("result"),
        }
    )


@app.route("/api/choose", methods=["POST"])
def choose():
    payload = request.get_json(silent=True) or {}
    choice = payload.get("choice")

    valid_choices = {"joke", "compliment", "memory", "quote"}
    if choice not in valid_choices:
        return jsonify({"error": "Invalid choice."}), 400

    try:
        jokes, compliments, quotes = load_content()

        if choice == "joke":
            items = jokes
        elif choice == "compliment":
            items = compliments
        elif choice == "quote":
            items = quotes
        else:
            items = fetch_memories()
            if not items:
                return jsonify(
                    {"error": "No images were found in the Google Drive folder."}
                ), 404

        reservation = reserve_daily_choice(
            category=choice,
            item_count=len(items),
        )

    except requests.RequestException as error:
        return jsonify(
            {"error": f"Could not contact Google services: {error}"}
        ), 502
    except (ValueError, RuntimeError) as error:
        return jsonify({"error": str(error)}), 502

    if reservation.get("existing"):
        saved_choice = reservation.get("choice", "")
        saved_result = reservation.get("result")

        if saved_choice != choice:
            return jsonify(
                {
                    "error": "A different choice has already been used today.",
                    "choice": saved_choice,
                    "result": saved_result,
                }
            ), 409

        if saved_result is not None:
            return jsonify(
                {
                    "choice": saved_choice,
                    "result": saved_result,
                    "existing": True,
                }
            )

        return jsonify(
            {
                "error": (
                    "Today's choice was reserved but its result has not "
                    "finished saving. Please try again."
                )
            }
        ), 409

    item_index = reservation.get("item_index")

    if not isinstance(item_index, int):
        return jsonify(
            {"error": "The state service returned an invalid item index."}
        ), 502

    if item_index < 0 or item_index >= len(items):
        return jsonify(
            {"error": "The saved item index is outside the available collection."}
        ), 502

    if choice == "joke":
        result = {"id": item_index, **jokes[item_index]}
    elif choice == "compliment":
        result = {"id": item_index, "text": compliments[item_index]}
    elif choice == "quote":
        result = {"id": item_index, **quotes[item_index]}
    else:
        result = items[item_index]

    try:
        save_remote_result(choice, result)
    except (requests.RequestException, RuntimeError) as error:
        return jsonify(
            {
                "error": (
                    "The item was selected but could not be saved: "
                    f"{error}"
                )
            }
        ), 502

    return jsonify(
        {
            "choice": choice,
            "result": result,
            "existing": False,
        }
    )


@app.route("/api/counts")
def counts():
    try:
        jokes, compliments, quotes = load_content()
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500

    return jsonify(
        {
            "jokes": len(jokes),
            "compliments": len(compliments),
            "quotes": len(quotes),
        }
    )


if __name__ == "__main__":
    load_content()
    app.run(debug=True)

