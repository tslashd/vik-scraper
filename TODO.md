# TODO — vik-scraper improvements

## Critical — Security

- [x] **SQL injection in all DB operations** — Switched to parameterized queries (`%s` placeholders) in `db.py` (`execute_query`, `move_data`) and `scraper.py` (`input_to_db`). No more f-string interpolation of user data.

## High — Bugs

- [x] **`valid_key` logic bug in `ai.py`** — Fixed. Was `or` (always `True`), now `api_key is not None and api_key != "MY_OPENAI_API_KEY"`.
- [x] **`existing_data` is a module-level global** — Removed global. Now passed as a parameter through `web_scraper()`, `article_looper()`, `input_to_db()`, and `full_export()`.
- [x] **`formatted_place.strip()` crashes when `None`** — Resolved by GPT-first extraction (always returns a string). Added fallback `if formatted_place else "N/A"` for safety.
- [x] **`scraped` may be undefined** — Fixed in CLI rewrite. `scraped` is always assigned before use.
- [x] **`date_updated` never actually updated** — Added `date_updated = NOW()` to the UPDATE query in `input_to_db()`.

## High — Replace regex extraction with GPT-first (structured output)

- [x] **Removed regex and string-split extraction entirely.** Every article now goes through GPT structured output via Pydantic `ExtractorModel`. Single extraction path, no more fragile regex for Bulgarian text.

## Medium — Modernize OpenAI SDK

- [x] **`openai` is pinned to 0.28.0** — Upgraded to v1+ SDK. Now uses `client.beta.chat.completions.parse()` with proper client instantiation.
- [x] **Use the Pydantic `ExtractorModel`** — Implemented as `response_format=ExtractorModel` for validated, typed structured outputs. No more manual JSON parsing.

## Medium — Robustness

- [x] **No request timeouts** — Added `timeout=30` to all `requests.get()` calls.
- [x] **No retry logic for HTTP requests** — Using `requests.Session()` with `urllib3.util.retry.Retry` (3 retries, exponential backoff, 500/502/503/504).
- [x] **No GPT response validation** — Wrapped in try/except for `openai.APIError` and `openai.APITimeoutError`. Returns fallback `ExtractorModel` on failure. Checks for `None` parsed response.
- [x] **No graceful DB reconnection** — Added `_reconnect()` helper in `Database` with 3 attempts and 2s delay. `execute_query()` auto-reconnects on `OperationalError`.

## Medium — Code quality

- [x] **`OpenAIExtractor()` instantiated repeatedly** — Single shared instance created once, passed to `Scraper` and used throughout.
- [x] **`memoize()` decorator defined but never used** — Removed.
- [x] **`full_export()` year list is hardcoded** — Now uses `range(2020, datetime.now().year + 1)`.
- [x] **Table name derived from model string** — Extracted as `TABLE_NAME = "vik_gpt_4o_mini"` constant in `db.py`, imported elsewhere.
- [x] **Logging via `print()`** — Replaced with Python `logging` module. Module-level loggers (`scraper`, `db`, `ai`). `--verbose` flag enables DEBUG level.

## Low — Docker / Deployment

- [x] **`.env` is COPYed into the image** — Removed `COPY .env` from Dockerfile. Use `--env-file` at runtime or `docker-compose.yml`.
- [x] **Cron doesn't pass env vars to the script** — Added `env >> /etc/environment` in CMD before cron starts.
- [x] **No health check** — Added `HEALTHCHECK` that verifies a log file was written in the last ~2 hours.
- [x] **No log rotation** — Added weekly cron job that deletes console logs older than 30 days.
- [x] **Two separate `apt-get update` calls in Dockerfile** — Merged `tzdata` and `cron` installs into a single RUN layer.

## Low — Nice to have

- [x] **Add a CLI interface** — `argparse` added with `--year`, `--pages`, `--dry-run`, and `--verbose` options.
- [x] **Add `--dry-run` mode** — Scrapes and extracts without DB connection. Useful for testing GPT prompt changes.
- [x] **Track GPT cost per run** — `OpenAIExtractor` tracks `total_prompt_tokens` and `total_completion_tokens` across all calls. `log_usage_summary()` prints totals at end of run.
- [x] **Add a `docker-compose.yml`** — Created with `env_file: .env` and `./logs` volume mount.
