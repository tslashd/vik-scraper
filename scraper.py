import json, re, requests, os, sys
from datetime import datetime
from functools import wraps
from time import perf_counter
from bs4 import BeautifulSoup
from db import Database
from ai import OpenAIExtractor


# Mapping of Bulgarian month abbreviations to their numerical equivalents
bulgarian_months = {
    "ян.": "01",
    "февр.": "02",
    "мар.": "03",
    "апр.": "04",
    "май": "05",
    "юни": "06",
    "юли": "07",
    "авг.": "08",
    "сеп.": "09",
    "окт.": "10",
    "ное.": "11",
    "дек.": "12",
}

existing_data: dict = {}
logs_path: str = os.path.dirname(__file__)


# Want to test some stuff with this
def memoize(func):
    cache = {}

    @wraps(func)
    def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)

        if key not in cache:
            cache[key] = func(*args, **kwargs)

        return cache[key]

    return wrapper


def full_export():
    """Full scrapes 2020 to 2024. Prints redirected to an output file"""
    start_total = perf_counter()

    years = [2020, 2021, 2022, 2023, 2024]
    # years = [2020]

    for year in years:
        year_start = perf_counter()
        # Remove the file if it already exists
        if os.path.exists(f"{logs_path}/logs/console/output_{year}.txt"):
            os.remove(f"{logs_path}/logs/console/output_{year}.txt")

        # Redirect stdout to a file
        with open(
            f"{logs_path}/logs/console/output_{year}.txt", "w", encoding="utf-8"
        ) as file:
            sys.stdout = file

            # Initiate to get the model name which is used for table names
            gpt = OpenAIExtractor()

            # Load the data we will use for checking existing entries
            db = Database()
            get_query = f"SELECT * FROM vik_{gpt.model.replace('-', '_')};"
            existing_data = db.get_data(get_query)

            db.close_connection()

            if existing_data is not False:
                print(f"[Main] {len(existing_data)} entries loaded")

            # Start the scraping process
            x = Scraper(year=year, pages=0)

            if x.total_pages > 0:
                scraped = x.web_scraper()
            else:
                print(f"[Main] Got no pages")

            input_to_db(scraped)

            year_end = perf_counter()
            print(
                f"[Main] Finished the process for {year} in {year_end - year_start} seconds"
            )

            # Restore stdout to default (console)
            sys.stdout = sys.__stdout__

    end_total = perf_counter()
    print(f"[Main] Finished the full export in {end_total - start_total} seconds")


