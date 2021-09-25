import os

from setuptools import find_packages, setup

VERSION = '0.3.9b0'


def readme() -> str:
    """Load the contents of the README file"""
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    with open(readme_path, 'r') as f:
        return f.read()


setup(
    name='easy-dialogs',
    description='A mini-framework for creating chatbots.'
                'Facilitates the creation of relationships and transitions between scenes (states).',
    long_description=readme(),
    long_description_content_type='text/markdown',
    version=VERSION,
    packages=find_packages(include=['dialog', 'dialog.*']),
    url='https://github.com/MaximZayats/aiogram-dialog',
    author='Maxim',
    author_email='maximzayats1@gmail.com',
    install_requires=['aiogram~=2.14.3', 'vkbottle~=3.0.2'],
    keywords=[
        'python',
        'fsm',
        'telegram',
        'asyncio',
        'chatbot',
        'bot-framework',
        'vk',
        'framework',
    ],
)
