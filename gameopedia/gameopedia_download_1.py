import requests
import base64
import gzip
import json
import csv
import os

# ==== CONFIGURE HERE ====
BASE_URL = "https://apiv2.gameopedia.com"
USERNAME = "703f7d0f43da5f41b5b10aa5"
PASSWORD = "3xcv8#b~$4&Zl"

# =======================

def get_basic_auth_token(username, password):
    token = f"{username}:{password}"
    base64_token = base64.b64encode(token.encode('utf-8')).decode('utf-8')
    return base64_token

def login():
    print("Logging in to Gameopedia API...")
    auth_token = get_basic_auth_token(USERNAME, PASSWORD)
    headers = {"Authorization": f"Basic {auth_token}"}
    resp = requests.get(f"{BASE_URL}/api/login", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    print("Login successful.")
    return data["IdToken"]

def get_package_url(id_token, package_type="full"):
    print(f"Requesting {package_type} package URL...")
    headers = {"Authorization": f"Bearer {id_token}"}
    params = {"package_type": package_type}
    resp = requests.get(f"{BASE_URL}/api/get_package", headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "success":
        print("Package URL received.")
        return data["package_url"]
    else:
        raise Exception("Failed to get package URL")

def download_package(url, filepath="games_data/package.gz"):
    print(f"Downloading package from {url} ...")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"Package saved to {filepath}")
    
if __name__ == "__main__":
    id_token = login()
    package_url = get_package_url(id_token)
    download_package(package_url)