class Scraper:
    def __init__(self, year: int, pages: int):
        """Sending 0 or less as `pages` will scrape the whole year provided"""
        self.url: str = f"https://vikpz.com/{year}/"
        self.url_articles: str = f"https://vikpz.com/{year}/page/"
        self.year: int = year
        self.place_pattern = r"(гр\.|с\.|град |село |с . )\s?(.*?)(?= в |,| на | до | за | от |\W |$)"  # RegEx for getting the town/village of the accident
        self.period_pattern_check = r"""(\d*:\d* - \d*:\d*)"""

        # Pages Init
        self.current_page: int = 1
        self.total_pages: int = (
            pages  # Assign the passed pages variable - use 0 to get all pages
        )

        # Scraped Data Init
        self.scraped_data: dict = {}

        # Start the scraping by getting all the pages for the year that has been passed
        if pages <= 0:
            self.get_pages()

    def get_pages(self) -> dict:
        # Load the page
        response = requests.get(self.url)
        if response.status_code == 200:
            # Parse the HTML content
            soup = BeautifulSoup(response.content, "html.parser")

            # Get navigation links data (next page)
            nav_links = soup.find(class_="nav-links")

            if nav_links:
                # Extract the current page number
                self.current_page = int(
                    nav_links.find("span", class_="page-numbers current").text.strip()
                    if nav_links.find("span", class_="page-numbers current")
                    else -1
                )

                # Extract the href for the next page link
                next_page_link: str = (
                    nav_links.find("a", class_="next page-numbers")["href"]
                    if nav_links.find("a", class_="next page-numbers")
                    else "N/A"
                )

                # Extract the href for the total amount of pages
                self.total_pages = int(
                    nav_links.find_all("a", class_="page-numbers")[-2].text.strip()
                    if len(nav_links.find_all("a", class_="page-numbers")) > 1
                    else -1
                )

                # Print the extracted pages data
                print(f"[Pages] Total: {self.total_pages}")

                data = {
                    "current_page": self.current_page,
                    "next_page_url": next_page_link,
                    "total_pages": self.total_pages,
                }

                return data
            else:
                print("Navigation links not found.")

                return None
        else:
            print(f"[{response.status_code}] Could not reach website {self.url}")

            return None

    def web_scraper(self) -> dict:
        scraper_start_timer = perf_counter()

        # Loop through all the pages
        # while self.current_page <= 1:
        while self.current_page <= self.total_pages:
            article_start_timer = perf_counter()

            # URL of the page we are scraping
            url = f"{self.url_articles}{self.current_page}"
            print(f"[Scraper] On page {self.current_page}")

            # Load the page
            response = requests.get(url)

            if response.status_code == 200:
                # Parse the HTML content
                soup = BeautifulSoup(response.content, "html.parser")

                # Find all article tags
                articles = soup.find_all("article")
                print(f"[Scraper] Found {len(articles)} articles")

                self.scraped_data = self.article_looper(articles)

                article_end_timer = perf_counter()

                if len(self.scraped_data) < 1:
                    print(
                        f"[Scraper] Finished with page {self.current_page - 1} in {article_end_timer - article_start_timer} seconds, no new entries found so we stop here."
                    )
                    self.total_pages = self.current_page - 1
                    break

                print(
                    f"[Scraper] Finished with page {self.current_page - 1} in {article_end_timer - article_start_timer} seconds, moving on..."
                )
            else:
                print(f"[{response.status_code}] Could not reach website {url}")

        scraper_end_timer = perf_counter()
        print(
            f"[Scraper] Finished {self.total_pages} pages scraping in {scraper_end_timer - scraper_start_timer} seconds"
        )

        if len(self.scraped_data) >= 1:
            self.dump_to_file(
                self.scraped_data,
                f"{logs_path}/logs/data/scraped_data_{self.year}_full.json",
            )
        return self.scraped_data

    def article_looper(self, articles) -> tuple[dict, int]:
        print(
            f"[Looper] Got {len(self.scraped_data)} scraped data ({self.current_page})."
        )
        for article in articles:
            article_start = perf_counter()
            ai_extract = False
            update_entry = False

            # Extract the id attribute
            article_id: str = str(article.get("id", "N/A"))

            # Extract entry-summary
            entry_summary: str = str(
                article.find("div", class_="entry-summary").text.strip()
                if article.find("div", class_="entry-summary")
                else "N/A"
            )

            # Continue with next loop if current article already exists in database
            if isinstance(existing_data, dict) and existing_data.get(article_id):
                if existing_data.get(article_id)["summary"] == entry_summary:
                    print(
                        f"[Scraper] {article_id} already exists in DB with the same summary\n{'-' * 50}"
                    )
                    continue
                else:
                    update_entry = True
                    print(
                        f"[Scraper] {article_id} needs to be updated in DB\n[Update] Old: {existing_data.get(article_id)['summary']}\n[Update] New: {entry_summary}"
                    )

            # Extract ht-day and ht-month-year
            ht_day: str = str(
                article.find("span", class_="ht-day").text.strip()
                if article.find("span", class_="ht-day")
                else "N/A"
            )
            ht_month_year: str = str(
                article.find("span", class_="ht-month-year").text.strip()
                if article.find("span", class_="ht-month-year")
                else "N/A"
            )

            # Extract author name
            author: str = str(
                article.find("span", class_="author vcard").text.strip()
                if article.find("span", class_="author vcard")
                else "N/A"
            )

            # Extract entry-title
            entry_title: str = str(
                article.find("h2", class_="entry-title").text.strip()
                if article.find("h2", class_="entry-title")
                else "N/A"
            )

            # Extract category name under fa fa-bookmark
            category: str = str(
                article.find("div", class_="entry-categories").find("a").text.strip()
                if article.find("div", class_="entry-categories")
                else "N/A"
            )

            # Extract comments
            comments: str = str(
                article.find("a", href=True, class_=None).text.strip()
                if article.find("i", class_="fa fa-comment-o")
                else "No Comments"
            )

            # Format the data
            formatted_date = f"{ht_day}.{bulgarian_months[ht_month_year.split()[0]]}.{ht_month_year.split()[1]}"  # Format to a datetime format - dd.MM.YYYY
            formatted_place = (
                re.search(self.place_pattern, entry_summary)
                .group(0)[0:]
                .replace("гр. ", "гр.")
                .replace("с. ", "с.")
                .replace("гр.", "гр. ")
                .replace("с.", "с. ")
                .replace("град ", "гр. ")
                .replace("село ", "с. ")
                if re.search(self.place_pattern, entry_summary)
                else None
            )
            formatted_period = f"{entry_summary.split('периода от ')[1].strip()[:5].replace(',', ':').replace('.',':').strip() if 'периода от ' in entry_summary else 'N/A'} - {entry_summary.split(' до ')[1].strip()[:5].replace(',', ':').replace('.',':').strip() if ' до ' in entry_summary else 'N/A'}"  # Try and avoid using RegEx for extracting period

            # Call GPT
            if (
                "N/A" in formatted_period
                or re.search(self.period_pattern_check, formatted_period) == None
                or formatted_place == None
                or len(formatted_place.split()) > 2
            ):
                gpt_extractor = OpenAIExtractor()
                if gpt_extractor.valid_key:
                    gpt_response = json.loads(
                        gpt_extractor.extract_data(
                            entry_summary, formatted_date.strip()
                        )
                    )
                    ai_extract = True
                    print(
                        f"[GPT] Place Old: {formatted_place} | New: {gpt_response['places']}"
                    )
                    print(
                        f"[GPT] Period Old: {formatted_period} | New: {gpt_response['period']}"
                    )
                    formatted_place = ", ".join(gpt_response["places"])
                    formatted_period = gpt_response["period"]

                    self.dump_to_file(
                        gpt_response,
                        f"{logs_path}/logs/gpt/{article_id}_{gpt_extractor.model}.json",
                    )

            self.scraped_data[article_id] = {
                "day": ht_day.strip(),
                "month_year": ht_month_year.strip(),
                "date": formatted_date.strip(),
                "place": formatted_place.strip(),
                "period": formatted_period.strip(),
                "author": author.strip(),
                "title": entry_title.strip(),
                "category": category.strip(),
                "summary": entry_summary,
                "current_page": self.current_page,
                "total_pages": self.total_pages,
                "comments": comments,
                "ai_extract": ai_extract,
                "gpt_data": gpt_response if ai_extract else None,
                "update_entry": update_entry,
            }
            article_end = perf_counter()
            print(
                f"[Scraper] Finished with {article_id} in {article_end - article_start} seconds\n{'-' * 50}"
            )
        else:
            self.current_page += 1

        print(f"[Looper] Outputting {len(self.scraped_data)} scraped data.")
        return self.scraped_data

    def dump_to_file(self, new_dump: dict, file_name: str):
        """Appends data to a JSON or creates a new one. Writes all other logs in a new file"""
        print(f"[File Dumper] Dumping {len(new_dump)} entries to {file_name}")

        if "json" in file_name:
            # Check if the file exists
            if os.path.exists(file_name):
                # Read the existing content
                with open(file_name, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = {}  # Empty file case
            else:
                data = {}

            # Update the JSON object with new data
            data.update(new_dump)

            # Write the updated data back to the file
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        else:
            # Write the data to the file
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(str(new_dump))

        print(f"[File Dumper] Data has been dumped to {file_name}")


def input_to_db(data: dict):
    db = Database()
    x = OpenAIExtractor()

    db_start = perf_counter()
    for key, item in data.items():
        insert_query = f"""
        INSERT IGNORE INTO vik_{x.model.replace("-", "_")} (`post_id`, `title`, `location`, `period`, `author`, `summary`, `category`, `ai_extract`, `page`, `total_pages`, `comments`, `article_date` ) 
        VALUES 
        ('{key}', '{item["title"]}', '{item["place"]}', '{item["period"]}', '{item["author"]}', '{item["summary"]}', '{item["category"]}', '{1 if item["ai_extract"] else 0}', '{item["current_page"]}', '{item["total_pages"]}', '{item["comments"]}', '{datetime.strptime(item["date"], "%d.%m.%Y").strftime("%Y-%m-%d")}');"""

        update_query = f"""
        UPDATE vik_{x.model.replace("-", "_")} 
        SET 
        `title` = '{item["title"]}', `location` = '{item["place"]}', `period` = '{item["period"]}', `author` = '{item["author"]}', `summary` = '{item["summary"]}', `category` = '{item["category"]}', 
        `ai_extract` = '{1 if item["ai_extract"] else 0}', `page` = '{item["current_page"]}', `total_pages` = '{item["total_pages"]}', `comments` = '{item["comments"]}', `article_date` = '{datetime.strptime(item["date"], "%d.%m.%Y").strftime("%Y-%m-%d")}' 
        WHERE `post_id` = '{key}';
        """

        if item["update_entry"]:
            # Move the existing entry to the edited table
            moved = db.move_data(key, existing_data.get(key), x.model)
            print(
                f"[DB] Could not move entry {key} to edited table"
                if moved == False
                else f"[DB] Moved entry {key} to edited table"
            )

            # Update the entry in the main table
            execution = db.execute_query(update_query)
            # print(f"[DB] Updating entry for '{key}'\n{update_query}")
        else:
            execution = db.execute_query(insert_query)

        if not execution:
            print(
                f"[DB] Could NOT add '{key}'\n{insert_query if item['update_entry'] == False else update_query}"
            )

    db.close_connection()
    db_end = perf_counter()
    print(f"[DB] Finished with {len(data)} entries in {db_end - db_start} seconds")


if __name__ == "__main__":
    start_total = perf_counter()

    year = datetime.now().year

    # Initiate to get the model name which is used for table names
    gpt = OpenAIExtractor()

    # Load the data we will use for checking existing entries
    db = Database()
    get_query = f"SELECT * FROM vik_{gpt.model.replace('-', '_')} WHERE `article_date` LIKE '{year}%';"
    existing_data = db.get_data(get_query)
    db.close_connection()

    if existing_data is not False:
        print(f"[Main] {len(existing_data)} entries loaded")

    # Start the scraping process
    x = Scraper(year=year, pages=2)

    if x.total_pages > 0:
        scraped = x.web_scraper()
    else:
        print(f"[Main] Got no pages")

    if len(scraped) >= 1:
        input_to_db(scraped)

    end_total = perf_counter()
    print(f"[Main] Finished the process in {end_total - start_total} seconds")
