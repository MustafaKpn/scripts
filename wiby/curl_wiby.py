from bs4 import BeautifulSoup
import requests
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)
logger.info("Starting scraper")


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
    db = sqlite3.connect(dbname)
    for i in range(count):
        surprise_url = getSurpriseUrl(url)
        db.execute("""
        INSERT INTO urls (url)
        VALUES (?)
        ON CONFLICT(url) DO NOTHING
    """, (surprise_url,))
        
    db.commit()
    logger.info(f"Inserted {surprise_url} into the database {dbname}")



def countUrl(dbname):
    db = sqlite3.connect(dbname)
    cur = db.cursor()
    res = cur.execute("SELECT COUNT(*) FROM urls")
    return res.fetchone()[0]


def main():
    WIBY_URL = "https://www.wiby.me/surprise"
    DB_NAME = "wiby.db"

    logger.info("Fetching Wiby")
    fetchWibyUrls(WIBY_URL, DB_NAME, 20)
    logging.info(F"Inserted {countUrl(DB_NAME)} into {DB_NAME}")

main()