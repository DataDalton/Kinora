"""
Script to automatically update requirements.txt to latest versions
Run: python update_requirements.py
"""

import subprocess
import sys
import os
from pathlib import Path


def get_latest_version(package_name):
    """Get the latest version of a package from PyPI"""
    try:
        # Remove extras like [reload] or [cryptography]
        base_package = package_name.split("[")[0]

        result = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", base_package],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Parse output to get available versions
        output = result.stdout
        if "Available versions:" in output:
            versions_line = output.split("Available versions:")[1].strip()
            versions = [v.strip() for v in versions_line.split(",")]
            if versions:
                latest = versions[0]  # First one is the latest
                print(f"✓ {base_package}: {latest}")
                return latest

        # Fallback: try pip show
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", base_package], capture_output=True, text=True, timeout=10
        )

        for line in result.stdout.split("\n"):
            if line.startswith("Version:"):
                version = line.split("Version:")[1].strip()
                print(f"✓ {base_package}: {version} (installed)")
                return version

    except Exception as e:
        print(f"✗ {package_name}: Error - {e}")
        return None

    return None


def update_requirements():
    """Update requirements.txt with latest versions"""
    print("Fetching latest versions from PyPI...\n")

    # Find requirements.txt in current directory or parent
    script_dir = Path(__file__).parent
    req_file = script_dir / "requirements.txt"

    if not req_file.exists():
        print(f"Could not find requirements.txt at: {req_file}")
        print(f"Please run this script from the backend directory or specify the path.")
        sys.exit(1)

    print(f"Found requirements.txt at: {req_file}\n")

    with open(req_file, "r") as f:
        lines = f.readlines()

    updated_lines = []

    for line in lines:
        line = line.strip()

        # Keep comments and empty lines
        if not line or line.startswith("#"):
            updated_lines.append(line)
            continue

        # Parse package name and check for extras
        if "==" in line:
            package_with_extras = line.split("==")[0]
            extras = ""

            # Check for extras like [reload], [cryptography], etc.
            if "[" in package_with_extras:
                package_name = package_with_extras.split("[")[0]
                extras = "[" + package_with_extras.split("[")[1]
            else:
                package_name = package_with_extras

            # Get latest version
            latest_version = get_latest_version(package_name)

            if latest_version:
                updated_line = f"{package_name}{extras}=={latest_version}"
                updated_lines.append(updated_line)
            else:
                # Keep original if we couldn't get latest
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # Write updated requirements
    with open(req_file, "w") as f:
        f.write("\n".join(updated_lines) + "\n")

    print("\nrequirements.txt updated with latest versions!")
    print(f"\nTo install: cd {script_dir} && pip install -r requirements.txt")


if __name__ == "__main__":
    update_requirements()
