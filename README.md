[![PyPI version](https://badge.fury.io/py/easy-dialogs.svg)](https://badge.fury.io/py/easy-dialogs)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)


### About

**Easy-dialogs** is a framework for creating chatbots.

**Easy-dialog** facilitates the creation of relationships and transitions between scenes (states).

Based on [aiogram](https://github.com/aiogram/aiogram), [vkbottle](https://github.com/vkbottle/vkbottle).

### Quickstart

1. Install:

```bash
pip install easy-dialogs
```

or

```bash
pip install git+https://github.com/MaximZayats/easy-dialogs
```

2. See [examples](examples)

### Usage

#### Simple Dialog example:

```python
from dialog.telegram import Dialog, Scene, Router, Relation
from dialog.telegram.types import Message


class MyDialog(Dialog):
    router = Router(Relation('MyDialog.scene1',
                             commands='start'))

    scene1 = Scene(messages=Message(text='Inside the Scene 1'),
                   relations=Relation('MyDialog.scene2',
                                      text='scene2'))
    scene2 = Scene(messages=Message(text='Inside the Scene 2'),
                   relations=Relation('MyDialog.scene1',
                                      text='scene1'))


dp = ...

Dialog.register_handlers(dp)

executor.start_polling(dp)  # aiogram default start method

```