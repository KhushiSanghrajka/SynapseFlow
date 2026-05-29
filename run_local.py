import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"


def run_checked(command: list[str], cwd: Path | None = None) -> None:
    print(f"[setup] Running: {' '.join(command)}")
    subprocess.check_call(command, cwd=str(cwd or ROOT))


def run_best_effort(command: list[str], cwd: Path | None = None) -> None:
    print(f"[setup] Running (best effort): {' '.join(command)}")
    try:
        subprocess.check_call(command, cwd=str(cwd or ROOT))
    except subprocess.CalledProcessError as exc:
        print(f"[warn] Command failed but continuing: {exc}")


def command_succeeds(command: list[str], cwd: Path | None = None) -> bool:
    completed = subprocess.run(command, cwd=str(cwd or ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return completed.returncode == 0


def venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def recreate_venv() -> None:
    if VENV_DIR.exists():
        print(f"[setup] Recreating virtual environment at {VENV_DIR}")
        shutil.rmtree(VENV_DIR)
    run_checked([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=ROOT)


def ensure_working_pip(venv_python: Path) -> Path:
    if command_succeeds([str(venv_python), "-m", "pip", "--version"], cwd=ROOT):
        return venv_python

    print("[warn] Virtual environment pip is broken. Attempting repair with ensurepip.")
    run_best_effort([str(venv_python), "-m", "ensurepip", "--upgrade"], cwd=ROOT)
    if command_succeeds([str(venv_python), "-m", "pip", "--version"], cwd=ROOT):
        return venv_python

    print("[warn] ensurepip repair failed. Rebuilding .venv from scratch.")
    recreate_venv()
    repaired_python = venv_python_path(VENV_DIR)
    run_best_effort([str(repaired_python), "-m", "ensurepip", "--upgrade"], cwd=ROOT)
    if not command_succeeds([str(repaired_python), "-m", "pip", "--version"], cwd=ROOT):
        raise RuntimeError("Failed to recover pip inside .venv.")
    return repaired_python


def main() -> int:
    backend_dir = ROOT / "backend"
    frontend_dir = ROOT / "frontend"

    if not VENV_DIR.exists():
        recreate_venv()

    venv_python = venv_python_path(VENV_DIR)
    if not venv_python.exists():
        raise RuntimeError(f"Virtual environment python not found at {venv_python}")
    venv_python = ensure_working_pip(venv_python)

    run_checked(
        [str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"],
        cwd=backend_dir,
    )
    if not (frontend_dir / "node_modules").exists():
        run_checked(["npm", "install"], cwd=frontend_dir)

    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(backend_dir)

    backend_proc = subprocess.Popen(
        [str(venv_python), "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd=str(backend_dir),
        env=backend_env,
    )
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"],
        cwd=str(frontend_dir),
        env=os.environ.copy(),
    )

    print("[run] Backend: http://localhost:8000")
    print("[run] Frontend: http://localhost:5173")
    print("[run] Press Ctrl+C to stop both processes.")

    try:
        while True:
            if backend_proc.poll() is not None or frontend_proc.poll() is not None:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (backend_proc, frontend_proc):
            if proc.poll() is None:
                proc.terminate()
        for proc in (backend_proc, frontend_proc):
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
