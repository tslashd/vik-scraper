import os
import mysql.connector
from mysql.connector.cursor import MySQLCursorDict
from dotenv import load_dotenv


load_dotenv()
host = os.getenv("host")
user = os.getenv("user")
password = os.getenv("password")
database = os.getenv("database")


class Database:
    """### Connects to the database with credentials from `.env`"""

    def __init__(self):
        self.connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            auth_plugin="mysql_native_password",
        )
        self.cursor = self.connection.cursor(cursor_class=MySQLCursorDict)
        print(f"[DB] Successfully connected to '{database}' with user '{user}'")

    def close_connection(self):
        if self.connection.is_connected():
            self.cursor.close()
            self.connection.close()
            print("[DB] Connection closed")

    def execute_query(self, query: str) -> bool:
        """### Executes any query passed to it"""
        try:
            self.cursor.execute(query)
            self.connection.commit()
            # print("[DB] Query executed successfully")

            return True
        except mysql.connector.Error as err:
            print(f"[DB] Error: {err}")

            return False

    def get_data(self, query: str) -> dict | bool:
        """### Gets the existing data from DB to check for differences with new data"""
        try:
            return_data = {}
            self.cursor.execute(query)
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

                print(f"[DB] Got {len(return_data)} items from DB. Query:\n{query}")
                return return_data
            else:
                return False
        except mysql.connector.Error as err:
            print(f"[DB] Error: {err}")

            return False

    def move_data(self, key: str, post: dict, table: str) -> bool:
        """### Moves an existing `post_id` to the edited table"""

        query = f"""
            INSERT IGNORE INTO vik_{table.replace("-", "_")}_edited (`post_id`, `title`, `location`, `period`, `author`, `summary`, `category`, `ai_extract`, `page`, `total_pages`, `comments`, `article_date` ) 
            VALUES 
            ('{key}', '{post["title"]}', '{post["place"]}', '{post["period"]}', '{post["author"]}', '{post["summary"]}', '{post["category"]}', '{post["ai_extract"]}', 
            '{post["current_page"]}', '{post["total_pages"]}', '{post["comments"]}', '{post["date"]}');
        """

        try:
            self.cursor.execute(query)
            self.connection.commit()
            # print("[DB] Query executed successfully")

            return True
        except mysql.connector.Error as err:
            print(f"[DB] Error: {err}")

            return False
