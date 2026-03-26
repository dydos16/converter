"""
Сборка .app для macOS
"""
from setuptools import setup

APP = ['run.py']

DATA_FILES = [
    ('', ['src/']),
]

OPTIONS = {
    'argv_emulation': True,
    'packages': [
        'PySide6',
        'docx',
        'pptx',
        'reportlab',
        'PIL',
        'openpyxl',
        'loguru',
        'colorama',
        'lxml',
    ],
    'includes': [
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'PySide6.QtPrintSupport',
    ],
    'excludes': [
        'tkinter',
        'PyQt5',
        'PyQt6',
        'matplotlib',
        'scipy',
        'numpy',
    ],
    'plist': {
        'CFBundleName': 'File Converter Pro',
        'CFBundleDisplayName': 'File Converter Pro',
        'CFBundleIdentifier': 'com.fileconverter.pro',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleExecutable': 'File Converter Pro',
        'CFBundleDevelopmentRegion': 'ru',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
        'LSMinimumSystemVersion': '10.13',
    },
    'site_packages': True,
    'use_pythonpath': True,
    'semi_standalone': False,
    'strip': False,
}

setup(
    name='File Converter Pro',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)