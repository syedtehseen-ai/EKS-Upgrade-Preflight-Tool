from setuptools import setup, find_packages

setup(
    name="eks-preflight",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "boto3",
        "kubernetes"
    ],
    entry_points={
        "console_scripts": [
            "eks-preflight=eks_preflight.main:main",
        ],
    },
)