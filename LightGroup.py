import bpy
from bpy.types import Operator, Panel

# Dictionaries to track group states
group_collapse_dict = {}  # Tracks collapsed/expanded states for groups
group_exclusive_dict = {}  # Tracks exclusive toggle states for groups

class LG2_AssignLightGroup(Operator):
    """Assign the selected light group to selected lights."""
    bl_idname = "light_editor.assign_light_group"
    bl_label = "Assign"

    def execute(self, context):
        view_layer = context.view_layer
        if hasattr(view_layer, "lightgroups") and view_layer.active_lightgroup_index < len(view_layer.lightgroups):
            active_group = view_layer.lightgroups[view_layer.active_lightgroup_index]
            selected_lights = [obj for obj in context.selected_objects if obj.type == 'LIGHT']
            for light in selected_lights:
                light.lightgroup = active_group.name

            # Reset light selection after assignment
            bpy.ops.light_editor.reset_light_selection()

        else:
            self.report({'WARNING'}, "No light group selected or available.")
        return {'FINISHED'}

class LG2_UnassignLightGroup(Operator):
    """Unassign the selected lights from their current light group."""
    bl_idname = "light_editor.unassign_light_group"
    bl_label = "Unassign"

    def execute(self, context):
        selected_lights = [obj for obj in context.selected_objects if obj.type == 'LIGHT']
        for light in selected_lights:
            light.lightgroup = ""

        # Reset light selection after unassigning
        bpy.ops.light_editor.reset_light_selection()

        return {'FINISHED'}

class LG2_ResetLightSelection(Operator):
    """Reset the selection of lights."""
    bl_idname = "light_editor.reset_light_selection"
    bl_label = "Reset Light Selection"

    def execute(self, context):
        # Deselect all objects in the scene
        bpy.ops.object.select_all(action='DESELECT')

        # Reset the custom `is_selected` property for all lights
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT':
                obj.is_selected = False

        self.report({'INFO'}, "Deselected all lights")
        return {'FINISHED'}

class LG2_ToggleLightSelection(Operator):
    """Toggle selection for an individual light."""
    bl_idname = "light_editor.toggle_light_selection"
    bl_label = "Toggle Light Selection"
    light_name: bpy.props.StringProperty()

    def execute(self, context):
        light_obj = bpy.data.objects.get(self.light_name)
        if light_obj:
            light_obj.is_selected = not light_obj.is_selected  # Toggle the custom property
        else:
            self.report({'WARNING'}, f"Light '{self.light_name}' not found.")
        return {'FINISHED'}

class LG2_ToggleGroupExclusive(Operator):
    """Toggle exclusive activation of this group."""
    bl_idname = "light_editor.toggle_group_exclusive"
    bl_label = "Toggle Group Exclusive"
    group_key: bpy.props.StringProperty()

    def execute(self, context):
        global group_exclusive_dict
        # Toggle the exclusive state of the current group
        is_exclusive = not group_exclusive_dict.get(self.group_key, False)
        group_exclusive_dict[self.group_key] = is_exclusive

        # If exclusive is ON, disable all other groups
        if is_exclusive:
            view_layer = context.view_layer
            exclusive_group_name = self.group_key.replace("group_", "")
            for obj in view_layer.objects:
                if obj.type == 'LIGHT':
                    if getattr(obj, "lightgroup", "") != exclusive_group_name:
                        obj.hide_viewport = True  # Hide lights not in the exclusive group
                    else:
                        obj.hide_viewport = False  # Show lights in the exclusive group
        else:
            # If exclusive is OFF, restore all lights to their normal state
            for obj in context.view_layer.objects:
                if obj.type == 'LIGHT':
                    obj.hide_viewport = False

        return {'FINISHED'}

class LG2_ToggleGroup(Operator):
    """Toggle the collapse state of a group."""
    bl_idname = "light_editor.toggle_group"
    bl_label = "Toggle Group"
    group_key: bpy.props.StringProperty()

    def execute(self, context):
        global group_collapse_dict
        group_collapse_dict[self.group_key] = not group_collapse_dict.get(self.group_key, False)
        return {'FINISHED'}

class LG2_RemoveLightGroup(Operator):
    """Remove the selected light group."""
    bl_idname = "light_editor.remove_light_group"
    bl_label = "Remove Light Group"

    def execute(self, context):
        view_layer = context.view_layer
        if hasattr(view_layer, "lightgroups") and view_layer.active_lightgroup_index < len(view_layer.lightgroups):
            active_group_name = view_layer.lightgroups[view_layer.active_lightgroup_index].name

            # Clear the lightgroup property for lights assigned to the removed group
            for obj in view_layer.objects:
                if obj.type == 'LIGHT' and getattr(obj, "lightgroup", "") == active_group_name:
                    obj.lightgroup = ""  # Clear the lightgroup assignment

            # Remove the group
            bpy.ops.scene.view_layer_remove_lightgroup()

            # Clean up dictionaries
            group_key = f"group_{active_group_name}"
            if group_key in group_collapse_dict:
                del group_collapse_dict[group_key]
            if group_key in group_exclusive_dict:
                del group_exclusive_dict[group_key]

            # Force UI redraw
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        return {'FINISHED'}

