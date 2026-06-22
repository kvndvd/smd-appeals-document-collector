from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from webdriver_manager.chrome import ChromeDriverManager
# from webdriver_manager.microsoft import EdgeChromiumDriverManager


def _apply_download_behavior(driver, download_dir):
    """Enable Chrome downloads, including in headless mode."""
    folder = Path(download_dir).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)

    # Browser.setDownloadBehavior is required by newer headless Chrome.
    # Page.setDownloadBehavior is kept as a fallback for older drivers.
    for command in ("Browser.setDownloadBehavior", "Page.setDownloadBehavior"):
        try:
            params = {
                "behavior": "allow",
                "downloadPath": str(folder),
            }
            if command == "Browser.setDownloadBehavior":
                params["eventsEnabled"] = True
            driver.execute_cdp_cmd(command, params)
        except Exception:
            pass


def session(headless=True, download_dir=None):
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    )

    default_download_dir = Path(download_dir or Path.cwd() / "downloads").expanduser().resolve()
    default_download_dir.mkdir(parents=True, exist_ok=True)

    options.add_argument(f"--user-agent={user_agent}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-features=UseXNNPACK")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--high-dpi-support=1")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    options.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "download.default_directory": str(default_download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "download_restrictions": 0,
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "plugins.always_open_pdf_externally": True,
        "download.open_pdf_in_system_reader": False,
        "safebrowsing.enabled": True,
        "safebrowsing.disable_download_protection": True,
    })
    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    # driver = webdriver.Edge(service=Service(EdgeChromiumDriverManager().install()), options=options)

    _apply_download_behavior(driver, default_download_dir)

    if not headless:
        driver.maximize_window()

    return driver
