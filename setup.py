#!/usr/bin/env python3
"""Setup script for the xvoice2 package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="xvoice2",
    version="0.1.0",
    author="Jim Smith",
    author_email="jim@example.com",
    description="A cross-platform voice dictation application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tdoris/xvoice2",
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "xvoice2=xvoice2.main:main",
        ],
    },
    # Define test dependencies separately
    extras_require={
        "test": [
            "pytest",
            "pytest-mock",
            "pytest-cov",
        ],
        "dev": [
            "black",
            "isort",
            "mypy",
            "flake8",
        ],
    },
)