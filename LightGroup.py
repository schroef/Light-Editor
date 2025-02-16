import bpy
from bpy.types import Operator, Panel

# Global dictionaries for group states, moved to Scene for persistence
bpy.types.Scene.group_collapse_dict = {}
bpy.types.Scene.group_exclusive_dict = {}

# -------------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------------
class LG_AssignLightGroup(Operator):
    """Assign the selected light group to selected lights."""
    bl_idname = "lg_editor.assign_light_group"
    bl_label = "Assign"

    def execute(self, context):
        view_layer = context.view_layer
        if (hasattr(view_layer, "lightgroups")
                and view_layer.active_lightgroup_index >= 0
                and view_layer.active_lightgroup_index < len(view_layer.lightgroups)):
            active_group = view_layer.lightgroups[view_layer.active_lightgroup_index]
            selected_lights = [obj for obj in context.selected_objects if obj.type == 'LIGHT']
            for light in selected_lights:
                light.lightgroup = active_group.name

            bpy.ops.lg_editor.reset_light_selection()
        else:
            self.report({'WARNING'}, "No light group selected or available.")
        return {'FINISHED'}


class LG_UnassignLightGroup(Operator):
    """Unassign the selected lights from their current light group."""
    bl_idname = "lg_editor.unassign_light_group"
    bl_label = "Unassign"

    def execute(self, context):
        selected_lights = [obj for obj in context.selected_objects if obj.type == 'LIGHT']
        for light in selected_lights:
            light.lightgroup = ""

        bpy.ops.lg_editor.reset_light_selection()
        return {'FINISHED'}


class LG_ResetLightSelection(Operator):
    """Reset the selection of lights."""
    bl_idname = "lg_editor.reset_light_selection"
    bl_label = "Reset Light Selection"

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        for obj in context.scene.objects:
            if obj.type == 'LIGHT':
                obj.is_selected = False

        self.report({'INFO'}, "Deselected all lights")
        return {'FINISHED'}


class LG_ToggleLightSelection(Operator):
    """Toggle selection for an individual light."""
    bl_idname = "lg_editor.toggle_light_selection"
    bl_label = "Toggle Light Selection"

    light_name: bpy.props.StringProperty()

    def execute(self, context):
        light_obj = context.scene.objects.get(self.light_name)
        if light_obj:
            light_obj.is_selected = not light_obj.is_selected
        else:
            self.report({'WARNING'}, f"Light '{self.light_name}' not found.")
        return {'FINISHED'}


class LG_ToggleGroupExclusive(Operator):
    """Toggle exclusive activation of this group."""
    bl_idname = "lg_editor.toggle_group_exclusive"
    bl_label = "Toggle Group Exclusive"

    group_key: bpy.props.StringProperty()

    def execute(self, context):
        is_exclusive = not context.scene.group_exclusive_dict.get(self.group_key, False)
        context.scene.group_exclusive_dict[self.group_key] = is_exclusive

        if is_exclusive:
            exclusive_group_name = self.group_key.replace("group_", "")
            for obj in context.scene.objects:
                if obj.type == 'LIGHT':
                    obj.hide_viewport = getattr(obj, "lightgroup", "") != exclusive_group_name
        else:
            for obj in context.scene.objects:
                if obj.type == 'LIGHT':
                    obj.hide_viewport = False
        return {'FINISHED'}


class LG_ToggleGroup(Operator):
    """Toggle the collapse state of a group."""
    bl_idname = "lg_editor.toggle_group"
    bl_label = "Toggle Group"
    group_key: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.group_collapse_dict[self.group_key] = not context.scene.group_collapse_dict.get(self.group_key, False)
        return {'FINISHED'}


class LG_AddLightGroup(Operator):
    """Add a new light group in the current view_layer."""
    bl_idname = "lg_editor.add_light_group"
    bl_label = "Add Light Group"

    def execute(self, context):
        view_layer = context.view_layer
        if not hasattr(view_layer, "lightgroups"):
            self.report({'WARNING'}, "This Blender version doesn't support per‐view‐layer lightgroups.")
            return {'CANCELLED'}

        new_group = view_layer.lightgroups.add()
        new_group.name = "NewGroup"
        view_layer.active_lightgroup_index = len(view_layer.lightgroups) - 1
        return {'FINISHED'}


