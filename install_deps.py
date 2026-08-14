import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
VENV = BASE / "venv"
REQS = BASE / "requirements.txt"
MARKER = VENV / ".deps_installed"

UNIX_CANDIDATES = ["python3.13", "python3.12", "python3.11", "python3.10", "python3"]
WINDOWS_CANDIDATES = [["py", "-3.12"], ["py", "-3.11"], ["py", "-3.10"], ["py", "-3"], ["python"]]


def log(msg):
    print(msg)


def fail(msg):
    log("")
    log("ERROR: " + msg)
    log("Setup was not completed. Please close this window, then double-click the launcher again.")
    if os.name == "nt":
        os.system("pause")
    else:
        try:
            input("Press Enter to close...")
        except EOFError:
            pass
    sys.exit(1)


def venv_python():
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def find_interpreter():
    candidates = WINDOWS_CANDIDATES if os.name == "nt" else [[c] for c in UNIX_CANDIDATES]
    for cand in candidates:
        try:
            probe = subprocess.run(cand + ["--version"], capture_output=True, text=True, timeout=30)
            if probe.returncode == 0:
                return cand
        except Exception:
            continue
    return None


def create_venv(interp):
    log("")
    log("First-time setup - creating a private environment for the app...")
    subprocess.run(interp + ["-m", "venv", str(VENV)], check=True)


def install_deps():
    log("Installing the app (this downloads the AI engine, about 1.5 GB...")  # noqa: E501
    log("   ...please be patient, this happens only once).")
    py = venv_python()
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(py), "-m", "pip", "install", "-r", str(REQS)], check=True)
    MARKER.touch()


def download_model():
    log("")
    log("Downloading the AI model (about 100 MB)...")
    py = venv_python()
    subprocess.run([str(py), "-c", "from separator import ensure_model; ensure_model()"], cwd=str(BASE), check=True)


def main():
    interp = find_interpreter()
    if interp is None:
        fail("Python could not be found. Install it from https://www.python.org/downloads/ then retry.")
    log("Using Python: " + " ".join(interp))

    if not VENV.exists():
        try:
            create_venv(interp)
        except Exception:
            shutil.rmtree(VENV, ignore_errors=True)
            fail("Could not create the environment. Check that Python is installed correctly.")
    if not MARKER.exists():
        try:
            install_deps()
        except Exception as e:
            shutil.rmtree(VENV, ignore_errors=True)
            fail("Installing the app failed: {}".format(e))
    try:
        download_model()
    except Exception:
        log("")
        log("Note: the model will be downloaded automatically the first time you split a song.")

    log("")
    log("Setup is ready. Opening the app...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
