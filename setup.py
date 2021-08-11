from setuptools import setup, find_packages


setup(
    name='dialog',
    version='0.1.0a0',
    packages=find_packages(include=['dialog', 'dialog.*']),
    url='https://github.com/MaximZayats/aiogram-dialog',
    license='',
    author='Maxim',
    author_email='maximzayats1@gmail.com',
    description='',
    install_requires=[
        'aiogram~=2.14.3',
    ],
)
