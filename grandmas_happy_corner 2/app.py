from flask import Flask, render_template, jsonify, request
from pathlib import Path
from datetime import date
import json
import random
import requests

app = Flask(__name__)

try:
    from config import MEMORY_FEED_URL, TEST_MODE
except ImportError:
    MEMORY_FEED_URL = ""
    TEST_MODE = False

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_DIR = BASE_DIR / "state"


def read_json(path, default=None):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        if default is not None:
            write_json(path, default)
            return default
        raise
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Invalid JSON in {path.name}, line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temp_path.replace(path)


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


def today_string():
    return date.today().isoformat()


def daily_state_path():
    return STATE_DIR / "daily_state.json"


def get_daily_state():
    state = read_json(
        daily_state_path(),
        {"date": "", "choice": "", "result": None},
    )

    if TEST_MODE:
        return {"date": today_string(), "choice": "", "result": None}

    if state.get("date") != today_string():
        state = {"date": today_string(), "choice": "", "result": None}
        write_json(daily_state_path(), state)

    return state


def save_daily_state(state):
    if not TEST_MODE:
        write_json(daily_state_path(), state)


def draw_from_deck(category, items):
    state_path = STATE_DIR / f"{category}_state.json"
    state = read_json(state_path, {"remaining": [], "last_count": 0})

    valid_ids = list(range(len(items)))
    remaining = [
        item_id for item_id in state.get("remaining", [])
        if isinstance(item_id, int) and 0 <= item_id < len(items)
    ]

    # Rebuild the deck when the collection changed or the deck is empty.
    if state.get("last_count") != len(items) or not remaining:
        remaining = valid_ids[:]
        random.shuffle(remaining)

    item_id = remaining.pop()
    write_json(
        state_path,
        {"remaining": remaining, "last_count": len(items)},
    )
    return item_id


def fetch_memories():
    if not MEMORY_FEED_URL:
        raise RuntimeError("MEMORY_FEED_URL has not been configured.")

    response = requests.get(MEMORY_FEED_URL, timeout=20)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict) and not payload.get("ok", True):
        raise RuntimeError(payload.get("error", "The Google Drive feed returned an error."))

    items = payload if isinstance(payload, list) else payload.get("memories", [])
    valid = []

    for item in items:
        if isinstance(item, dict) and item.get("url"):
            valid.append({
                "id": str(item.get("id") or item["url"]),
                "name": str(item.get("name") or "Family memory"),
                "url": str(item["url"]),
            })

    return valid


def draw_memory(memories):
    state_path = STATE_DIR / "memories_state.json"
    state = read_json(state_path, {"remaining": [], "last_ids": []})

    current_ids = [memory["id"] for memory in memories]
    remaining = [
        memory_id for memory_id in state.get("remaining", [])
        if memory_id in current_ids
    ]

    if state.get("last_ids") != current_ids or not remaining:
        remaining = current_ids[:]
        random.shuffle(remaining)

    chosen_id = remaining.pop()
    write_json(
        state_path,
        {"remaining": remaining, "last_ids": current_ids},
    )

    return next(memory for memory in memories if memory["id"] == chosen_id)


@app.route("/")
def home():
    return render_template("index.html", test_mode=TEST_MODE)


@app.route("/api/status")
def status():
    state = get_daily_state()
    return jsonify({
        "test_mode": TEST_MODE,
        "date": state["date"],
        "choice": state.get("choice", ""),
        "result": state.get("result"),
    })


@app.route("/api/choose", methods=["POST"])
def choose():
    payload = request.get_json(silent=True) or {}
    choice = payload.get("choice")

    valid_choices = {"joke", "compliment", "memory", "quote"}
    if choice not in valid_choices:
        return jsonify({"error": "Invalid choice."}), 400

    state = get_daily_state()

    if not TEST_MODE and state.get("choice") and state["choice"] != choice:
        return jsonify({
            "error": "A different choice has already been used today.",
            "choice": state["choice"],
            "result": state.get("result"),
        }), 409

    if state.get("choice") == choice and state.get("result") is not None:
        return jsonify({
            "choice": choice,
            "result": state["result"],
            "existing": True,
        })

    jokes, compliments, quotes = load_content()

    if choice == "joke":
        item_id = draw_from_deck("jokes", jokes)
        result = {"id": item_id, **jokes[item_id]}
    elif choice == "compliment":
        item_id = draw_from_deck("compliments", compliments)
        result = {"id": item_id, "text": compliments[item_id]}
    elif choice == "quote":
        item_id = draw_from_deck("quotes", quotes)
        result = {"id": item_id, **quotes[item_id]}
    else:
        try:
            memories = fetch_memories()
        except (requests.RequestException, ValueError, RuntimeError) as error:
            return jsonify({"error": str(error)}), 502

        if not memories:
            return jsonify({"error": "No images were found in the Google Drive folder."}), 404

        result = draw_memory(memories)

    state = {
        "date": today_string(),
        "choice": choice,
        "result": result,
    }
    save_daily_state(state)

    return jsonify({
        "choice": choice,
        "result": result,
        "existing": False,
    })


@app.route("/api/counts")
def counts():
    jokes, compliments, quotes = load_content()
    return jsonify({
        "jokes": len(jokes),
        "compliments": len(compliments),
        "quotes": len(quotes),
    })


if __name__ == "__main__":
    load_content()
    get_daily_state()
    app.run(debug=True)
