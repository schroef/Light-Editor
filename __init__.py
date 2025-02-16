bl_info = {
    "name": "Light Editor",
    "author": "Robert Rioux aka Blender Bob, Rombout Versluijs",
    "location": "3Dview > Light Editor",
    "version": (1, 9, 2),
    "blender": (4, 2, 0),
    "description": "A Light Editor and Light Linking addon",
    "category": "Object",
}

# __init__.py

def register():
    from .LightEditor import register as light_editor_register
    from .Linking import register as linking_register
    from .LightGroup import register as light_group_register

    light_editor_register()
    linking_register()
    light_group_register()

def unregister():
    from .LightGroup import unregister as light_group_unregister
    from .Linking import unregister as linking_unregister
    from .LightEditor import unregister as light_editor_unregister

    light_group_unregister()
    linking_unregister()
    light_editor_unregister()

if __name__ == "__main__":
    register()