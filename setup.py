from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gitdigital-policy-engine",
    version="1.0.0",
    author="GitDigital Team",
    author_email="team@gitdigital.ai",
    description="Rules-as-Code engine for eligibility, compliance logic, and thresholds",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gitdigital/policy-engine",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "redis>=5.0.0",
        "celery>=5.3.0",
        "jsonschema>=4.20.0",
        "jinja2>=3.1.0",
        "graphviz>=0.20.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "gitdigital-engine=gitdigital.cli.main:main",
        ],
    },
)
