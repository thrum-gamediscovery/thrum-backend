import os
import base64
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ====== CONFIG (env vars override these) ======
BASE_URL = os.getenv("GAMEOPEDIA_BASE_URL", "https://apiv2.gameopedia.com").rstrip("/")
USERNAME = os.getenv("GAMEOPEDIA_USERNAME", "703f7d0f43da5f41b5b10aa5").strip()
PASSWORD = os.getenv("GAMEOPEDIA_PASSWORD", "3xcv8#b~$4&Zl")
PACKAGE_TYPE = os.getenv("GAMEOPEDIA_PACKAGE_TYPE", "full")  # "full" or "delta"
OUT_DIR = Path(os.getenv("GAMEOPEDIA_OUT_DIR", "games_data"))
TIMEOUT_SECS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
# ==============================================

def _session() -> requests.Session:
    """Shared session with retry/backoff for 429/5xx."""
    s = requests.Session()
    retries = Retry(
        total=5, connect=5, read=5,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def get_basic_auth_token(username, password):
    token = f"{(username or '').strip()}:{password or ''}"
    return base64.b64encode(token.encode("utf-8")).decode("utf-8")

def login():
    print("Logging in to Gameopedia API...")
    auth_token = get_basic_auth_token(USERNAME, PASSWORD)
    headers = {"Authorization": f"Basic {auth_token}"}
    url = urljoin(BASE_URL + "/", "api/login")
    resp = _session().get(url, headers=headers, timeout=TIMEOUT_SECS)
    resp.raise_for_status()
    data = resp.json()
    if "IdToken" not in data:
        raise RuntimeError(f"Login response missing IdToken: {data}")
    print("Login successful.")
    return data["IdToken"]

def get_package_url(id_token, package_type="full"):
    if package_type not in ("full", "delta"):
        raise ValueError("package_type must be 'full' or 'delta'")
    print(f"Requesting {package_type} package URL...")
    headers = {"Authorization": f"Bearer {id_token}"}
    params = {"package_type": package_type}
    url = urljoin(BASE_URL + "/", "api/get_package")
    resp = _session().get(url, headers=headers, params=params, timeout=TIMEOUT_SECS)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "success" and data.get("package_url"):
        print("Package URL received.")
        return data["package_url"]
    raise RuntimeError(f"Failed to get package URL: {data}")

def download_package(url, filepath=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if filepath is None:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filepath = OUT_DIR / f"gameopedia-{PACKAGE_TYPE}-package-{ts}.gz"
    else:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading package from {url} ...")
    with _session().get(url, stream=True, timeout=TIMEOUT_SECS) as r:
        r.raise_for_status()
        total = 0
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)
    print(f"Package saved to {filepath} ({total/1_048_576:.2f} MB)")
    return str(filepath)

if __name__ == "__main__":
    id_token = login()
    package_url = get_package_url(id_token, package_type=PACKAGE_TYPE)
    download_package(package_url)  # -> writes .gz into game_data/
