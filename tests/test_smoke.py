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


def test_unpack_deb_extracts_files_and_skips_absolute_symlinks(tmp_path=None):
    import io
    import tarfile
    import tempfile
    from src.core.libreoffice_manager import unpack_deb
    tmp = Path(tmp_path or tempfile.mkdtemp())

    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:xz") as tar:
        body = b"#!/bin/sh\n"
        info = tarfile.TarInfo("./opt/libreoffice9.9/program/soffice")
        info.size, info.mode = len(body), 0o755
        tar.addfile(info, io.BytesIO(body))
        link = tarfile.TarInfo("./usr/bin/libreoffice9.9")
        link.type, link.linkname = tarfile.SYMTYPE, "/opt/libreoffice9.9/program/soffice"
        tar.addfile(link)

    def member(name, payload):
        head = f"{name:<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(payload):<10}`\n".encode()
        return head + payload + (b"\n" if len(payload) % 2 else b"")

    deb = tmp / "pkg.deb"
    deb.write_bytes(b"!<arch>\n" + member("debian-binary", b"2.0\n")
                    + member("control.tar.xz", b"x") + member("data.tar.xz", data.getvalue()))
    unpack_deb(deb, tmp / "out")

    soffice = tmp / "out/opt/libreoffice9.9/program/soffice"
    assert soffice.read_bytes() == b"#!/bin/sh\n" and os.access(soffice, os.X_OK)
    assert not (tmp / "out/usr/bin/libreoffice9.9").exists()   # абсолютная ссылка пропущена


def test_missing_linux_libraries_are_recognised():
    from src.core.libreoffice_manager import missing_libraries
    # Настоящая ошибка из чистого Debian-контейнера
    stderr = ("/root/.local/share/FileConverterPro/libreoffice/linux/opt/libreoffice26.2/program/oosplash: "
              "error while loading shared libraries: libXinerama.so.1: cannot open shared object file: "
              "No such file or directory")
    assert missing_libraries(stderr) == ["libXinerama.so.1"]
    assert missing_libraries("Error: source file could not be loaded") == []


if __name__ == "__main__":
    test_missing_linux_libraries_are_recognised()
    test_unpack_deb_extracts_files_and_skips_absolute_symlinks()
    test_parallel_threads_get_distinct_libreoffice_profiles()
    test_stylesheets_have_no_unfilled_tokens()
    print("ok")
