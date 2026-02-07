from setuptools import setup, find_packages

setup(
    name="opcua-cloud-bridge-common",
    version="1.0.0",
    description="Common data models and utilities for OPC UA to Cloud Bridge",
    author="GlobalCorp",
    author_email="engineering@globalcorp.com",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0.0",
        "PyYAML>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Monitoring",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    keywords="opcua, iot, industrial, bridge, cloud, telemetry",
    project_urls={
        "Bug Reports": "https://github.com/globalcorp/opcua-cloud-bridge/issues",
        "Source": "https://github.com/globalcorp/opcua-cloud-bridge",
        "Documentation": "https://opcua-cloud-bridge.readthedocs.io/",
    },
)
