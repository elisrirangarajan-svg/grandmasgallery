# Grandma's Happy Corner

## Testing switch

Open `config.py`.

```python
TEST_MODE = True
```

With `True`, the once-per-day restriction is disabled so you can test all four
choices. Before giving the website to Grandma, change it to:

```python
TEST_MODE = False
```

Restart Flask after changing the setting.

## Google Drive memories

The Apps Script web-app URL is already configured:

`https://script.google.com/macros/s/AKfycbxWz0cGA09tC8saNbqr9WeL7ICSdSuafFWLCoHt6E4L7xMZ-pRwZYhOnTsiTLKMDiFVng/exec`

The Drive folder ID is:

`1Bqmt9lUV_gCC0tNsXPGPkE9HgyGFF5y2`

New image files added to that folder are picked up automatically.

## Daily behavior

When `TEST_MODE = False`, Grandma may choose only one of the four categories per
calendar day on that browser. The selected category can be reopened that day,
but the other three remain locked until tomorrow. The exact item selected that
day is remembered, so refreshing does not generate a different one.

Jokes, compliments, quotes, and photos do not repeat until their respective
collections have been exhausted; then a new cycle begins.


## Adding jokes, compliments, and quotes

All editable content is now in the `data` folder:

```text
data/
├── jokes.json
├── compliments.json
└── quotes.json
```

### Add a joke

Open `data/jokes.json`. Add a comma after the previous joke, then add:

```json
{
  "setup": "Your joke setup",
  "punchline": "Your punchline"
}
```

### Add a compliment

Open `data/compliments.json`. Add a comma after the previous compliment, then add:

```json
"You make every day a little brighter."
```

### Add a quote

Open `data/quotes.json`. Add a comma after the previous quote, then add:

```json
{
  "quote": "Your inspirational quote",
  "author": "Author name"
}
```

Restart Flask after editing the JSON files.

Important JSON rules:

- Put commas between entries, but not after the final entry.
- Use double quotation marks.
- Keep the opening `[` and closing `]`.
- Save the files as UTF-8.

The app checks these files at startup and reports the exact line number if the JSON is invalid.


## Server-side daily lock

The daily choice and no-repeat decks are now stored in the `state` folder:

```text
state/
├── daily_state.json
├── jokes_state.json
├── compliments_state.json
├── quotes_state.json
└── memories_state.json
```

Refreshing the page, clearing browser storage, or opening another browser will
not create a new daily result while the same Flask server and project folder are
being used.

To reset everything during development, stop Flask and replace the contents of
`state/daily_state.json` with:

```json
{
  "date": "",
  "choice": "",
  "result": null
}
```

You can also delete the files in `state`; the app recreates them automatically.

`TEST_MODE = True` still disables the daily lock while testing. Set it to
`False` before normal use.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Open `http://127.0.0.1:5000`.
