from setuptools import setup, find_packages

setup(
    name="math-limits-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        'python-telegram-bot==20.7',
        'pandas==2.2.2',
        'openpyxl==3.1.5',
        'python-dotenv==1.0.0',
        'gunicorn==21.2.0',
    ],
    python_requires='>=3.8',
)
