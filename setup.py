from setuptools import setup, find_packages

setup(
    name="rc_zoho_microservices",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.21.0",
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
        "jinja2>=3.1.2",
        "python-multipart>=0.0.6",
        "email-validator>=2.0.0",
        "cryptography>=40.0.0",
        "python-dotenv>=1.0.0",
        "aio-pika>=9.0.0",
        "requests>=2.28.0",
        "typing-extensions>=4.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "isort>=5.0.0",
            "mypy>=1.0.0",
            "flake8>=6.0.0",
        ],
    },
    python_requires=">=3.9",
    author="Your Name",
    author_email="your.email@example.com",
    description="Microservices integration between RingCentral and Zoho CRM",
    keywords="ringcentral, zoho, crm, integration, microservices",
    url="https://github.com/yourusername/rc_zoho_microservices",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 