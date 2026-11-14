"""Safe diagnostics; does not print API keys or tokens or contact external services."""
from importlib import import_module
from platform import system, python_version
from jarvis.config import Config, api_key, data_dir

if __name__ == "__main__":
    print("JARVIS DIAGNOSTICS")
    print("OS:", system(), "Python:", python_version())
    print("Data directory:", data_dir())
    print("API key:", "configured" if api_key() else "missing")
    cfg = Config.load()
    print("Wake listener:", "enabled" if cfg.wake_enabled else "disabled")
    print("Google Desktop OAuth file:", "selected" if cfg.google_credentials_path else "not selected")
    modules = ["PySide6", "openai", "sounddevice", "numpy", "psutil", "PIL", "pyttsx3", "keyring", "vosk", "googleapiclient", "google_auth_oauthlib"]
    for name in modules:
        try:
            import_module(name)
            print(f"{name:23} OK")
        except Exception as exc:
            print(f"{name:23} UNAVAILABLE ({type(exc).__name__})")