class LG_RemoveLightGroup(Operator):
    """Remove the selected light group."""
    bl_idname = "lg_editor.remove_light_group"
    bl_label = "Remove Light Group"

    def execute(self, context):
        view_layer = context.view_layer
        if (hasattr(view_layer, "lightgroups")
                and view_layer.active_lightgroup_index >= 0
                and view_layer.active_lightgroup_index < len(view_layer.lightgroups)):
            active_group_name = view_layer.lightgroups[view_layer.active_lightgroup_index].name

            for obj in context.scene.objects:
                if obj.type == 'LIGHT' and getattr(obj, "lightgroup", "") == active_group_name:
                    obj.lightgroup = ""

            view_layer.lightgroups.remove(view_layer.active_lightgroup_index)

            group_key = f"group_{active_group_name}"
            context.scene.group_collapse_dict.pop(group_key, None)
            context.scene.group_exclusive_dict.pop(group_key, None)

            if view_layer.active_lightgroup_index >= len(view_layer.lightgroups):
                view_layer.active_lightgroup_index = len(view_layer.lightgroups) - 1

            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        return {'FINISHED'}


def draw_main_row(box, obj):
    row = box.row(align=True)
    row.prop(obj, "is_selected", text="", emboss=True, icon='NONE')
    row.prop(obj, "name", text="")


class LG_PT_LightGroupPanel(Panel):
    bl_label = "Light Groups"
    bl_idname = "LG_PT_light_group_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Editor"

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        view_layer = context.view_layer

        row = layout.row(align=True)
        col = row.column()
        if hasattr(view_layer, "lightgroups"):
            col.template_list("UI_UL_list", "lightgroups", view_layer, "lightgroups",
                              view_layer, "active_lightgroup_index", rows=3)
            col = row.column(align=True)
            col.operator("lg_editor.add_light_group", icon='ADD', text="")
            col.operator("lg_editor.remove_light_group", icon='REMOVE', text="")
        else:
            col.label(text="No Lightgroups in this Blender version", icon='ERROR')

        row = layout.row(align=True)
        row.operator("lg_editor.assign_light_group", text="Assign")
        row.operator("lg_editor.unassign_light_group", text="Unassign")
        row.operator("lg_editor.reset_light_selection", text="Reset")

        groups = {}
        if hasattr(view_layer, "lightgroups"):
            for lg in view_layer.lightgroups:
                lights_in_group = [
                    obj for obj in context.scene.objects
                    if obj.type == 'LIGHT'
                       and not obj.hide_render
                       and getattr(obj, "lightgroup", "") == lg.name
                ]
                groups[lg.name] = lights_in_group

        not_assigned = [
            obj for obj in context.scene.objects
            if obj.type == 'LIGHT'
               and not obj.hide_render
               and not getattr(obj, "lightgroup", "")
        ]
        if not_assigned:
            groups["Not Assigned"] = not_assigned

        for grp_name, group_objs in groups.items():
            group_key = f"group_{grp_name}"
            collapsed = context.scene.group_collapse_dict.get(group_key, False)
            is_exclusive = context.scene.group_exclusive_dict.get(group_key, False)

            header_box = layout.box()
            header_row = header_box.row(align=True)

            icon_exclusive = "RADIOBUT_ON" if is_exclusive else "RADIOBUT_OFF"
            op_exclusive = header_row.operator("lg_editor.toggle_group_exclusive", text="",
                                               icon=icon_exclusive, emboss=True)
            op_exclusive.group_key = group_key

            icon_arrow = 'TRIA_DOWN' if not collapsed else 'TRIA_RIGHT'
            op = header_row.operator("lg_editor.toggle_group", text="", icon=icon_arrow)
            op.group_key = group_key

            header_row.label(text=grp_name, icon='GROUP')

            if not collapsed:
                for obj in group_objs:
                    draw_main_row(header_box, obj)


classes = (
    LG_AssignLightGroup,
    LG_UnassignLightGroup,
    LG_ResetLightSelection,
    LG_ToggleLightSelection,
    LG_ToggleGroupExclusive,
    LG_ToggleGroup,
    LG_AddLightGroup,
    LG_RemoveLightGroup,
    LG_PT_LightGroupPanel,
)


def register():

    bpy.types.Object.is_selected = bpy.props.BoolProperty(
        name="Is Selected",
        description="Indicates whether the light is selected",
        default=False,
        update=lambda self, context: self.select_set(self.is_selected)
    )

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    del bpy.types.Object.is_selected
    del bpy.types.Scene.group_collapse_dict
    del bpy.types.Scene.group_exclusive_dict

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()