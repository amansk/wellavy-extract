from setuptools import setup, find_packages

setup(
    name="pdf-to-csv-blood-test",
    version="1.0.0",
    description="Extract blood test information from lab report PDFs and convert to CSV",
    author="Your Name",
    py_modules=["pdf_to_csv"],
    install_requires=[
        "PyPDF2==3.0.1",
        "click==8.1.7",
        "python-dateutil==2.8.2",
    ],
    entry_points={
        "console_scripts": [
            "pdf-to-csv=pdf_to_csv:main",
        ],
    },
    python_requires=">=3.7",
)
