from dataclasses import dataclass
from typing import Optional


@dataclass
class FutureScene:
    class_name: Optional[str]
    scene_name: str


class FutureDialog:
    """
    Used to create a link to a dialog that has not yet been initialized.
    Can only be used to create scene relation.
    """

    def __init__(self, class_name: Optional[str] = None):
        self.class_name = class_name

    def __getattr__(self, scene_name: str) -> FutureScene:
        return FutureScene(class_name=self.class_name, scene_name=scene_name)
