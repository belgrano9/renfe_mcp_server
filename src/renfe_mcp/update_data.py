"""
Module to check and update Renfe GTFS schedule data.
Compares local data with server version and downloads if needed.

Security: Implements safe ZIP extraction to prevent Zip Slip attacks.
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

# Security: Allowed file extensions for GTFS data
ALLOWED_EXTENSIONS = {'.txt', '.csv', '.json'}
# Security: Maximum file size (50MB) to prevent zip bombs
MAX_FILE_SIZE = 50 * 1024 * 1024
# Security: Maximum total extraction size (500MB)
MAX_TOTAL_SIZE = 500 * 1024 * 1024


class ZipSlipError(Exception):
    """Raised when a Zip Slip attack is detected."""
    pass


class ZipSecurityError(Exception):
    """Raised for ZIP security violations."""
    pass


def safe_extract_zip(zip_path: str, extract_to: str) -> list[str]:
    """
    Safely extract a ZIP file, preventing Zip Slip and other attacks.

    Security measures:
    1. Path traversal prevention (Zip Slip)
    2. Absolute path rejection
    3. File extension validation
    4. File size limits (prevent zip bombs)
    5. Total size limits

    Args:
        zip_path: Path to the ZIP file
        extract_to: Target directory for extraction

    Returns:
        List of extracted file paths

    Raises:
        ZipSlipError: If path traversal is detected
        ZipSecurityError: For other security violations
    """
    extract_to = Path(extract_to).resolve()
    extracted_files = []
    total_size = 0

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            # Get the member's filename
            member_name = member.filename

            # SECURITY CHECK 1: Reject absolute paths
            if member_name.startswith('/') or member_name.startswith('\\'):
                raise ZipSlipError(
                    f"Absolute path detected in ZIP: {member_name}"
                )

            # SECURITY CHECK 2: Reject path traversal attempts
            if '..' in member_name:
                raise ZipSlipError(
                    f"Path traversal attempt detected: {member_name}"
                )

            # SECURITY CHECK 3: Validate the resolved path is within target
            member_path = (extract_to / member_name).resolve()

            # Ensure the resolved path starts with the target directory
            try:
                member_path.relative_to(extract_to)
            except ValueError:
                raise ZipSlipError(
                    f"Path escapes target directory: {member_name} -> {member_path}"
                )

            # Skip directories (they'll be created automatically)
            if member.is_dir():
                continue

            # SECURITY CHECK 4: Validate file extension
            file_ext = Path(member_name).suffix.lower()
            if file_ext and file_ext not in ALLOWED_EXTENSIONS:
                print(f"[SECURITY] Skipping file with disallowed extension: {member_name}")
                continue

            # SECURITY CHECK 5: Check individual file size
            if member.file_size > MAX_FILE_SIZE:
                raise ZipSecurityError(
                    f"File too large ({member.file_size / 1024 / 1024:.2f}MB): {member_name}"
                )

            # SECURITY CHECK 6: Check total extraction size
            total_size += member.file_size
            if total_size > MAX_TOTAL_SIZE:
                raise ZipSecurityError(
                    f"Total extraction size exceeds limit ({MAX_TOTAL_SIZE / 1024 / 1024:.0f}MB)"
                )

            # Create parent directories safely
            member_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract the file
            with zip_ref.open(member) as source:
                with open(member_path, 'wb') as target:
                    # Read in chunks to handle large files efficiently
                    chunk_size = 8192
                    while True:
                        chunk = source.read(chunk_size)
                        if not chunk:
                            break
                        target.write(chunk)

            extracted_files.append(str(member_path))

    return extracted_files


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
    """
    Download the GTFS zip file and extract it securely.

    Security: Uses safe_extract_zip() to prevent Zip Slip attacks.
    """
    print(f"[DOWNLOAD] Downloading GTFS data from {last_modified}...")

    try:
        # Download the zip file with timeout
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        # Save to file
        with open(LOCAL_ZIP_PATH, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"[OK] Downloaded {os.path.getsize(LOCAL_ZIP_PATH) / 1024 / 1024:.2f} MB")

        # Remove old data directory if it exists
        if os.path.exists(LOCAL_DATA_DIR):
            shutil.rmtree(LOCAL_DATA_DIR)

        # SECURITY: Use safe extraction instead of extractall()
        print(f"[EXTRACT] Securely extracting to {LOCAL_DATA_DIR}/...")
        try:
            extracted_files = safe_extract_zip(LOCAL_ZIP_PATH, LOCAL_DATA_DIR)
            print(f"[SECURITY] Safe extraction completed: {len(extracted_files)} files")
        except ZipSlipError as e:
            print(f"[SECURITY] ZIP SLIP ATTACK BLOCKED: {e}")
            print("[SECURITY] The downloaded file may be malicious. Aborting.")
            # Clean up the potentially malicious file
            if os.path.exists(LOCAL_ZIP_PATH):
                os.remove(LOCAL_ZIP_PATH)
            return False
        except ZipSecurityError as e:
            print(f"[SECURITY] Security violation: {e}")
            print("[SECURITY] The downloaded file failed security checks. Aborting.")
            if os.path.exists(LOCAL_ZIP_PATH):
                os.remove(LOCAL_ZIP_PATH)
            return False

        # Save metadata
        save_metadata(last_modified)

        print(f"[OK] GTFS data updated successfully!")
        print(f"     Version: {last_modified}")

        # List extracted files
        files = os.listdir(LOCAL_DATA_DIR)
        gtfs_files = [f for f in files if f.endswith('.txt')]
        print(f"     Files: {len(gtfs_files)} GTFS files extracted")

        return True

    except requests.Timeout:
        print(f"[ERROR] Download timed out. Please try again later.")
        return False
    except requests.RequestException as e:
        print(f"[ERROR] Network error during download: {e}")
        return False
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
