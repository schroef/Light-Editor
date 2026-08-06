import bpy
from bpy.types import Operator, Panel, Menu

class LG_MT_lightgroup_context_menu(Menu):
    bl_label = "LighGroup Specials"

    def draw(self, _context):
        layout = self.layout

        layout.operator("scene.view_layer_add_used_lightgroups", icon='ADD')
        layout.operator("scene.view_layer_remove_unused_lightgroups", icon='REMOVE')

        layout.separator()
        layout.operator(
            "lg.reset_all_lightgroups",
            icon='LOOP_BACK',
            text="Reset All LighGroups",
        )
        layout.operator(
            "lg.remove_all_lightgroups",
            icon='NONE',
            text="Delete All LighGroups",
        )

class LG_ResetAllLighgrGroups(Operator):
    """Remove all lights from any LightGroups."""
    bl_idname = "lg.reset_all_lightgroups"
    bl_label = "Reset All LightGroups"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        view_layer = context.view_layer
        # Unassign lights from the group before removing the group
        for obj in context.scene.objects :
            print(obj.type)
            if obj.type == 'LIGHT' and (obj.lightgroup != ""): 
                obj.lightgroup = ""

                # Force redraw panel so lightgroup gets updated
                for area in context.screen.areas:
                    if area.type == 'PROPERTIES':
                        area.tag_redraw()

        for obj in bpy.data.worlds:
            if obj.lightgroup != "": 
                obj.lightgroup = ""

                # Force redraw panel so lightgroup gets updated
                for area in context.screen.areas:
                    if area.type == 'PROPERTIES':
                        area.tag_redraw()

        else:
            self.report({'INFO'}, "All Lightgroups cleared.")
        return {'FINISHED'}


class LG_RemoveAllLighgrGroups(Operator):
    """Remove all LightGroups."""
    bl_idname = "lg.remove_all_lightgroups"
    bl_label = "Remove All the LightGroups in the scene. Also removes them from the lights."
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        view_layer = context.view_layer
        # Unassign lights from the group before removing the group
        if hasattr(view_layer, "lightgroups"):
            for index, item in reversed(list(enumerate(view_layer.lightgroups))):
                view_layer.active_lightgroup_index = index

                # Use the Blender operator to remove the lightgroup
                bpy.ops.scene.view_layer_remove_lightgroup()

                # Force redraw panel so lightgroup gets updated
                for area in context.screen.areas:
                    if area.type == 'PROPERTIES':
                        area.tag_redraw()

        else:
            self.report({'INFO'}, "All Lightgroups Removed.")
        return {'FINISHED'}
    
classes = [
    LG_MT_lightgroup_context_menu,
    LG_ResetAllLighgrGroups,
    LG_RemoveAllLighgrGroups,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)



def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()