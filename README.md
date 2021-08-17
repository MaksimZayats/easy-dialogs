### About

**Aiogram-dialog** is a framework for creating telegram bots.

**Aiogram-dialog** facilitates the creation of relationships and transitions between scenes (states).

Based on aiogram.

### Quickstart

1. Install:

```bash
pip install git+https://github.com/MaximZayats/aiogram-dialog
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

Dialog.register(dp)

executor.start_polling(dp)  # aiogram default start method

```