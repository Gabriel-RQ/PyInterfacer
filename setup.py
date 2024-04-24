from setuptools import find_packages, setup

setup(
    name="pyinterfacer",
    packages=find_packages(include=["pyinterfacer", "pyinterfacer.*"]),
    version="1.3.5",
    description="A modular library for handling interfaces in pygame projects.",
    author="Gabriel RQ",
    url="https://github.com/Gabriel-RQ/PyInterfacer",
    install_requires=["PyYAML", "pygame-ce"],
)
