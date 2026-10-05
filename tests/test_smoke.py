"""Smoke-проверки: python -m pytest tests  (или python tests/test_smoke.py)"""
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_parallel_threads_get_distinct_libreoffice_profiles():
    from src.core.libreoffice_manager import LibreOfficeManager
    lo = LibreOfficeManager()
    seen, gate = [], threading.Barrier(3)

    def grab():
        seen.append(lo._get_user_profile_path())
        gate.wait()  # держим все три потока живыми одновременно

    threads = [threading.Thread(target=grab) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(seen)) == 3, seen
    # завершившиеся потоки освобождают слоты — новый поток берёт существующий
    t = threading.Thread(target=lambda: seen.append(lo._get_user_profile_path()))
    t.start(); t.join()
    assert seen[-1] in seen[:3]


def test_stylesheets_have_no_unfilled_tokens():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.styles import get_stylesheet_for
    for mode in ("light", "dark", "system"):
        assert "$" not in get_stylesheet_for(mode)


if __name__ == "__main__":
    test_parallel_threads_get_distinct_libreoffice_profiles()
    test_stylesheets_have_no_unfilled_tokens()
    print("ok")
