import logging
import os

import mysql.connector
from mysql.connector.cursor import MySQLCursorDict
from dotenv import load_dotenv


load_dotenv()  # no-op in Docker; loads .env for local dev
host = os.getenv("host")
user = os.getenv("user")
password = os.getenv("password")
database = os.getenv("database")

TABLE_NAME = "vik_gpt_4o_mini"

logger = logging.getLogger("db")


class Database:
    """Connects to the database with credentials from `.env`"""

    def __init__(self):
        self.connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            auth_plugin="mysql_native_password",
        )
        self.cursor = self.connection.cursor(cursor_class=MySQLCursorDict)
        logger.info("Successfully connected to '%s' with user '%s'", database, user)

    def close_connection(self):
        if self.connection.is_connected():
            self.cursor.close()
            self.connection.close()
            logger.info("Connection closed")

    def _reconnect(self):
        """Attempt to reconnect to the database."""
        try:
            self.connection.reconnect(attempts=3, delay=2)
            self.cursor = self.connection.cursor(cursor_class=MySQLCursorDict)
            logger.info("Reconnected to database")
        except mysql.connector.Error as err:
            logger.error("Reconnection failed: %s", err)
            raise

    def execute_query(self, query: str, params: tuple = None) -> bool:
        """Executes a query with optional parameterized values."""
        try:
            self.cursor.execute(query, params)
            self.connection.commit()
            return True
        except mysql.connector.errors.OperationalError as err:
            logger.warning("Connection lost, attempting reconnect: %s", err)
            try:
                self._reconnect()
                self.cursor.execute(query, params)
                self.connection.commit()
                return True
            except mysql.connector.Error as retry_err:
                logger.error("Query failed after reconnect: %s", retry_err)
                return False
        except mysql.connector.Error as err:
            logger.error("Query error: %s", err)
            return False

    def get_data(self, query: str, params: tuple = None) -> dict | bool:
        """Gets existing data from DB to check for differences with new data."""
        try:
            return_data = {}
            self.cursor.execute(query, params)
            data = self.cursor.fetchall()

            if data:
                for item in data:
                    return_data[item["post_id"]] = {
                        "date": item["article_date"],
                        "place": item["location"],
                        "period": item["period"],
                        "author": item["author"],
                        "title": item["title"],
                        "category": item["category"],
                        "summary": item["summary"],
                        "current_page": item["page"],
                        "total_pages": item["total_pages"],
                        "comments": item["comments"],
                        "ai_extract": item["ai_extract"],
                    }

                logger.info("Got %d items from DB", len(return_data))
                return return_data
            else:
                return False
        except mysql.connector.Error as err:
            logger.error("Query error: %s", err)
            return False

    def move_data(self, key: str, post: dict, table: str = TABLE_NAME) -> bool:
        """Moves an existing `post_id` to the edited table."""
        query = f"""
            INSERT IGNORE INTO {table}_edited
            (`post_id`, `title`, `location`, `period`, `author`, `summary`,
             `category`, `ai_extract`, `page`, `total_pages`, `comments`, `article_date`)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            key,
            post["title"],
            post["place"],
            post["period"],
            post["author"],
            post["summary"],
            post["category"],
            post["ai_extract"],
            post["current_page"],
            post["total_pages"],
            post["comments"],
            post["date"],
        )

        return self.execute_query(query, params)
