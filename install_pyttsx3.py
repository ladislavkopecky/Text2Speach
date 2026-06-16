import subprocess
import sys


def run_install(package: str) -> None:
    print(f"Installing {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", package])


def main() -> int:
    try:
        # pyttsx3 is the text-to-speech library used by text2hlas.py
        run_install("pyttsx3")
        run_install("edge-tts")
        run_install("pydub")
        run_install("imageio-ffmpeg")

        # Windows speech drivers used by pyttsx3 often rely on these packages.
        if sys.platform.startswith("win"):
            run_install("comtypes")
            run_install("pywin32")

        print("\nInstallation completed successfully.")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"\nInstallation failed with exit code {exc.returncode}.")
        return exc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
