#!/usr/bin/env python3
"""Build script for FlowPilot package.

This script:
1. Builds the frontend using bun
2. Copies the built frontend to the static directory
3. Optionally builds the Python package
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FRONTEND_DIR = ROOT / "frontend"
STATIC_DIR = ROOT / "src" / "flowpilot" / "static"


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=False,
        text=True,
    )


def check_dependencies() -> bool:
    """Check if required build dependencies are available."""
    # Check for bun
    if shutil.which("bun") is None:
        print("Error: 'bun' is not installed. Please install bun first.")
        print("  Visit: https://bun.sh")
        return False

    # Check for frontend directory
    if not FRONTEND_DIR.exists():
        print(f"Error: Frontend directory not found at {FRONTEND_DIR}")
        return False

    return True


def build_frontend() -> bool:
    """Build frontend and copy to static directory."""
    print("\n=== Building Frontend ===")

    # Install dependencies
    print("Installing frontend dependencies...")
    result = run_command(["bun", "install"], cwd=FRONTEND_DIR, check=False)
    if result.returncode != 0:
        print("Error: Failed to install frontend dependencies")
        return False

    # Build production bundle
    print("Building production bundle...")
    result = run_command(["bun", "run", "build"], cwd=FRONTEND_DIR, check=False)
    if result.returncode != 0:
        print("Error: Failed to build frontend")
        return False

    # Copy to static directory
    dist_dir = FRONTEND_DIR / "dist"
    if not dist_dir.exists():
        print(f"Error: Build output not found at {dist_dir}")
        return False

    if STATIC_DIR.exists():
        print(f"Removing existing static directory: {STATIC_DIR}")
        shutil.rmtree(STATIC_DIR)

    print(f"Copying build output to {STATIC_DIR}")
    shutil.copytree(dist_dir, STATIC_DIR)

    # Create a marker file to indicate this is a built frontend
    marker_file = STATIC_DIR / ".built"
    marker_file.write_text("Built by scripts/build.py\n")

    print(f"Frontend built successfully: {STATIC_DIR}")
    return True


def build_package() -> bool:
    """Build Python package."""
    print("\n=== Building Python Package ===")

    # Check if static directory exists
    if not STATIC_DIR.exists():
        print("Warning: Static directory not found. Run with --frontend first.")

    # Build the package
    result = run_command(
        [sys.executable, "-m", "build"],
        cwd=ROOT,
        check=False,
    )

    if result.returncode != 0:
        print("Error: Failed to build Python package")
        return False

    print("\nPackage built successfully!")
    print(f"Artifacts in: {ROOT / 'dist'}")
    return True


def clean() -> None:
    """Clean build artifacts."""
    print("\n=== Cleaning Build Artifacts ===")

    # Clean static directory
    if STATIC_DIR.exists():
        print(f"Removing: {STATIC_DIR}")
        shutil.rmtree(STATIC_DIR)

    # Clean Python build artifacts
    for path in [ROOT / "dist", ROOT / "build"]:
        if path.exists():
            print(f"Removing: {path}")
            shutil.rmtree(path)

    # Clean egg-info
    for egg_info in ROOT.glob("*.egg-info"):
        print(f"Removing: {egg_info}")
        shutil.rmtree(egg_info)

    # Clean frontend dist
    frontend_dist = FRONTEND_DIR / "dist"
    if frontend_dist.exists():
        print(f"Removing: {frontend_dist}")
        shutil.rmtree(frontend_dist)

    print("Clean complete!")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build FlowPilot package with bundled frontend")
    parser.add_argument(
        "--frontend",
        action="store_true",
        help="Build frontend only",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Build Python package only (assumes frontend already built)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build frontend and package (default if no flags)",
    )

    args = parser.parse_args()

    # Default to --all if no flags specified
    if not any([args.frontend, args.package, args.clean, args.all]):
        args.all = True

    if args.clean:
        clean()
        return 0

    if not check_dependencies():
        return 1

    if (args.frontend or args.all) and not build_frontend():
        return 1

    if (args.package or args.all) and not build_package():
        return 1

    print("\n=== Build Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
