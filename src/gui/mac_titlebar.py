"""
Родная шапка окна macOS цвета фона приложения.

Шапка остаётся системной — значит, перетаскивание (в том числе неактивного окна),
двойной клик, прилипание к краям экрана делает сама macOS. Мы только делаем её
прозрачной, прячем заголовок и красим окно в цвет фона, чтобы шапка сливалась
с интерфейсом. AppKit вызываем через ctypes — без pyobjc.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import sys

from loguru import logger
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

_objc = None


def _lib():
    global _objc
    if _objc is None:
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        lib.objc_getClass.restype = ctypes.c_void_p
        lib.objc_getClass.argtypes = [ctypes.c_char_p]
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        _objc = lib
    return _objc


def _cls(name: str) -> int:
    return _lib().objc_getClass(name.encode())


def _msg(obj, selector: str, *args: tuple, restype=ctypes.c_void_p):
    """objc_msgSend с явными типами аргументов: args — пары (ctypes-тип, значение)."""
    lib = _lib()
    proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *(t for t, _ in args))
    send = proto(("objc_msgSend", lib))
    return send(obj, lib.sel_registerName(selector.encode()), *(v for _, v in args))


def style_titlebar(window: QWidget, color: QColor, dark: bool | None) -> None:
    """Прозрачная шапка без заголовка, окно цвета color.
    dark=None — «светофор» и системные элементы следуют за темой macOS."""
    if sys.platform != "darwin":
        return
    try:
        ns_window = _msg(int(window.winId()), "window")   # winId() на маке — это NSView
        if not ns_window:
            return
        _msg(ns_window, "setTitlebarAppearsTransparent:", (ctypes.c_bool, True), restype=None)
        _msg(ns_window, "setTitleVisibility:", (ctypes.c_long, 1), restype=None)   # NSWindowTitleHidden
        ns_color = _msg(_cls("NSColor"), "colorWithSRGBRed:green:blue:alpha:",
                        (ctypes.c_double, color.redF()), (ctypes.c_double, color.greenF()),
                        (ctypes.c_double, color.blueF()), (ctypes.c_double, 1.0))
        _msg(ns_window, "setBackgroundColor:", (ctypes.c_void_p, ns_color), restype=None)
        appearance = None
        if dark is not None:
            name = _msg(_cls("NSString"), "stringWithUTF8String:",
                        (ctypes.c_char_p, b"NSAppearanceNameDarkAqua" if dark else b"NSAppearanceNameAqua"))
            appearance = _msg(_cls("NSAppearance"), "appearanceNamed:", (ctypes.c_void_p, name))
        _msg(ns_window, "setAppearance:", (ctypes.c_void_p, appearance), restype=None)
    except Exception as e:   # оформление шапки — не повод ронять приложение
        logger.warning(f"Не удалось настроить шапку окна macOS: {e}")
