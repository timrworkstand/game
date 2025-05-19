import requests
from bs4 import BeautifulSoup

def scrape_top_movies():
    url = "https://www.rottentomatoes.com/guide/best-movies-of-all-time/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return

    soup = BeautifulSoup(response.content, "html.parser")

    table = soup.find("table", class_="table")
    if not table:
        print("Could not find the movies table.")
        return

    rows = table.find_all("tr")
    for row in rows[1:]:
        columns = row.find_all("td")
        if len(columns) >= 2:
            rank = columns[0].get_text(strip=True).rstrip('.')
            title = columns[2].a.get_text(strip=True)
            rating = columns[1].get_text(strip=True)
            print(f"{rank}. {title} - {rating}")

if __name__ == "__main__":
    scrape_top_movies()
