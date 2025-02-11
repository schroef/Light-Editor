bl_info = {
    "name": "Light Editor Addon",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "description": "A Light Editor and Light Linking addon",
    "category": "Object",
}

from . import lightEditor
from . import Linking

def register():
    lightEditor.register()
    Linking.register()

def unregister():
    Linking.unregister()
    lightEditor.unregister()

if __name__ == "__main__":
    register()
