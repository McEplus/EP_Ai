# coding=utf-8
from {base_import} import {base_class}


class {class_name}({base_class}):
    def __init__(self):
        {base_class}.__init__(
            self,
            {ui_name},
            {scroll_path},
            {screen_path},
            {block_path}
        )
        self.LayoutConfig = {{
            "columns": {columns},
            "interval_x": 0,
            "interval_y": -20
        }}
        self.ScreenRenderConfig = [
            {{
                "id": "ExampleOption",
                "label": "示例选项",
                "touch_type": "Toggle",
                "bind_func": self.OnExampleOption,
                "default_value": True
            }}
        ]

    def OnExampleOption(self, State):
        pass

