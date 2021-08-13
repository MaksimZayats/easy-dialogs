from setuptools import find_packages, setup

setup(
    name='dialog',
    version='0.3.0b0',
    packages=find_packages(include=['dialog', 'dialog.*']),
    url='https://github.com/MaximZayats/aiogram-dialog',
    license='',
    author='Maxim',
    author_email='maximzayats1@gmail.com',
    description='',
    install_requires=[
        'aiogram~=2.14.3',
        'vkbottle~=3.0.2'
    ],
)
