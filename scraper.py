#!/usr/bin/env python3
"""
VIK Water Outage Scraper
Fetches outage announcements from vikpz.com via the WordPress REST API,
extracts structured data (location, time period) using GPT-4o-mini,
and stores results in MySQL.

Reads DB credentials and OpenAI key from .env

Usage:
    python scraper.py                                # scrape current year, 2 pages
    python scraper.py --dry-run                      # scrape without DB writes
    python scraper.py --year 2025                    # scrape a specific year
    python scraper.py --year 2020 2021 2022 --pages 0  # full export, all pages
    python scraper.py --dry-run --verbose            # debug output, no DB
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from time import perf_counter

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ai import OpenAIExtractor
from db import Database, TABLE_NAME


API_BASE = "https://vikpz.com/wp-json/wp/v2"
CATEGORY_AVARII = 7  # "Аварии" category ID
PER_PAGE = 50  # max 100 per WP REST API

logs_path: str = os.path.dirname(__file__)
logger = logging.getLogger("scraper")

REQUEST_TIMEOUT = 30


def _create_http_session() -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _strip_html(html: str) -> str:
    """Strip HTML tags and return clean text."""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ").strip()


def _fetch_authors(session: requests.Session) -> dict:
    """Fetch author ID-to-name mapping from WP API."""
    try:
        resp = session.get(f"{API_BASE}/users", timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return {u["id"]: u["name"] for u in resp.json()}
    except requests.RequestException as err:
        logger.warning("Could not fetch authors: %s", err)
        return {}


class Scraper:
    def __init__(self, year: int, pages: int, gpt: OpenAIExtractor):
        self.year = year
        self.pages = pages
        self.gpt = gpt
        self.session = _create_http_session()
        self.authors = _fetch_authors(self.session)
        self.scraped_data: dict = {}
        self.total_pages: int = 0

    def scrape(self, existing_data: dict) -> dict:
        """Fetch posts from WP REST API and extract structured data via GPT."""
        start = perf_counter()
        page = 1

        # Date range for the requested year
        after = f"{self.year}-01-01T00:00:00"
        before = f"{self.year}-12-31T23:59:59"

        while True:
            params = {
                "categories": CATEGORY_AVARII,
                "per_page": PER_PAGE,
                "page": page,
                "after": after,
                "before": before,
                "orderby": "date",
                "order": "desc",
            }

            try:
                resp = self.session.get(
                    f"{API_BASE}/posts", params=params, timeout=REQUEST_TIMEOUT
                )
                resp.raise_for_status()
            except requests.RequestException as err:
                logger.error("API request failed (page %d): %s", page, err)
                break

            posts = resp.json()
            if not posts:
                break

            # Read total pages from headers on first request
            if page == 1:
                self.total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                total_posts = int(resp.headers.get("X-WP-Total", 0))
                logger.info(
                    "Year %d: %d posts across %d pages",
                    self.year,
                    total_posts,
                    self.total_pages,
                )

            logger.info("Processing page %d/%d (%d posts)", page, self.total_pages, len(posts))

            for post in posts:
                self._process_post(post, existing_data)

            # Stop if we've hit the page limit or the last page
            if (self.pages > 0 and page >= self.pages) or page >= self.total_pages:
                break

            page += 1

        elapsed = perf_counter() - start
        logger.info(
            "Scraped %d entries from %d for year %d in %.2f seconds",
            len(self.scraped_data),
            page,
            self.year,
            elapsed,
        )

        if self.scraped_data:
            self._dump_to_file(
                self.scraped_data,
                f"{logs_path}/logs/data/scraped_data_{self.year}_full.json",
            )

        return self.scraped_data

    def _process_post(self, post: dict, existing_data: dict):
        """Process a single WP post into structured scraped data."""
        post_id = f"post-{post['id']}"
        summary = _strip_html(post["content"]["rendered"])

        # Skip if article already exists with same summary
        if isinstance(existing_data, dict) and existing_data.get(post_id):
            if existing_data[post_id]["summary"] == summary:
                logger.debug("%s already exists with same summary", post_id)
                return
            else:
                update_entry = True
                logger.info("%s needs to be updated in DB", post_id)
        else:
            update_entry = False

        # Parse fields directly from API response
        article_date = datetime.fromisoformat(post["date"])
        title = _strip_html(post["title"]["rendered"])
        author = self.authors.get(post["author"], "N/A")
        comments = str(post.get("uagb_comment_info", 0))
        category = "Аварии"  # We filter by this category

        formatted_date = article_date.strftime("%d.%m.%Y")

        # GPT extraction for place/period
        formatted_place = "N/A"
        formatted_period = "N/A"
        gpt_response = None

        if self.gpt.valid_key:
            gpt_response = self.gpt.extract_data(summary, formatted_date)
            formatted_place = (
                ", ".join(gpt_response.places) if gpt_response.places else "N/A"
            )
            formatted_period = gpt_response.period

            self._dump_to_file(
                gpt_response.model_dump(),
                f"{logs_path}/logs/gpt/{post_id}_{self.gpt.model}.json",
            )
            logger.debug("GPT: place=%s, period=%s", formatted_place, formatted_period)
        else:
            logger.warning("No valid OpenAI key — place and period set to N/A")

        self.scraped_data[post_id] = {
            "day": str(article_date.day),
            "month_year": article_date.strftime("%m %Y"),
            "date": formatted_date,
            "place": formatted_place.strip() if formatted_place else "N/A",
            "period": formatted_period.strip() if formatted_period else "N/A",
            "author": author,
            "title": title,
            "category": category,
            "summary": summary,
            "current_page": 1,
            "total_pages": self.total_pages,
            "comments": comments,
            "ai_extract": True,
            "gpt_data": gpt_response.model_dump() if gpt_response else None,
            "update_entry": update_entry,
        }

    def _dump_to_file(self, new_dump: dict, file_name: str):
        """Appends data to a JSON or creates a new one."""
        logger.debug("Dumping %d entries to %s", len(new_dump), file_name)

        if file_name.endswith(".json"):
            if os.path.exists(file_name):
                with open(file_name, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = {}
            else:
                data = {}

            data.update(new_dump)

            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        else:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(str(new_dump))


def input_to_db(data: dict, existing_data: dict):
    db = Database()

    db_start = perf_counter()
    for key, item in data.items():
        article_date = datetime.strptime(item["date"], "%d.%m.%Y").strftime("%Y-%m-%d")

        insert_query = f"""
        INSERT IGNORE INTO {TABLE_NAME}
        (`post_id`, `title`, `location`, `period`, `author`, `summary`,
         `category`, `ai_extract`, `page`, `total_pages`, `comments`, `article_date`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        insert_params = (
            key,
            item["title"],
            item["place"],
            item["period"],
            item["author"],
            item["summary"],
            item["category"],
            1 if item["ai_extract"] else 0,
            item["current_page"],
            item["total_pages"],
            item["comments"],
            article_date,
        )

        update_query = f"""
        UPDATE {TABLE_NAME}
        SET `title` = %s, `location` = %s, `period` = %s, `author` = %s,
            `summary` = %s, `category` = %s, `ai_extract` = %s, `page` = %s,
            `total_pages` = %s, `comments` = %s, `article_date` = %s,
            `date_updated` = NOW()
        WHERE `post_id` = %s
        """
        update_params = (
            item["title"],
            item["place"],
            item["period"],
            item["author"],
            item["summary"],
            item["category"],
            1 if item["ai_extract"] else 0,
            item["current_page"],
            item["total_pages"],
            item["comments"],
            article_date,
            key,
        )

        if item["update_entry"]:
            moved = db.move_data(key, existing_data.get(key))
            if not moved:
                logger.error("Could not move entry %s to edited table", key)
            else:
                logger.info("Moved entry %s to edited table", key)

            execution = db.execute_query(update_query, update_params)
        else:
            execution = db.execute_query(insert_query, insert_params)

        if not execution:
            logger.error("Could NOT add '%s'", key)

    db.close_connection()
    db_end = perf_counter()
    logger.info("Finished %d DB entries in %.2f seconds", len(data), db_end - db_start)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape VIK Pazardzhik water outage announcements via WP REST API"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scrape and run GPT extraction without touching the database",
    )
    parser.add_argument(
        "--year", type=int, nargs="+", metavar="YEAR",
        default=[datetime.now().year],
        help="Year(s) to scrape (e.g. --year 2024 2025). Defaults to current year.",
    )
    parser.add_argument(
        "--pages", type=int, default=2, metavar="N",
        help="Max API pages per year (50 posts/page). 0 = all pages. Default: 2",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show DEBUG-level logs (per-article GPT results, file dumps, etc.)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stdout,
    )

    start_total = perf_counter()

    gpt = OpenAIExtractor()
    existing_data: dict = {}

    # Load existing DB entries for duplicate detection (skip in dry-run)
    if not args.dry_run:
        db = Database()
        for year in args.year:
            get_query = f"SELECT * FROM {TABLE_NAME} WHERE `article_date` LIKE %s"
            loaded = db.get_data(get_query, (f"{year}%",))
            if loaded:
                existing_data.update(loaded)
        db.close_connection()

        if existing_data:
            logger.info("%d entries loaded", len(existing_data))
    else:
        logger.info("Dry run enabled — DB writes will be skipped")

    # Scrape each requested year
    for year in args.year:
        logger.info(
            "Scraping year %d (pages: %s)",
            year,
            "all" if args.pages <= 0 else args.pages,
        )
        scraper = Scraper(year=year, pages=args.pages, gpt=gpt)
        scraped = scraper.scrape(existing_data)

        if scraped and not args.dry_run:
            input_to_db(scraped, existing_data)
        elif args.dry_run and scraped:
            logger.info("Dry run — skipped DB insert for %d entries", len(scraped))

    gpt.log_usage_summary()
    end_total = perf_counter()
    logger.info("Finished in %.2f seconds", end_total - start_total)
