"""Setuptools entry point."""
import codecs
import os

from setuptools import setup

DIRNAME = os.path.dirname(__file__)
CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "Framework :: Django :: 4.2",
    "Framework :: Django :: 5.1",
    "Framework :: Django :: 5.2",
    "Intended Audience :: Developers",
    "Natural Language :: English",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]
LONG_DESCRIPTION = (
        codecs.open(os.path.join(DIRNAME, "README.md"), encoding="utf-8").read()
        + "\n"
        + codecs.open(os.path.join(DIRNAME, "CHANGELOG.md"), encoding="utf-8").read()
)
REQUIREMENTS = [
    "django>=4.2.0,<6.0.0",
    "djangorestframework>=3.0.0,<4.0.0",
    "djangorestframework-simplejwt>=5.0.0,<6.0.0",
    "pyjwt>=2.6.0,<3.0.0",
    "requests>=2.32.0,<3.0.0",
]

setup(
    name="drf-simple-oauth2",
    version="1.0.1",
    description=""" Simple OAuth2 client package allowing to define OAuth2 / OpenID providers through settings. """,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author="Quentin Coumes (Codoc)",
    author_email="quentin@codoc.co",
    url="https://github.com/Codoc-os/drf-simple-oauth2",
    packages=["simple_oauth2"],
    include_package_data=True,
    install_requires=REQUIREMENTS,
    keywords="django simple_oauth2 oauth2 oauth openid authentication",
    classifiers=CLASSIFIERS,
)
