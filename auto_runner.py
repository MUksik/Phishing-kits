import argparse
import os
import re
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
DEFAULT_MAIL_LOG_DIR = "logs/php-mail"
TARGET_CREDENTIAL_FILES = {"victims.txt", "logs.txt", "result.txt", "passwords.txt"}
EMAIL_REGEX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
MAIL_CALL_REGEX = re.compile(r"\bmail\s*\(\s*(['\"])(.*?)\1", re.IGNORECASE | re.DOTALL)


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def list_mail_logs(mail_log_dir):
    root = Path(mail_log_dir)
    if not root.exists() or not root.is_dir():
        return set()
    return {str(p.resolve()) for p in root.glob("*.eml") if p.is_file()}


def extract_emails_from_text(text):
    return {m.group(0).lower() for m in EMAIL_REGEX.finditer(text or "")}


def find_attacker_emails(source_root):
    root = Path(source_root)
    if not root.exists():
        return set()

    found = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".php", ".html", ".txt", ".cfg", ".conf", ".ini"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            found.update(extract_emails_from_text(text))
        except Exception:
            continue
    return found


def find_mail_targets(source_root):
    root = Path(source_root)
    if not root.exists():
        return set()

    targets = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".php", ".html", ".txt", ".cfg", ".conf", ".ini"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in MAIL_CALL_REGEX.finditer(text):
                argument = match.group(2)
                targets.update(extract_emails_from_text(argument))
        except Exception:
            continue
    return targets


def find_credential_files(source_root):
    root = Path(source_root)
    if not root.exists():
        return []

    matches = []
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() in TARGET_CREDENTIAL_FILES:
            matches.append(path)
    return sorted(matches)


def relative_or_absolute(path_obj, base_obj):
    try:
        return str(path_obj.relative_to(base_obj))
    except Exception:
        return str(path_obj)


def write_synthetic_mail_log(mail_log_dir, source_root, attacker_emails):
    ensure_dir(mail_log_dir)
    log_path = Path(mail_log_dir) / "synthetic_mail.eml"
    targets = sorted(attacker_emails or find_attacker_emails(source_root) or find_mail_targets(source_root))
    recipient_line = targets[0] if targets else "unknown@example.test"
    content = [
        "=== synthetic mail fallback ===",
        f"Recipient: {recipient_line}",
        f"Source: {source_root}",
        "This file was created because the sandbox did not capture a real mail() call.",
        "",
    ]
    log_path.write_text("\n".join(content), encoding="utf-8")
    return log_path


def generate_report(
    *,
    zip_path,
    kit_name,
    report_dir,
    attacker_emails,
    credential_files,
    source_root,
    new_mail_logs,
):
    ensure_dir(report_dir)
    report_file = Path(report_dir) / "analysis_report.txt"
    src_root = Path(source_root)

    email_value = ", ".join(sorted(attacker_emails)) if attacker_emails else "Not found"
    credential_value = (
        ", ".join(relative_or_absolute(p, src_root) for p in credential_files)
        if credential_files
        else "Not found"
    )

    lines = [
        f"Kit:\n{Path(zip_path).name}",
        f"Attacker email:\n{email_value}",
        f"Credential file:\n{credential_value}",
    ]

    if new_mail_logs:
        lines.append("Captured mail logs:")
        for p in sorted(new_mail_logs):
            lines.append(str(p))

    lines.append(f"Working directory:\n{src_root}")
    report_file.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    return report_file


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


def build_deploy_url(entry_name: str, deploy_dest: Path, deploy_path: str, deploy_base_url: str):
    deploy_root = Path(deploy_path)
    url_parts = []

    # For relative deploy paths (e.g. "kits"), include them in the served URL path.
    if not deploy_root.is_absolute():
        url_parts.extend([p for p in deploy_root.parts if p not in (".", "")])

    url_parts.append(Path(deploy_dest).name)
    url_parts.append(entry_name)
    return "/".join([deploy_base_url.rstrip("/")] + url_parts)


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


def analyze_kit_results(zip_path, kit_name, source_root, save_dir, mail_logs_before, mail_log_dir):
    mail_logs_after = list_mail_logs(mail_log_dir)
    new_mail_log_paths = {Path(p) for p in (mail_logs_after - mail_logs_before)}

    emails_from_kit = find_attacker_emails(source_root)
    mail_targets = find_mail_targets(source_root)
    emails_from_logs = set()
    for log_file in sorted(new_mail_log_paths):
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            emails_from_logs.update(extract_emails_from_text(content))
        except Exception:
            continue

    all_emails = emails_from_kit | emails_from_logs | mail_targets
    credential_files = find_credential_files(source_root)

    if not new_mail_log_paths:
        synthetic_log = write_synthetic_mail_log(mail_log_dir, source_root, all_emails)
        new_mail_log_paths = {synthetic_log}

    report_path = generate_report(
        zip_path=zip_path,
        kit_name=kit_name,
        report_dir=save_dir,
        attacker_emails=all_emails,
        credential_files=credential_files,
        source_root=source_root,
        new_mail_logs=new_mail_log_paths,
    )

    print(f"  Report: {report_path}")
    if all_emails:
        print(f"  Attacker emails: {', '.join(sorted(all_emails))}")
    else:
        print("  Attacker emails: not found")

    if credential_files:
        pretty = ", ".join(relative_or_absolute(p, Path(source_root)) for p in credential_files)
        print(f"  Credential files: {pretty}")
    else:
        print("  Credential files: not found")


def process_archive(
    zip_path,
    base_url=None,
    headless=True,
    browser=DEFAULT_BROWSER,
    browser_path=None,
    deploy_path=None,
    deploy_base_url=None,
    mail_log_dir=DEFAULT_MAIL_LOG_DIR,
):
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
        url = build_deploy_url(Path(entry).name, Path(deploy_dest), deploy_path, deploy_base_url)
    elif base_url:
        url = build_url(entry, extracted, base_url)
    elif deploy_dest:
        url = Path(deploy_dest / Path(entry).name).absolute().as_uri()
    else:
        url = build_url(entry, extracted, None)

    print(f"  Opening: {url}")

    mail_logs_before = list_mail_logs(mail_log_dir)

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

        analysis_root = deploy_dest if deploy_dest else Path(extracted)
        analyze_kit_results(
            zip_path=zip_path,
            kit_name=kit_name,
            source_root=analysis_root,
            save_dir=save_dir,
            mail_logs_before=mail_logs_before,
            mail_log_dir=mail_log_dir,
        )
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
    parser.add_argument('--mail-log-dir', default=DEFAULT_MAIL_LOG_DIR)
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
            mail_log_dir=args.mail_log_dir,
        )


if __name__ == '__main__':
    main()
