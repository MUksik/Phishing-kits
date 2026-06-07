import argparse
import os
import shutil
import zipfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

DOWNLOAD_DIR = "downloaded_kits"
EXTRACT_ROOT = "kits"
LOG_ROOT = "logs/auto_runner"
DEFAULT_BROWSER = "chrome"
SUPPORTED_BROWSERS = ["chrome", "firefox"]


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def extract_zip(zip_path, extract_root=EXTRACT_ROOT):
    zip_path = Path(zip_path)
    if not zip_path.exists():
        return None
    name = zip_path.stem
    dest = Path(extract_root) / name
    i = 1
    base_dest = dest
    while dest.exists():
        dest = Path(f"{base_dest}_{i}")
        i += 1
    ensure_dir(dest)
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(dest)
        return str(dest)
    except zipfile.BadZipFile:
        return None


COMMON_ENTRY = ["index.php", "index.html", "default.php", "home.php", "login.php"]


def find_entry_file(extracted_dir):
    p = Path(extracted_dir)
    for name in COMMON_ENTRY:
        candidate = p / name
        if candidate.exists():
            return candidate
    for ext in ('*.php', '*.html'):
        files = list(p.glob(ext))
        if files:
            return files[0]
    for root, dirs, files in os.walk(p):
        for f in files:
            if f.lower().startswith('index') and (f.lower().endswith('.php') or f.lower().endswith('.html')):
                return Path(root) / f
    return None


def build_url(entry_file: Path, extracted_dir: str, base_url: str = None):
    if base_url:
        rel = Path(extracted_dir).name
        return "/".join([base_url.rstrip('/'), rel, entry_file.name])
    else:
        return Path(entry_file).absolute().as_uri()


def find_browser_binary(browser, browser_path=None):
    if browser_path:
        return browser_path if shutil.which(browser_path) or Path(browser_path).exists() else None

    env_var = {
        'chrome': 'CHROME_BIN',
        'firefox': 'FIREFOX_BIN'
    }.get(browser)
    if env_var and os.getenv(env_var):
        return os.getenv(env_var)

    candidates = {
        'chrome': ['chrome', 'google-chrome', 'chromium', 'chromium-browser'],
        'firefox': ['firefox']
    }.get(browser, [])

    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def setup_driver(browser=DEFAULT_BROWSER, headless=True, browser_path=None):
    binary = find_browser_binary(browser, browser_path)
    if not binary:
        print(f"Failed to find '{browser}'. Please install {browser.title()} or set {browser.upper()}_BIN.")
        return None

    try:
        if browser == 'firefox':
            opts = FirefoxOptions()
            if headless:
                opts.add_argument('--headless')
            opts.binary_location = binary
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=opts)
        else:
            opts = ChromeOptions()
            if headless:
                opts.add_argument('--headless=new')
                opts.add_argument('--disable-gpu')
            opts.add_argument('--no-sandbox')
            opts.add_argument('--disable-dev-shm-usage')
            opts.binary_location = binary
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)

        driver.set_page_load_timeout(30)
        return driver
    except SessionNotCreatedException as e:
        print(f"Failed to create session for '{browser}': {e}")
        return None
    except WebDriverException as e:
        print(f"Failed to start {browser.title()} WebDriver: {e}")
        return None


