import os
import configparser


def load_credentials(config_path="pacer.config"):
    """
    Reads PACER credentials from pacer.config

    Expected format:

    [PACER]
    username = your_username
    password = your_password
    """

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Credential file not found: {config_path}. "
            "Create pacer.config in the same folder as the app."
        )

    config = configparser.ConfigParser()
    config.read(config_path)

    if "PACER" not in config:
        raise KeyError("Missing [PACER] section in pacer.config")

    username = config["PACER"].get("username", "").strip()
    password = config["PACER"].get("password", "").strip()

    if not username or not password:
        raise ValueError("PACER username/password missing in pacer.config")

    return username, password