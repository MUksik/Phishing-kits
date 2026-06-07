import os
import re
import sys
import errno
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


DOWNLOAD_DIR = "downloaded_kits"
HEADERS = {"User-Agent": "url-scanner/1.0 (+https://example.com)"}


def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def read_input(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            yield line


def find_zip_links(base_url, html_text):
    found = set()
    soup = BeautifulSoup(html_text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if ".zip" in href.lower():
            found.add(urljoin(base_url, href))

    for m in re.finditer(r"[\'\"]?(https?:\\/\\/[^\'\">]+?\.zip)[\'\"]?", html_text, re.I):
        found.add(m.group(1))

    return sorted(found)


def download_file(url, out_dir):
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path) or "download.zip"
    host = parsed.netloc.replace(":", "_")
    target_name = f"{host}__{filename}"
    target_path = os.path.join(out_dir, target_name)

    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(target_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        print(f"Downloaded: {url} -> {target_path}")
        return target_path
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None


def scan_url(url, out_dir):
    print(f"Scanning: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  Could not fetch {url}: {e}")
        return []

    zip_links = find_zip_links(url, r.text)

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    common_names = ["kit.zip", "phishing.zip", "site.zip", "package.zip"]
    for name in common_names:
        candidate = urljoin(base, name)
        if candidate not in zip_links:
            try:
                h = requests.head(candidate, headers=HEADERS, timeout=8, allow_redirects=True)
                if h.status_code == 200 and 'zip' in h.headers.get('Content-Type',''):
                    zip_links.append(candidate)
            except Exception:
                pass

    saved = []
    for z in zip_links:
        p = download_file(z, out_dir)
        if p:
            saved.append(p)

    if not zip_links:
        print(f"  No ZIPs found for {url}")

    return saved


def main(input_file="input_urls.txt"):
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        sys.exit(1)

    ensure_dir(DOWNLOAD_DIR)

    any_downloaded = 0
    for url in read_input(input_file):
        saved = scan_url(url, DOWNLOAD_DIR)
        any_downloaded += len(saved)

    print(f"Done. Total archives saved: {any_downloaded}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
