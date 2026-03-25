"""
Установочный файл для приложения
"""
from setuptools import setup, find_packages

setup(
    name="file-converter-pro",
    version="1.0.0",
    description="Мощный конвертер файлов с графическим интерфейсом",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        'PyQt6>=6.6.1',
        'python-docx>=1.1.0',
        'PyPDF2>=3.0.1',
        'reportlab>=4.1.0',
        'Pillow>=10.1.0',
        'openpyxl>=3.1.2',
        'pandas>=2.1.4',
        'python-magic>=0.4.27',
        'loguru>=0.7.2',
        'colorama>=0.4.6',
    ],
    entry_points={
        'console_scripts': [
            'file-converter=src.main:main',
        ],
    },
    python_requires='>=3.8',
)