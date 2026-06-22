import logging
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ORDER_DESC_PATTERN = re.compile(r"\borders?\b", re.IGNORECASE)
DOWNLOAD_CONFIRMATION_TEXT = "download confirmation"
ACCEPT_BUTTON_XPATH = "//input[@type='button' and @value='Accept Charges and Retrieve']"
PDF_WAIT_SECONDS = 60


@dataclass(frozen=True)
class OrderDocument:
    description: str
    href: str
    doc_number: str


def court_folder_name(location_id: str) -> str:
    """Use the LocationID value directly as the court folder name, such as CA7 or CA11."""
    code = (location_id or "UNKNOWN").strip().upper()
    return code or "UNKNOWN"


def safe_case_filename(case_number: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (case_number or "UNKNOWN").strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "UNKNOWN"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def set_download_dir(driver, folder: Path) -> None:
    """Set the active Chrome download folder, including for headless Chrome."""
    folder.mkdir(parents=True, exist_ok=True)
    resolved = str(folder.resolve())
    cd_outputs = []

    # Newer headless Chrome needs Browser.setDownloadBehavior.
    # Page.setDownloadBehavior is kept as a fallback for older ChromeDriver builds.
    for command in ("Browser.setDownloadBehavior", "Page.setDownloadBehavior"):
        try:
            params = {
                "behavior": "allow",
                "downloadPath": resolved,
            }
            if command == "Browser.setDownloadBehavior":
                params["eventsEnabled"] = True
            driver.execute_cdp_cmd(command, params)
            cd_outputs.append(command)
        except Exception as exc:
            logging.debug("%s failed while setting download folder: %s", command, exc)

    if cd_outputs:
        logging.info("Chrome download folder set to %s", resolved)
    else:
        logging.warning("Could not update Chrome download folder through CDP: %s", resolved)


def page_has_download_confirmation(driver) -> bool:
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        body_text = ""
    source = driver.page_source or ""
    return DOWNLOAD_CONFIRMATION_TEXT in f"{body_text}\n{source}".lower()


def find_order_documents(driver) -> List[OrderDocument]:
    """Find attached-document table rows whose Description contains Order/Orders."""
    documents: List[OrderDocument] = []
    rows = driver.find_elements(By.XPATH, "//tr[td]")

    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 4:
            continue

        description = (cells[3].text or "").strip()
        if not ORDER_DESC_PATTERN.search(description):
            continue

        links = row.find_elements(By.XPATH, ".//a[.//img[contains(@title, 'Open Document') or contains(@alt, 'Open')]]")
        if not links:
            links = row.find_elements(By.XPATH, ".//a[contains(@href, '/docs')]")
        if not links:
            continue

        href = links[0].get_attribute("href")
        if not href:
            continue

        doc_number = (cells[1].text or str(len(documents) + 1)).strip()
        documents.append(OrderDocument(description=description, href=href, doc_number=doc_number))

    return documents


def _current_download_files(folder: Path) -> set[Path]:
    if not folder.exists():
        return set()
    return {path for path in folder.iterdir() if path.is_file()}


def wait_for_new_pdf(folder: Path, before_files: set[Path], timeout: int = PDF_WAIT_SECONDS) -> Optional[Path]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        current_files = _current_download_files(folder)
        unfinished = [p for p in current_files if p.name.endswith(".crdownload") or p.name.endswith(".tmp")]
        new_files = [p for p in current_files - before_files if p.suffix.lower() == ".pdf"]
        if new_files and not unfinished:
            newest = max(new_files, key=lambda p: p.stat().st_mtime)
            # Give Chrome a short moment to release the file handle.
            time.sleep(0.5)
            return newest
        time.sleep(0.5)
    return None


def accept_charges_and_download(driver, download_folder: Path, target_path: Path, timeout: int = 30) -> Optional[Path]:
    wait = WebDriverWait(driver, timeout)
    try:
        wait.until(lambda d: page_has_download_confirmation(d))
    except TimeoutException:
        logging.warning("Download Confirmation marker was not detected before looking for the accept button.")

    before_files = _current_download_files(download_folder)
    button = wait.until(EC.element_to_be_clickable((By.XPATH, ACCEPT_BUTTON_XPATH)))
    button.click()

    downloaded = wait_for_new_pdf(download_folder, before_files)
    if downloaded is None:
        logging.error("Timed out waiting for PDF download in %s", download_folder)
        return None

    final_path = unique_path(target_path)
    if downloaded.resolve() == final_path.resolve():
        return final_path

    final_path.parent.mkdir(parents=True, exist_ok=True)
    if final_path.exists():
        final_path = unique_path(final_path)
    shutil.move(str(downloaded), str(final_path))
    return final_path


def download_order_documents_from_current_page(driver, output_root, location_id, case_number, timeout=30) -> int:
    """
    Download only attached documents whose description contains Order/Orders.

    If the current page is already a Download Confirmation page, it accepts charges
    and downloads that document using the same naming convention.
    """
    output_root = Path(output_root).expanduser().resolve()
    court_folder = output_root / court_folder_name(location_id)
    set_download_dir(driver, court_folder)

    case_part = safe_case_filename(case_number)
    base_target = court_folder / f"LDC_SMD_{case_part}_PCQ.pdf"

    if page_has_download_confirmation(driver):
        logging.info("Download Confirmation page detected for %s. Accepting charges and retrieving PDF.", case_number or "(blank)")
        result = accept_charges_and_download(driver, court_folder, base_target, timeout=timeout)
        if result:
            logging.info("Downloaded PDF: %s", result)
            return 1
        return 0

    order_docs = find_order_documents(driver)
    if not order_docs:
        logging.info("No attached document descriptions containing Order/Orders were found for %s.", case_number or "(blank)")
        return 0

    logging.info("Found %s Order document(s) for %s.", len(order_docs), case_number or "(blank)")
    original_handle = driver.current_window_handle
    downloaded_count = 0

    for doc_index, doc in enumerate(order_docs, start=1):
        logging.info("Opening Order document %s | Description: %s", doc.doc_number, doc.description)
        existing_handles = set(driver.window_handles)
        driver.execute_script("window.open(arguments[0], '_blank');", doc.href)
        WebDriverWait(driver, timeout).until(lambda d: len(set(d.window_handles) - existing_handles) > 0)
        new_handle = list(set(driver.window_handles) - existing_handles)[0]
        driver.switch_to.window(new_handle)

        try:
            # Multiple Order documents for the same case receive a suffix to avoid overwrite.
            if len(order_docs) == 1:
                target_path = base_target
            else:
                target_path = court_folder / f"LDC_SMD_{case_part}_PCQ_{doc_index}.pdf"

            result = accept_charges_and_download(driver, court_folder, target_path, timeout=timeout)
            if result:
                downloaded_count += 1
                logging.info("Downloaded Order document %s to %s", doc.doc_number, result)
            else:
                logging.error("Order document %s did not download successfully.", doc.doc_number)
        finally:
            try:
                driver.close()
            except Exception:
                pass
            if original_handle in driver.window_handles:
                driver.switch_to.window(original_handle)
            elif driver.window_handles:
                driver.switch_to.window(driver.window_handles[0])

    return downloaded_count