def autofill_and_submit(driver, save_dir):
    ensure_dir(save_dir)
    forms = driver.find_elements(By.TAG_NAME, 'form')
    if not forms:
        forms = [driver]

    for idx, form in enumerate(forms, start=1):
        try:
            inputs = form.find_elements(By.TAG_NAME, 'input')
            for inp in inputs:
                try:
                    itype = (inp.get_attribute('type') or '').lower()
                    name = inp.get_attribute('name') or inp.get_attribute('id') or ''
                    if itype in ('text', 'email'):
                        if 'email' in name.lower() or itype == 'email':
                            inp.clear()
                            inp.send_keys('victim@example.test')
                        else:
                            inp.clear()
                            inp.send_keys('John Doe')
                    elif itype == 'password':
                        inp.clear()
                        inp.send_keys('P@ssw0rd!')
                    elif itype in ('tel', 'number'):
                        inp.clear()
                        inp.send_keys('123456789')
                    elif itype in ('checkbox', 'radio'):
                        try:
                            inp.click()
                        except Exception:
                            pass
                except Exception:
                    continue

            textareas = form.find_elements(By.TAG_NAME, 'textarea')
            for area in textareas:
                try:
                    area.clear()
                    area.send_keys('Test message.')
                except Exception:
                    pass

            try:
                submit = form.find_element(By.CSS_SELECTOR, "input[type=submit], button[type=submit], button")
                try:
                    submit.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", submit)
            except NoSuchElementException:
                is_form_element = getattr(form, 'tag_name', '').lower() == 'form'
                if is_form_element:
                    try:
                        driver.execute_script("arguments[0].submit();", form)
                    except Exception:
                        pass
                else:
                    try:
                        button = driver.find_element(By.TAG_NAME, 'button')
                        button.click()
                    except Exception:
                        pass

            time.sleep(2)
            driver.save_screenshot(os.path.join(save_dir, f'screenshot_form_{idx}.png'))
            with open(os.path.join(save_dir, f'page_after_form_{idx}.html'), 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
        except Exception as e:
            print(f"Error #{idx}: {e}")


def process_archive(zip_path, base_url=None, headless=True, browser=DEFAULT_BROWSER, browser_path=None, deploy_path=None, deploy_base_url=None):
    print(f"Processing: {zip_path}")
    extracted = extract_zip(zip_path)
    if not extracted:
        print(f"  Failed to extract {zip_path}")
        return

    entry = find_entry_file(extracted)
    if not entry:
        print(f"  There is no entry file in {extracted}")
        return

    deploy_dest = None
    if deploy_path:
        kit_name = Path(extracted).name
        dest = Path(deploy_path) / kit_name
        i = 1
        base_dest = dest
        while dest.exists():
            dest = Path(f"{base_dest}_{i}")
            i += 1
        try:
            shutil.copytree(extracted, dest)
            deploy_dest = dest
            print(f"  Deployed to: {deploy_dest}")
        except Exception as e:
            print(f"  Failed to deploy to {deploy_path}: {e}")

    if deploy_base_url and deploy_dest:
        rel = Path(deploy_dest).name
        url = "/".join([deploy_base_url.rstrip('/'), rel, Path(entry).name])
    elif base_url:
        url = build_url(entry, extracted, base_url)
    elif deploy_dest:
        url = Path(deploy_dest / Path(entry).name).absolute().as_uri()
    else:
        url = build_url(entry, extracted, None)

    print(f"  Opening: {url}")

    driver = setup_driver(browser=browser, headless=headless, browser_path=browser_path)
    if not driver:
        print("  There is no webdriver available.")
        return

    try:
        driver.get(url)
        kit_name = Path(extracted).name
        save_dir = os.path.join(LOG_ROOT, kit_name)
        ensure_dir(save_dir)
        driver.save_screenshot(os.path.join(save_dir, 'page_initial.png'))
        autofill_and_submit(driver, save_dir)
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip')
    parser.add_argument('--dir', default=DOWNLOAD_DIR)
    parser.add_argument('--base-url')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--browser', default=DEFAULT_BROWSER, choices=SUPPORTED_BROWSERS)
    parser.add_argument('--browser-path')
    parser.add_argument('--deploy-path')
    parser.add_argument('--deploy-base-url')
    args = parser.parse_args()

    ensure_dir(LOG_ROOT)
    ensure_dir(EXTRACT_ROOT)

    zips = []
    if args.zip:
        zips = [args.zip]
    else:
        for f in os.listdir(args.dir):
            if f.lower().endswith('.zip'):
                zips.append(os.path.join(args.dir, f))

    if not zips:
        print('There is no ZIP files.')
        return

    for z in zips:
        process_archive(
            z,
            base_url=args.base_url,
            headless=args.headless,
            browser=args.browser,
            browser_path=args.browser_path,
            deploy_path=args.deploy_path,
            deploy_base_url=args.deploy_base_url,
        )


if __name__ == '__main__':
    main()
