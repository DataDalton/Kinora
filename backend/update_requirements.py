"""
Script to automatically update pyproject.toml dependencies to latest versions
Run: uv run update_requirements.py
"""

import subprocess
import sys
import re
from pathlib import Path


def getLatestVersion(packageName):
    """Get the latest version of a package from PyPI using uv"""
    try:
        # Remove extras like [reload] or [cryptography]
        basePackage = packageName.split("[")[0]

        result = subprocess.run(
            ["uv", "pip", "compile", "--quiet", "--no-header", "-"],
            input=f"{basePackage}\n",
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Parse output to get resolved version
            for line in result.stdout.strip().split("\n"):
                if line and not line.startswith("#"):
                    match = re.match(rf"^{re.escape(basePackage)}==(.+)$", line, re.IGNORECASE)
                    if match:
                        version = match.group(1)
                        print(f"  {basePackage}: {version}")
                        return version

        # Fallback: use uv pip show for installed packages
        result = subprocess.run(
            ["uv", "pip", "show", basePackage],
            capture_output=True,
            text=True,
            timeout=10,
        )

        for line in result.stdout.split("\n"):
            if line.startswith("Version:"):
                version = line.split("Version:")[1].strip()
                print(f"  {basePackage}: {version} (installed)")
                return version

    except Exception as e:
        print(f"  {packageName}: Error - {e}")
        return None

    return None


def updateDependencies():
    """Update pyproject.toml with latest versions"""
    print("Fetching latest versions from PyPI...\n")

    scriptDir = Path(__file__).parent
    pyprojectFile = scriptDir / "pyproject.toml"

    if not pyprojectFile.exists():
        print(f"Could not find pyproject.toml at: {pyprojectFile}")
        sys.exit(1)

    print(f"Found pyproject.toml at: {pyprojectFile}\n")

    with open(pyprojectFile, "r") as f:
        content = f.read()

    # Pattern to match dependency lines with version constraints
    dependencyPattern = re.compile(r'^(\s*)"([a-zA-Z0-9_-]+)(\[[^\]]+\])?>=([^"]+)",$', re.MULTILINE)

    def replaceDependency(match):
        indent = match.group(1)
        packageName = match.group(2)
        extras = match.group(3) or ""

        latestVersion = getLatestVersion(packageName)
        if latestVersion:
            return f'{indent}"{packageName}{extras}>={latestVersion}",'
        return match.group(0)

    updatedContent = dependencyPattern.sub(replaceDependency, content)

    with open(pyprojectFile, "w") as f:
        f.write(updatedContent)

    print("\npyproject.toml updated with latest versions!")
    print(f"\nTo sync dependencies: cd {scriptDir} && uv sync")


if __name__ == "__main__":
    updateDependencies()
