from setuptools import setup, find_packages

setup(
    name="zotsearch",
    version="0.2.1",
    author="ZotSearch Contributors",
    description="Enhanced Zotero Library and Full-Text PDF Search",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "pyzotero>=1.5.0",
        "pypdfium2>=4.0.0",
        "nltk>=3.8"
    ],
    entry_points={
        'console_scripts': [
            'zotsearch=zotsearch.cli:main',
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Researchers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    include_package_data=True,
)