from setuptools import setup, find_packages

setup(
    name="zotgrep",
    version="2.1.0",
    author="ZotGrep Contributors",
    description="Enhanced Zotero Library and Full-Text PDF Search",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "pyzotero>=1.8.0",
        "pypdfium2>=5.3.0",
        "nltk>=3.9.1",
        "PyYAML>=6.0.1",
    ],
    entry_points={
        'console_scripts': [
            'zotgrep=zotgrep.cli:main',
        ],
    },
    python_requires=">=3.11",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Researchers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    include_package_data=True,
)
