import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import json
from urllib.parse import urljoin, urlparse

# ─────────────────────────────────────────
# CONFIG — edit these before running
# ─────────────────────────────────────────
BASE_URL = "https://example.com"       # 🔁 Replace with your target URL
MAX_PAGES = 5                          # Number of pages to scrape
OUTPUT_DIR = "scraped_output"          # Folder for saved results

# Pagination: how to get page 2, 3, etc.
# Common patterns (uncomment the one that fits your site):
def get_page_url(page_num):
    return f"{BASE_URL}?page={page_num}"          # ?page=2
    # return f"{BASE_URL}/page/{page_num}"         # /page/2
    # return f"{BASE_URL}&offset={page_num * 10}"  # offset-based

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}
# ─────────────────────────────────────────


def setup_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(f"{OUTPUT_DIR}/images", exist_ok=True)


def fetch_page(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"  ⚠️  Failed to fetch {url}: {e}")
        return None


def scrape_text_and_articles(soup, page_num):
    articles = []
    # Try common article/content tags
    for tag in soup.find_all(["article", "section", "div"], class_=lambda c: c and any(
            k in c for k in ["article", "post", "content", "entry", "story"])):
        title_tag = tag.find(["h1", "h2", "h3"])
        title = title_tag.get_text(strip=True) if title_tag else "N/A"
        paragraphs = " ".join(p.get_text(strip=True) for p in tag.find_all("p"))
        if title != "N/A" or paragraphs:
            articles.append({"page": page_num, "title": title, "text": paragraphs})
    return articles


def scrape_images(soup, page_url, page_num):
    images = []
    for img in soup.find_all("img", src=True):
        src = urljoin(page_url, img["src"])
        alt = img.get("alt", "")
        images.append({"page": page_num, "url": src, "alt": alt})
    return images


def scrape_links(soup, page_url, page_num):
    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        text = a.get_text(strip=True)
        links.append({"page": page_num, "text": text, "url": href})
    return links


def scrape_tables(soup, page_num):
    all_tables = []
    for i, table in enumerate(soup.find_all("table")):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            all_tables.append({"page": page_num, "table_index": i, "rows": rows})
    return all_tables


def scrape_categories(soup, page_num):
    categories = []
    # Common category patterns: nav menus, breadcrumbs, sidebar lists
    for tag in soup.find_all(["nav", "ul", "ol"], class_=lambda c: c and any(
            k in c for k in ["category", "categories", "menu", "breadcrumb", "nav", "sidebar", "tag"])):
        for item in tag.find_all(["li", "a"]):
            text = item.get_text(strip=True)
            link = item.find("a")
            href = urljoin(BASE_URL, link["href"]) if link and link.get("href") else ""
            if text:
                categories.append({"page": page_num, "category": text, "url": href})
    return categories


def download_images(images):
    print(f"\n📥 Downloading {len(images)} images...")
    for i, img in enumerate(images[:20]):  # cap at 20 to avoid flooding
        try:
            r = requests.get(img["url"], headers=HEADERS, timeout=10)
            ext = os.path.splitext(urlparse(img["url"]).path)[-1] or ".jpg"
            filename = f"{OUTPUT_DIR}/images/img_{i+1}{ext}"
            with open(filename, "wb") as f:
                f.write(r.content)
        except Exception as e:
            print(f"  ⚠️  Could not download {img['url']}: {e}")


def save_results(all_data):
    # Save articles
    if all_data["articles"]:
        pd.DataFrame(all_data["articles"]).to_csv(f"{OUTPUT_DIR}/articles.csv", index=False)
        print(f"  ✅ articles.csv — {len(all_data['articles'])} items")

    # Save images list
    if all_data["images"]:
        pd.DataFrame(all_data["images"]).to_csv(f"{OUTPUT_DIR}/images.csv", index=False)
        print(f"  ✅ images.csv — {len(all_data['images'])} items")

    # Save links
    if all_data["links"]:
        pd.DataFrame(all_data["links"]).to_csv(f"{OUTPUT_DIR}/links.csv", index=False)
        print(f"  ✅ links.csv — {len(all_data['links'])} items")

    # Save tables
    if all_data["tables"]:
        with open(f"{OUTPUT_DIR}/tables.json", "w") as f:
            json.dump(all_data["tables"], f, indent=2)
        print(f"  ✅ tables.json — {len(all_data['tables'])} tables")

    # Save categories
    if all_data["categories"]:
        pd.DataFrame(all_data["categories"]).to_csv(f"{OUTPUT_DIR}/categories.csv", index=False)
        print(f"  ✅ categories.csv — {len(all_data['categories'])} items")


def main():
    setup_output_dir()
    print(f"🕷️  Starting scrape of: {BASE_URL}")
    print(f"   Pages to scrape: {MAX_PAGES}\n")

    all_data = {
        "articles": [],
        "images": [],
        "links": [],
        "tables": [],
        "categories": [],
    }

    for page_num in range(1, MAX_PAGES + 1):
        url = get_page_url(page_num) if page_num > 1 else BASE_URL
        print(f"📄 Scraping page {page_num}: {url}")

        soup = fetch_page(url)
        if not soup:
            continue

        all_data["articles"].extend(scrape_text_and_articles(soup, page_num))
        all_data["images"].extend(scrape_images(soup, url, page_num))
        all_data["links"].extend(scrape_links(soup, url, page_num))
        all_data["tables"].extend(scrape_tables(soup, page_num))
        all_data["categories"].extend(scrape_categories(soup, page_num))

        print(f"   Found: {len(all_data['articles'])} articles, "
              f"{len(all_data['images'])} images, "
              f"{len(all_data['links'])} links, "
              f"{len(all_data['tables'])} tables, "
              f"{len(all_data['categories'])} categories (cumulative)")

    print(f"\n💾 Saving results to '{OUTPUT_DIR}/'...")
    save_results(all_data)
    download_images(all_data["images"])

    print(f"\n✅ Done! All files saved in '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
