"""Create a project virtual environment for working with EDF EEG files."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_VENV_DIR = PROJECT_DIR / ".venv"
REQUIRED_PACKAGES = ("mne", "scipy", "matplotlib")


def venv_python(venv_dir: Path) -> Path:
    """Return the Python executable path for the current operating system."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(python: Path, *args: str) -> None:
    """Run a Python command and stop immediately if it fails."""
    command = [str(python), *args]
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=PROJECT_DIR, check=True)


def create_environment(venv_dir: Path) -> Path:
    """Create the virtual environment and return its Python executable."""
    python = venv_python(venv_dir)

    if not python.exists():
        print(f"Creating virtual environment: {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    else:
        print(f"Using existing virtual environment: {venv_dir}")

    return python


def install_packages(python: Path) -> None:
    """Install the packages needed to read and process EDF EEG data."""
    run(python, "-m", "pip", "install", "--upgrade", "pip")
    run(python, "-m", "pip", "install", *REQUIRED_PACKAGES)


def verify_installation(python: Path) -> None:
    """Verify that MNE and its EDF reader can be imported."""
    code = (
        "import mne; "
        "from mne.io import read_raw_edf; "
        "print(f'MNE {mne.__version__}: EDF reader ready')"
    )
    run(python, "-c", code)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a virtual environment for EDF/EEG processing with MNE."
    )
    parser.add_argument(
        "--venv",
        type=Path,
        default=DEFAULT_VENV_DIR,
        help="Virtual environment directory (default: .venv in this project)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    venv_dir = args.venv.expanduser().resolve()

    try:
        python = create_environment(venv_dir)
        install_packages(python)
        verify_installation(python)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"\nSetup failed: {exc}", file=sys.stderr)
        return 1

    activate = (
        venv_dir / "Scripts" / "Activate.ps1"
        if os.name == "nt"
        else venv_dir / "bin" / "activate"
    )
    print("\nSetup complete.")
    print(f"Activate the environment with:\n  {activate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
