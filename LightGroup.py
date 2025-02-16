import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel
import re

# Global variables to track active checkboxes
current_exclusive_group = None

# Dictionaries to store states
group_checkbox_1_state = {}      # First button on/off per group_key (ON by default)
group_lights_original_state = {} # Stores original light states for each group
group_checkbox_2_state = {}      # Second button on/off per group_key (OFF by default)
other_groups_original_state = {} # Stores other groups' states
group_collapse_dict = {}         # Whether each group is collapsed

class LG_OT_AssignLightGroup(Operator):
    """Assign the selected light group to selected lights."""
    bl_idname = "light_editor.assign_light_group"
    bl_label = "Assign"

    def execute(self, context):
        view_layer = context.view_layer
        if hasattr(view_layer, "lightgroups") and view_layer.active_lightgroup_index < len(view_layer.lightgroups):
            active_group = view_layer.lightgroups[view_layer.active_lightgroup_index]
            selected_lights = [obj for obj in context.selected_objects if obj.type == 'LIGHT']
            for light in selected_lights:
                if hasattr(active_group, 'name'):  # Check if 'name' attribute exists
                    light.lightgroup = active_group.name
                else:
                    self.report({'WARNING'}, "Active light group has no name.")
                    return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "No light group selected or available.")
        
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}

class LG_OT_UnassignLightGroup(Operator):
    """Unassign the selected lights from their current light group."""
    bl_idname = "light_editor.unassign_light_group"
    bl_label = "Unassign"

    def execute(self, context):
        selected_lights = [obj for obj in context.selected_objects if obj.type == 'LIGHT']
        for light in selected_lights:
            light.lightgroup = ""
        
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}

class LG_OT_ResetLightSelection(Operator):
    """Reset the selection of lights."""
    bl_idname = "light_editor.reset_light_selection"
    bl_label = "Reset Light Selection"

    def execute(self, context):
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        self.report({'INFO'}, "Deselected all lights")
        return {'FINISHED'}

def draw_main_row(box, obj):
    """Draws a row of controls for each light in the UI."""
    light = obj.data
    row = box.row(align=True)
    
    # Light enable/disable toggle
    row.prop(obj, "light_enabled", text="", 
             icon="OUTLINER_OB_LIGHT" if obj.light_enabled else "LIGHT_DATA")
    row.active = obj.light_enabled
    
    # Light name
    row.prop(obj, "name", text="")
    
    # Color swatch for light color
    col_color = row.column(align=True)
    col_color.scale_x = 0.25
    if light.use_nodes and light.node_tree:
        color_node = next((node for node in light.node_tree.nodes if node.type == 'EMISSION'), None)
        if color_node:
            col_color.prop(color_node.inputs[0], "default_value", text="")
    else:
        col_color.prop(light, "color", text="")
    
    # Light intensity
    col_energy = row.column(align=True)
    col_energy.scale_x = 0.35
    if light.use_nodes and light.node_tree:
        strength_node = next((node for node in light.node_tree.nodes if node.type == 'EMISSION'), None)
        if strength_node:
            col_energy.prop(strength_node.inputs[1], "default_value", text="")
    else:
        col_energy.prop(light, "energy", text="")

class LG_PT_LightGroupPanel(bpy.types.Panel):
    bl_label = "Light Groups"
    bl_idname = "LG_PT_LightGroupPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Editor"
    bl_options = {'DEFAULT_CLOSED'}
    bl_context = "objectmode"

    @classmethod
    def poll(cls, context):
        # Always return True to make the panel always visible
        return True

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        view_layer = context.view_layer

        if context.scene.render.engine in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            layout.label(text="Light Groups are not supported in Eevee")
            return

        row = layout.row()
        col = row.column()
        col.template_list("UI_UL_list", "lightgroups", view_layer, "lightgroups", view_layer, "active_lightgroup_index", rows=3)
        col = row.column()
        sub = col.column(align=True)
        sub.operator("scene.view_layer_add_lightgroup", icon='ADD', text="")
        sub.operator("scene.view_layer_remove_lightgroup", icon='REMOVE', text="")
        sub.separator()
        sub.menu("VIEWLAYER_MT_lightgroup_sync", icon='DOWNARROW_HLT', text="")

        row = layout.row()
        row.operator("light_editor.assign_light_group", text="Assign")
        row.operator("light_editor.unassign_light_group", text="Unassign")
        row.operator("light_editor.reset_light_selection", text="Reset")  # Reference to the new operator

        groups = {}
        if hasattr(view_layer, "lightgroups"):
            for lg in view_layer.lightgroups:
                # Filter only light objects
                groups[lg.name] = [obj for obj in view_layer.objects if obj.type == 'LIGHT' and getattr(obj, "lightgroup", "") == lg.name and not obj.hide_render]
        # Filter only light objects for the "Not Assigned" group
        not_assigned = [obj for obj in view_layer.objects if obj.type == 'LIGHT' and getattr(obj, "lightgroup", "") not in groups and not obj.hide_render]
        if not_assigned:
            groups["Not Assigned"] = not_assigned

        for grp_name, group_objs in groups.items():
            group_key = f"group_{grp_name}"
            collapsed = group_collapse_dict.get(group_key, False)
            header_box = layout.box()
            header_row = header_box.row(align=True)
            is_on_2 = group_checkbox_2_state.get(group_key, False)
            icon_2 = 'RADIOBUT_ON' if is_on_2 else 'RADIOBUT_OFF'
            op_2 = header_row.operator("light_editor.toggle_group_exclusive", text="", icon=icon_2, depress=is_on_2)
            op_2.group_key = group_key
            op_tri = header_row.operator("light_editor.toggle_group", text="", emboss=True, icon='DOWNARROW_HLT' if not collapsed else 'RIGHTARROW')
            op_tri.group_key = group_key
            header_row.label(text=grp_name, icon='GROUP')
            if not collapsed:
                for obj in group_objs:
                    draw_main_row(header_box, obj)

def register():
    bpy.utils.register_class(LG_OT_AssignLightGroup)
    bpy.utils.register_class(LG_OT_UnassignLightGroup)
    bpy.utils.register_class(LG_OT_ResetLightSelection)  # Register the new operator
    bpy.utils.register_class(LG_PT_LightGroupPanel)

def unregister():
    bpy.utils.unregister_class(LG_PT_LightGroupPanel)
    bpy.utils.unregister_class(LG_OT_UnassignLightGroup)
    bpy.utils.unregister_class(LG_OT_AssignLightGroup)
    bpy.utils.unregister_class(LG_OT_ResetLightSelection)  # Unregister the new operator