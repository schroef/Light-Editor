bl_info = {
    "name": "Light Editor",
    "author": "Robert Rioux aka Blender Bob, Rombout Versluijs",
    "location": "3Dview > Light Editor",
    "version": (1, 8, 0),
    "blender": (4, 2, 0),
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