def draw_main_row(box, obj):
    """Draws a row of controls for each light in the UI."""
    row = box.row(align=True)
    # Use the custom property for the checkbox
    row.prop(obj, "is_selected", text="", emboss=True, icon='NONE')  # Checkbox for selection
    # Light name
    row.prop(obj, "name", text="")

class LG2_LightGroupPanel(Panel):
    bl_label = "Light Groups"
    bl_idname = "LG2_LightGroupPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Editor"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        view_layer = context.view_layer

        # Light group list and controls
        row = layout.row(align=True)
        col = row.column()
        col.template_list("UI_UL_list", "lightgroups", view_layer, "lightgroups", view_layer, "active_lightgroup_index", rows=3)
        col = row.column(align=True)
        col.operator("scene.view_layer_add_lightgroup", icon='ADD', text="")
        col.operator("light_editor.remove_light_group", icon='REMOVE', text="")

        # Align the three buttons in a single row
        row = layout.row(align=True)
        row.operator("light_editor.assign_light_group", text="Assign")
        row.operator("light_editor.unassign_light_group", text="Unassign")
        row.operator("light_editor.reset_light_selection", text="Reset")

        # Grouped lights
        groups = {}
        if hasattr(view_layer, "lightgroups"):
            for lg in view_layer.lightgroups:
                # Filter lights by type and hide_render
                groups[lg.name] = [
                    obj for obj in view_layer.objects
                    if obj.type == 'LIGHT' and not obj.hide_render and getattr(obj, "lightgroup", "") == lg.name
                ]
        # Add "Not Assigned" group
        not_assigned = [
            obj for obj in view_layer.objects
            if obj.type == 'LIGHT' and not obj.hide_render and not getattr(obj, "lightgroup", "")
        ]
        if not_assigned:
            groups["Not Assigned"] = not_assigned

        # Draw groups
        for grp_name, group_objs in groups.items():
            group_key = f"group_{grp_name}"
            if group_key not in group_collapse_dict:
                group_collapse_dict[group_key] = False  # Initialize group state if missing
            if group_key not in group_exclusive_dict:
                group_exclusive_dict[group_key] = False  # Initialize exclusive state if missing
            collapsed = group_collapse_dict[group_key]
            is_exclusive = group_exclusive_dict[group_key]

            header_box = layout.box()
            header_row = header_box.row(align=True)

            # Exclusive toggle button
            icon_exclusive = "RADIOBUT_ON" if is_exclusive else "RADIOBUT_OFF"
            op_exclusive = header_row.operator("light_editor.toggle_group_exclusive", text="", icon=icon_exclusive, emboss=True)
            op_exclusive.group_key = group_key

            # Toggle button for group collapse
            op = header_row.operator("light_editor.toggle_group", text="", icon='TRIA_DOWN' if not collapsed else 'TRIA_RIGHT')
            op.group_key = group_key
            header_row.label(text=grp_name, icon='GROUP')

            if not collapsed:
                for obj in group_objs:
                    draw_main_row(header_box, obj)

def register():
    # Register classes
    bpy.utils.register_class(LG2_AssignLightGroup)
    bpy.utils.register_class(LG2_UnassignLightGroup)
    bpy.utils.register_class(LG2_ResetLightSelection)
    bpy.utils.register_class(LG2_ToggleLightSelection)
    bpy.utils.register_class(LG2_ToggleGroupExclusive)
    bpy.utils.register_class(LG2_ToggleGroup)
    bpy.utils.register_class(LG2_RemoveLightGroup)
    bpy.utils.register_class(LG2_LightGroupPanel)

    # Add a custom property to track selection
    bpy.types.Object.is_selected = bpy.props.BoolProperty(
        name="Is Selected",
        description="Indicates whether the light is selected",
        default=False,
        update=lambda self, context: self.select_set(self.is_selected)  # Sync with actual selection
    )

    # Initialize custom properties for existing lights
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            obj.is_selected = obj.select_get()

def unregister():
    # Remove the custom property
    del bpy.types.Object.is_selected

    # Unregister classes
    bpy.utils.unregister_class(LG2_LightGroupPanel)
    bpy.utils.unregister_class(LG2_ToggleGroup)
    bpy.utils.unregister_class(LG2_ToggleGroupExclusive)
    bpy.utils.unregister_class(LG2_ToggleLightSelection)
    bpy.utils.unregister_class(LG2_ResetLightSelection)
    bpy.utils.unregister_class(LG2_UnassignLightGroup)
    bpy.utils.unregister_class(LG2_AssignLightGroup)
    bpy.utils.unregister_class(LG2_RemoveLightGroup)

if __name__ == "__main__":
    register()