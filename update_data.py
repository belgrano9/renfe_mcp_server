"""
Module to check and update Renfe GTFS schedule data.
Compares local data with server version and downloads if needed.
"""
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import requests


# Configuration
RENFE_API_URL = "https://data.renfe.com/api/3/action/resource_show"
RESOURCE_ID = "25d6b043-9e47-4f99-bd91-edd51d782450"
LOCAL_ZIP_PATH = "renfe_schedule.zip"
LOCAL_DATA_DIR = "renfe_schedule"
METADATA_FILE = "renfe_schedule/.last_updated"


def get_server_last_modified():
    """Get the last modified date from Renfe API."""
    try:
        response = requests.get(RENFE_API_URL, params={"id": RESOURCE_ID})
        response.raise_for_status()
        data = response.json()

        last_modified = data['result']['last_modified']
        download_url = data['result']['url']

        return last_modified, download_url
    except Exception as e:
        print(f"[ERROR] Error fetching server metadata: {e}")
        return None, None


def get_local_last_modified():
    """Get the last modified date of local data."""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return None


def save_metadata(last_modified):
    """Save the last modified timestamp to metadata file."""
    os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
    with open(METADATA_FILE, 'w') as f:
        f.write(last_modified)


def download_and_extract(download_url, last_modified):
    """Download the GTFS zip file and extract it."""
    print(f"[DOWNLOAD] Downloading GTFS data from {last_modified}...")

    try:
        # Download the zip file
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        # Save to file
        with open(LOCAL_ZIP_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"[OK] Downloaded {os.path.getsize(LOCAL_ZIP_PATH) / 1024 / 1024:.2f} MB")

        # Remove old data directory if it exists
        if os.path.exists(LOCAL_DATA_DIR):
            shutil.rmtree(LOCAL_DATA_DIR)

        # Extract the zip file
        print(f"[EXTRACT] Extracting to {LOCAL_DATA_DIR}/...")
        with zipfile.ZipFile(LOCAL_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(LOCAL_DATA_DIR)

        # Save metadata
        save_metadata(last_modified)

        print(f"[OK] GTFS data updated successfully!")
        print(f"     Version: {last_modified}")

        # List extracted files
        files = os.listdir(LOCAL_DATA_DIR)
        gtfs_files = [f for f in files if f.endswith('.txt')]
        print(f"     Files: {len(gtfs_files)} GTFS files extracted")

        return True

    except Exception as e:
        print(f"[ERROR] Error downloading/extracting data: {e}")
        return False


def needs_update():
    """Check if local data needs to be updated."""
    server_modified, download_url = get_server_last_modified()

    if not server_modified:
        print("[WARNING] Could not check server version")
        return False, None, None

    local_modified = get_local_last_modified()

    print(f"[CHECK] Checking data versions:")
    print(f"        Server: {server_modified}")
    print(f"        Local:  {local_modified or 'Not found'}")

    # Check if we need to update
    if not local_modified:
        print("[INFO] No local data found")
        return True, server_modified, download_url

    if server_modified != local_modified:
        print("[UPDATE] Server has newer data")
        return True, server_modified, download_url

    print("[OK] Local data is up to date")
    return False, server_modified, download_url


def update_if_needed():
    """Check for updates and download if needed."""
    print("=" * 60)
    print("  RENFE GTFS DATA UPDATE CHECK")
    print("=" * 60)
    print()

    should_update, server_modified, download_url = needs_update()

    if should_update and download_url:
        print()
        download_and_extract(download_url, server_modified)
        print()
        print("=" * 60)
        return True
    else:
        print()
        print("=" * 60)
        return False


def force_update():
    """Force download of latest data regardless of version."""
    print("=" * 60)
    print("  RENFE GTFS DATA FORCED UPDATE")
    print("=" * 60)
    print()

    server_modified, download_url = get_server_last_modified()

    if download_url:
        download_and_extract(download_url, server_modified)
        print()
        print("=" * 60)
        return True
    else:
        print("[ERROR] Could not get download URL")
        print()
        print("=" * 60)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        force_update()
    else:
        update_if_needed()
