from bs4 import BeautifulSoup
import requests
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

def getHtmlContent(link):
    response = requests.get(link)
    return response.text

def getSurpriseUrl(url):
    html_document = getHtmlContent(url)
    soup = BeautifulSoup(html_document, 'html.parser')
    surprise_link = str(soup.find_all("meta")[-1]).split(" ")[2][4:-1]

    logging.info(f"Fetched the url: {surprise_link}")

    return surprise_link


def createDatabase(dbname):
    db = sqlite3.connect(dbname)
    cur = db.cursor()
    res = cur.execute("SELECT name FROM sqlite_master WHERE name='urls'")
    if not res.fetchone():
        cur.execute("CREATE TABLE urls(id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE)")
        logging.info(f"{dbname} database was created")
    else:
        logging.info(f"Database {dbname} already exists")


def fetchWibyUrls(url, dbname, count=10):
    new_entries_count = 0

    with sqlite3.connect(dbname) as db:
        for _ in range(count):
            surprise_url = getSurpriseUrl(url)

            cursor = db.execute(
                """
                INSERT INTO urls (url)
                VALUES (?)
                ON CONFLICT(url) DO NOTHING
                """,
                (surprise_url,),
            )

            if cursor.rowcount == 1:
                new_entries_count += 1

    logger.info(f"Inserted {new_entries_count} new entries into database {dbname}")


def countUrl(dbname):
    db = sqlite3.connect(dbname)
    cur = db.cursor()
    res = cur.execute("SELECT COUNT(*) FROM urls")
    return res.fetchone()[0]


def main():
    WIBY_URL = "https://www.wiby.me/surprise"
    DB_NAME = "wiby.db"
    URLS_COUNT = 100

    logger.info("Starting Wiby crawler")
    fetchWibyUrls(WIBY_URL, DB_NAME, URLS_COUNT)
    logging.info(F"{DB_NAME} has {countUrl(DB_NAME)} entries")

main()