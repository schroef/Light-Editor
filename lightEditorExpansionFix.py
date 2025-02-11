import bpy
import fnmatch
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
)

# Global variables to track active checkboxes
current_active_light = None
current_exclusive_group = None

# Dictionaries to store states
group_checkbox_1_state = {}      # First button on/off per group_key (ON by default)
group_lights_original_state = {} # Stores original light states for each group
group_checkbox_2_state = {}      # Second button on/off per group_key (OFF by default)
other_groups_original_state = {} # Stores other groups' states
group_collapse_dict = {}         # Whether each group is collapsed


# -------------------------------------------------------------------------
# Load light linking editor
# -------------------------------------------------------------------------

class LIGHT_OT_LoadLinkingEditor(bpy.types.Operator):
    """Load the Light Linking Editor UI"""
    bl_idname = "light_editor.load_linking_editor"
    bl_label = "Load Light Linking Editor"

    def execute(self, context):
        import importlib
        from . import Linking  # Adjust this import if necessary
        importlib.reload(Linking)
        # Unregister the current panel so the Linking UI can take over.
        bpy.utils.unregister_class(LIGHT_PT_editor)
        # Register the Linking UI (assuming Linking.py defines its own register() function)
        Linking.register()
        return {'FINISHED'}



# -------------------------------------------------------------------------
# Add a new operator for deleting a light group
# -------------------------------------------------------------------------
class LIGHT_OT_DeleteLightGroup(bpy.types.Operator):
    """Delete the selected light group."""
    bl_idname = "light_editor.delete_light_group"
    bl_label = "Delete Light Group"

    def execute(self, context):
        scene = context.scene
        selected_group = scene.light_editor_delete_group

        if selected_group == "NoGroup":
            self.report({'WARNING'}, "No group selected.")
            return {'CANCELLED'}

        # Remove the group from all lights (use context.view_layer.objects)
        for obj in context.view_layer.objects:
            if obj.type == 'LIGHT' and getattr(obj, "custom_lightgroup", "") == selected_group:
                obj.custom_lightgroup = ""
                obj.custom_lightgroup_menu = "NoGroup"

        # Remove the group from the scene's custom_lightgroups_list
        if hasattr(scene, "custom_lightgroups_list") and scene.custom_lightgroups_list:
            groups = [g.strip() for g in scene.custom_lightgroups_list.split(",") if g.strip()]
            if selected_group in groups:
                groups.remove(selected_group)
                scene.custom_lightgroups_list = ", ".join(groups)

        self.report({'INFO'}, f"Deleted light group '{selected_group}'")
        return {'FINISHED'}

# -------------------------------------------------------------------------
# 1) Functions for custom light group handling
# -------------------------------------------------------------------------
def get_light_groups(context):
    """
    Loop through all objects, find lights, and collect them by their custom light group.
    If a light already has an old "lightgroup" value, it is used.
    Also include any groups stored in the scene property.
    Returns a dictionary mapping group names to lists of light object names.
    """
    groups = {}
    for obj in context.view_layer.objects:
        if obj.type == 'LIGHT':
            # Try the new property; if empty, fallback to old property.
            group_val = getattr(obj, "custom_lightgroup", "")
            if not group_val:
                group_val = getattr(obj, "lightgroup", "")
            if group_val:
                groups.setdefault(group_val, []).append(obj.name)
    # Get any groups created via the operator (even if no light has that assignment)
    scene = context.scene
    if hasattr(scene, "custom_lightgroups_list") and scene.custom_lightgroups_list:
        extra_groups = [g.strip() for g in scene.custom_lightgroups_list.split(",") if g.strip()]
        for g in extra_groups:
            if g not in groups:
                groups[g] = []  # no lights assigned yet
    return groups

def get_light_group_items(self, context):
    """Return a list of custom light group items for the EnumProperty."""
    items = [("NoGroup", "No Group", "")]
    groups = get_light_groups(context)  # Pass context to get_light_groups
    for group_name in groups.keys():
        if group_name != "NoGroup":
            items.append((group_name, group_name, ""))
    return items
def get_light_group_items(self, context):
    """Return a list of custom light group items for the EnumProperty."""
    items = [("NoGroup", "No Group", "")]
    groups = get_light_groups(context)  # Pass context to get_light_groups
    for group_name in groups.keys():
        if group_name != "NoGroup":
            items.append((group_name, group_name, ""))
    return items

def update_lightgroup_menu(self, context):
    """When the menu selection changes, copy the value into our custom_lightgroup property."""
    self.custom_lightgroup = self.custom_lightgroup_menu

def view_layer_items(self, context):
    """Return a list of view layer items for the EnumProperty."""
    items = []
    for view_layer in context.scene.view_layers:
        items.append((view_layer.name, view_layer.name, ""))
    return items

def update_light_enabled(self, context):
    self.hide_viewport = not self.light_enabled
    self.hide_render = not self.light_enabled

def update_light_turn_off_others(self, context):
    scene = context.scene
    if self.light_turn_off_others:
        if scene.current_active_light and scene.current_active_light != self:
            scene.current_active_light.light_turn_off_others = False
        scene.current_active_light = self
        # Use objects from the active view layer
        for obj in context.view_layer.objects:
            if obj.type == 'LIGHT' and obj.name != self.name:
                if 'prev_light_enabled' not in obj:
                    obj['prev_light_enabled'] = obj.light_enabled
                obj.light_enabled = False
    else:
        if scene.current_active_light == self:
            scene.current_active_light = None
        for obj in context.view_layer.objects:
            if obj.type == 'LIGHT' and obj.name != self.name:
                if 'prev_light_enabled' in obj:
                    obj.light_enabled = obj['prev_light_enabled']
                    del obj['prev_light_enabled']

# --- MUTUALLY EXCLUSIVE GROUPING TOGGLES ---
def update_group_by_kind(self, context):
    if self.light_editor_kind_alpha:
        self.light_editor_group_by_collection = False
        self.light_editor_light_group = False

def update_group_by_collection(self, context):
    if self.light_editor_group_by_collection:
        self.light_editor_kind_alpha = False
        self.light_editor_light_group = False

def update_light_group(self, context):
    if self.light_editor_light_group:
        self.light_editor_kind_alpha = False
        self.light_editor_group_by_collection = False
        
        # Collapse all expanded lights when switching to "By Light Groups" mode
        for obj in context.view_layer.objects:
            if obj.type == 'LIGHT':
                obj.light_expanded = False
# -------------------------------------------------------------------------
# 2) Extra parameters drawing function (unchanged)
# -------------------------------------------------------------------------
def draw_extra_params(box, obj, light):
    if light.type in {'POINT', 'SPOT'}:
        row = box.row(align=True)
        row.label(text="Soft Falloff:")
        row.prop(light, "soft_falloff", text="")
        row = box.row(align=True)
        row.label(text="Radius:")
        row.prop(light, "shadow_soft_size", text="")
        row = box.row(align=True)
        row.label(text="Max Bounce:")
        row.prop(light, "max_bounce", text="")
        row = box.row(align=True)
        row.label(text="Cast Shadow:")
        row.prop(light, "use_shadow", text="")
        row = box.row(align=True)
        row.label(text="Multiple Inst:")
        row.prop(light, "multiple_instance", text="")
        row = box.row(align=True)
        row.label(text="Shadow Caustic:")
        row.prop(light, "shadow_caustic", text="")
        if light.type == 'SPOT':
            row = box.row(align=True)
            row.label(text="Spot Size:")
            row.prop(light, "spot_size", text="")
            row = box.row(align=True)
            row.label(text="Blende:")
            row.prop(light, "spot_blend", text="")
            row = box.row(align=True)
            row.label(text="Show Cone:")
            row.prop(light, "show_cone", text="")
    elif light.type == 'SUN':
        row = box.row(align=True)
        row.label(text="Angle:")
        row.prop(light, "angle", text="")
        row = box.row(align=True)
        row.label(text="Max Bounce:")
        row.prop(light, "max_bounce", text="")
        row = box.row(align=True)
        row.label(text="Cast Shadow:")
        row.prop(light, "use_shadow", text="")
        row = box.row(align=True)
        row.label(text="Multiple Inst:")
        row.prop(light, "multiple_instance", text="")
        row = box.row(align=True)
        row.label(text="Shadow Caustic:")
        row.prop(light, "shadow_caustic", text="")
    elif light.type == 'AREA':
        row = box.row(align=True)
        row.label(text="Shape:")
        row.prop(light, "shape", text="")
        row = box.row(align=True)
        row.label(text="Size X:")
        row.prop(light, "size", text="")
        row = box.row(align=True)
        row.label(text="Size Y:")
        row.prop(light, "size_y", text="")
        row = box.row(align=True)
        row.label(text="Max Bounce:")
        row.prop(light, "max_bounce", text="")
        row = box.row(align=True)
        row.label(text="Cast Shadow:")
        row.prop(light, "use_shadow", text="")
        row = box.row(align=True)
        row.label(text="Multi Imp:")
        row.prop(light, "use_multiple_importance", text="")
        row = box.row(align=True)
        row.label(text="Shadow Caustics:")
        row.prop(light, "shadow_caustic", text="")
        row = box.row(align=True)
        row.label(text="Portal:")
        if hasattr(light, "cycles"):
            row.prop(light.cycles, "is_portal", text="")
        else:
            row.label(text="-")
        row = box.row(align=True)
        row.label(text="Spread:")
        row.prop(light, "spread", text="")

# -------------------------------------------------------------------------
# 3) Operator: Add Lightgroup
# This operator now works even if no light is selected.
# When executed it assigns the new group name to the active light (if one exists)
# or adds the group name to the scene's custom_lightgroups_list.
# -------------------------------------------------------------------------
class LIGHT_OT_CreateNewLightgroup(bpy.types.Operator):
    """Add a new lightgroup and assign it (if a light is selected) or store it for later use."""
    bl_idname = "light_editor.create_new_lightgroup"
    bl_label = "Add Lightgroup"

    def execute(self, context):
        scene = context.scene
        new_group = scene.create_new_lightgroup.strip()
        if not new_group:
            self.report({'WARNING'}, "No group name entered.")
            return {'CANCELLED'}
        active_obj = context.active_object
        if active_obj and active_obj.type == 'LIGHT':
            active_obj.custom_lightgroup = new_group
            active_obj.custom_lightgroup_menu = new_group
            self.report({'INFO'}, f"Assigned group '{new_group}' to {active_obj.name}")
        else:
            # No active light: add the group name to the scene list (if not already present)
            current_list = scene.custom_lightgroups_list
            groups = [g.strip() for g in current_list.split(",") if g.strip()] if current_list else []
            if new_group not in groups:
                groups.append(new_group)
                scene.custom_lightgroups_list = ", ".join(groups)
            self.report({'INFO'}, f"Created light group '{new_group}'")
        scene.create_new_lightgroup = ""
        return {'FINISHED'}

# -------------------------------------------------------------------------
# 4) Operators for group toggling (object access updated)
# -------------------------------------------------------------------------
class LIGHT_OT_ToggleGroup(bpy.types.Operator):
    """Collapse or expand a group header."""
    bl_idname = "light_editor.toggle_group"
    bl_label = "Toggle Group"
    group_key: StringProperty()

    def execute(self, context):
        current = group_collapse_dict.get(self.group_key, False)
        group_collapse_dict[self.group_key] = not current
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}

class LIGHT_OT_ToggleGroupAllOff(bpy.types.Operator):
    """Toggle all lights in the group off or restore them."""
    bl_idname = "light_editor.toggle_group_all_off"
    bl_label = "Toggle Group All Off"
    group_key: StringProperty()

    def execute(self, context):
        global group_checkbox_1_state, group_lights_original_state
        is_on = group_checkbox_1_state.get(self.group_key, True)
        group_objs = self._get_group_objects(context, self.group_key)
        if is_on:
            original_states = {}
            for obj in group_objs:
                original_states[obj.name] = obj.light_enabled
            group_lights_original_state[self.group_key] = original_states
            for obj in group_objs:
                obj.light_enabled = False
            group_checkbox_1_state[self.group_key] = False
        else:
            original_states = group_lights_original_state.get(self.group_key, {})
            for obj in group_objs:
                obj.light_enabled = original_states.get(obj.name, True)
            if self.group_key in group_lights_original_state:
                del group_lights_original_state[self.group_key]
            group_checkbox_1_state[self.group_key] = True
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}

    def _get_group_objects(self, context, group_key):
        scene = context.scene
        filter_pattern = scene.light_editor_filter.lower()
        if filter_pattern:
            all_lights = [obj for obj in context.view_layer.objects
                          if obj.type == 'LIGHT' and fnmatch.fnmatch(obj.name.lower(), filter_pattern)]
        else:
            all_lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']
        if scene.light_editor_group_by_collection and group_key.startswith("coll_"):
            coll_name = group_key[5:]
            return [obj for obj in all_lights
                    if (obj.users_collection and obj.users_collection[0].name == coll_name)
                    or (not obj.users_collection and coll_name == "No Collection")]
        if scene.light_editor_kind_alpha and group_key.startswith("kind_"):
            kind = group_key[5:]
            return [obj for obj in all_lights if obj.data.type == kind]
        if scene.light_editor_light_group and group_key.startswith("group_"):
            group_name = group_key[6:]
            return [obj for obj in all_lights if getattr(obj, "custom_lightgroup", "") == group_name]
        return []

class LIGHT_OT_ToggleGroupExclusive(bpy.types.Operator):
    """
    Toggle exclusive mode for a group.
    When turned on, lights in other groups are turned off.
    """
    bl_idname = "light_editor.toggle_group_exclusive"
    bl_label = "Toggle Group Exclusive"
    group_key: StringProperty()

    def execute(self, context):
        global current_exclusive_group, group_checkbox_2_state, other_groups_original_state
        is_on = group_checkbox_2_state.get(self.group_key, False)
        if not is_on:
            if current_exclusive_group and current_exclusive_group != self.group_key:
                group_checkbox_2_state[current_exclusive_group] = False
                saved_dict = other_groups_original_state.get(current_exclusive_group, {})
                for gk, light_dict in saved_dict.items():
                    grp_objs = self._get_group_objects(context, gk)
                    for obj in grp_objs:
                        obj.light_enabled = light_dict.get(obj.name, True)
                if current_exclusive_group in other_groups_original_state:
                    del other_groups_original_state[current_exclusive_group]
            others = self._get_all_other_groups(context, self.group_key)
            saved_dict = {}
            for gk in others:
                grp_objs = self._get_group_objects(context, gk)
                saved_dict[gk] = {obj.name: obj.light_enabled for obj in grp_objs}
                for obj in grp_objs:
                    obj.light_enabled = False
            other_groups_original_state[self.group_key] = saved_dict
            group_checkbox_2_state[self.group_key] = True
            current_exclusive_group = self.group_key
        else:
            saved_dict = other_groups_original_state.get(self.group_key, {})
            for gk, light_dict in saved_dict.items():
                grp_objs = self._get_group_objects(context, gk)
                for obj in grp_objs:
                    obj.light_enabled = light_dict.get(obj.name, True)
            if self.group_key in other_groups_original_state:
                del other_groups_original_state[self.group_key]
            group_checkbox_2_state[self.group_key] = False
            current_exclusive_group = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}

    def _get_all_other_groups(self, context, current_key):
        return [k for k in self._get_all_group_keys(context) if k != current_key]

    def _get_all_group_keys(self, context):
        scene = context.scene
        filter_pattern = scene.light_editor_filter.lower()
        if filter_pattern:
            lights = [obj for obj in context.view_layer.objects
                      if obj.type == 'LIGHT' and fnmatch.fnmatch(obj.name.lower(), filter_pattern)]
        else:
            lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']
        group_keys = set()
        if scene.light_editor_group_by_collection:
            for obj in lights:
                if obj.users_collection:
                    coll_name = obj.users_collection[0].name
                else:
                    coll_name = "No Collection"
                group_keys.add(f"coll_{coll_name}")
        elif scene.light_editor_kind_alpha:
            tmap = {'POINT': [], 'SPOT': [], 'SUN': [], 'AREA': []}
            for obj in lights:
                if obj.data.type in tmap:
                    tmap[obj.data.type].append(obj)
            for kind, items in tmap.items():
                if items:
                    group_keys.add(f"kind_{kind}")
        elif scene.light_editor_light_group:
            for obj in lights:
                group_name = getattr(obj, "custom_lightgroup", "")
                if group_name:
                    group_keys.add(f"group_{group_name}")
        return list(group_keys)

    def _get_group_objects(self, context, group_key):
        scene = context.scene
        filter_pattern = scene.light_editor_filter.lower()
        if filter_pattern:
            all_lights = [obj for obj in context.view_layer.objects
                          if obj.type == 'LIGHT' and fnmatch.fnmatch(obj.name.lower(), filter_pattern)]
        else:
            all_lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']
        if scene.light_editor_group_by_collection and group_key.startswith("coll_"):
            coll_name = group_key[5:]
            return [obj for obj in all_lights
                    if (obj.users_collection and obj.users_collection[0].name == coll_name)
                    or (not obj.users_collection and coll_name == "No Collection")]
        if scene.light_editor_kind_alpha and group_key.startswith("kind_"):
            kind = group_key[5:]
            return [obj for obj in all_lights if obj.data.type == kind]
        if scene.light_editor_light_group and group_key.startswith("group_"):
            group_name = group_key[6:]
            return [obj for obj in all_lights if getattr(obj, "custom_lightgroup", "") == group_name]
        return []

# -------------------------------------------------------------------------
# 4) The main row UI: use custom_lightgroup property when in Light Group mode
# -------------------------------------------------------------------------
def draw_main_row(box, obj):
    light = obj.data
    scene = bpy.context.scene
    row = box.row(align=True)
    controls_row = row.row(align=True)
    
    # The enabled and "turn off others" toggles remain:
    controls_row.prop(obj, "light_enabled", text="",
                      icon="CHECKBOX_HLT" if obj.light_enabled else "CHECKBOX_DEHLT")
    controls_row.prop(obj, "light_turn_off_others", text="",
                      icon="RADIOBUT_ON" if obj.light_turn_off_others else "RADIOBUT_OFF")

    # -- Only show the triangle if NOT in Light Group mode --
    if not scene.light_editor_light_group:
        controls_row.prop(obj, "light_expanded", text="",
                          emboss=True,
                          icon='TRIA_DOWN' if obj.light_expanded else 'TRIA_RIGHT')
    
    col_name = row.column(align=True)
    col_name.scale_x = 0.5
    col_name.prop(obj, "name", text="")

    if scene.light_editor_light_group:
        col_group = row.column(align=True)
        col_group.scale_x = 0.6
        col_group.prop(obj, "custom_lightgroup_menu", text="")
    else:
        col_color = row.column(align=True)
        col_color.scale_x = 0.25
        col_color.prop(light, "color", text="")
        col_energy = row.column(align=True)
        col_energy.scale_x = 0.35
        col_energy.prop(light, "energy", text="")

# -------------------------------------------------------------------------
# 5) The main panel
# -------------------------------------------------------------------------
class LIGHT_PT_editor(bpy.types.Panel):
    """Panel to view/edit lights with grouping, filtering, and per‐group toggles."""
    bl_label = "Light Editor"
    bl_idname = "LIGHT_PT_editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Light Editor"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Top toggles with new labels.
        row = layout.row(align=True)
        row.prop(scene, "light_editor_kind_alpha", text="By Kind")
        row.prop(scene, "light_editor_group_by_collection", text="By Collections")
        row.prop(scene, "light_editor_light_group", text="By Light Groups")
        layout.prop(scene, "light_editor_filter", text="Filter")

        # Only show these rows if in Light Group mode.
        if scene.light_editor_light_group:
            # Row for adding a new light group.
            row = layout.row(align=True)
            row.prop(scene, "create_new_lightgroup", text="")
            row.operator("light_editor.create_new_lightgroup", text="Add Lightgroup")

            # Row for selecting and deleting a light group.
            row = layout.row(align=True)
            row.prop(scene, "light_editor_delete_group", text="")
            row.operator("light_editor.delete_light_group", text="Delete Light Group")

        # Get lights from the active view layer
        if scene.light_editor_filter:
            lights = [obj for obj in context.view_layer.objects
                      if obj.type == 'LIGHT' and fnmatch.fnmatch(obj.name.lower(), scene.light_editor_filter.lower())]
        else:
            lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']

        if scene.light_editor_group_by_collection:
            # Group by collection logic
            groups = {}
            for obj in lights:
                if obj.users_collection:
                    group_name = obj.users_collection[0].name
                else:
                    group_name = "No Collection"
                groups.setdefault(group_name, []).append(obj)
            for group_name, group_objs in groups.items():
                group_key = f"coll_{group_name}"
                collapsed = group_collapse_dict.get(group_key, False)
                header_box = layout.box()
                header_row = header_box.row(align=True)
                is_on_1 = group_checkbox_1_state.get(group_key, True)
                icon_1 = 'CHECKBOX_HLT' if is_on_1 else 'CHECKBOX_DEHLT'
                op_1 = header_row.operator("light_editor.toggle_group_all_off",
                                           text="",
                                           icon=icon_1,
                                           depress=is_on_1)
                op_1.group_key = group_key
                is_on_2 = group_checkbox_2_state.get(group_key, False)
                icon_2 = 'RADIOBUT_ON' if is_on_2 else 'RADIOBUT_OFF'
                op_2 = header_row.operator("light_editor.toggle_group_exclusive",
                                           text="",
                                           icon=icon_2,
                                           depress=is_on_2)
                op_2.group_key = group_key
                op_tri = header_row.operator("light_editor.toggle_group",
                                             text="",
                                             emboss=True,
                                             icon='TRIA_RIGHT' if collapsed else 'TRIA_DOWN')
                op_tri.group_key = group_key
                header_row.label(text=group_name, icon='OUTLINER_COLLECTION')
                if not collapsed:
                    for obj in group_objs:
                        draw_main_row(header_box, obj)
                        if obj.light_expanded:
                            extra_box = header_box.box()
                            extra_box.label(text="Extra Parameters:")
                            draw_extra_params(extra_box, obj, obj.data)

        elif scene.light_editor_kind_alpha:
            # Group by kind logic
            groups = {'POINT': [], 'SPOT': [], 'SUN': [], 'AREA': []}
            for obj in lights:
                if obj.data.type in groups:
                    groups[obj.data.type].append(obj)
            for kind in ('POINT', 'SPOT', 'SUN', 'AREA'):
                if groups[kind]:
                    group_key = f"kind_{kind}"
                    collapsed = group_collapse_dict.get(group_key, False)
                    header_box = layout.box()
                    header_row = header_box.row(align=True)
                    is_on_1 = group_checkbox_1_state.get(group_key, True)
                    icon_1 = 'CHECKBOX_HLT' if is_on_1 else 'CHECKBOX_DEHLT'
                    op_1 = header_row.operator("light_editor.toggle_group_all_off",
                                               text="",
                                               icon=icon_1,
                                               depress=is_on_1)
                    op_1.group_key = group_key
                    is_on_2 = group_checkbox_2_state.get(group_key, False)
                    icon_2 = 'RADIOBUT_ON' if is_on_2 else 'RADIOBUT_OFF'
                    op_2 = header_row.operator("light_editor.toggle_group_exclusive",
                                               text="",
                                               icon=icon_2,
                                               depress=is_on_2)
                    op_2.group_key = group_key
                    op_tri = header_row.operator("light_editor.toggle_group",
                                                 text="",
                                                 emboss=True,
                                                 icon='TRIA_RIGHT' if collapsed else 'TRIA_DOWN')
                    op_tri.group_key = group_key
                    header_row.label(text=f"{kind} Lights", icon='LIGHT_DATA')
                    if not collapsed:
                        for obj in groups[kind]:
                            draw_main_row(header_box, obj)
                            if obj.light_expanded:
                                extra_box = header_box.box()
                                extra_box.label(text="Extra Parameters:")
                                draw_extra_params(extra_box, obj, obj.data)

        elif scene.light_editor_light_group:
            # Group by light group logic
            groups = {}
            for obj in lights:
                grp = getattr(obj, "custom_lightgroup", "")
                if not grp:
                    grp = getattr(obj, "lightgroup", "")
                if not grp:
                    grp = "NoGroup"
                groups.setdefault(grp, []).append(obj)
            for grp_name, group_objs in groups.items():
                group_key = f"group_{grp_name}"
                collapsed = group_collapse_dict.get(group_key, False)
                header_box = layout.box()
                header_row = header_box.row(align=True)
                is_on_1 = group_checkbox_1_state.get(group_key, True)
                icon_1 = 'CHECKBOX_HLT' if is_on_1 else 'CHECKBOX_DEHLT'
                op_1 = header_row.operator("light_editor.toggle_group_all_off",
                                           text="",
                                           icon=icon_1,
                                           depress=is_on_1)
                op_1.group_key = group_key
                is_on_2 = group_checkbox_2_state.get(group_key, False)
                icon_2 = 'RADIOBUT_ON' if is_on_2 else 'RADIOBUT_OFF'
                op_2 = header_row.operator("light_editor.toggle_group_exclusive",
                                           text="",
                                           icon=icon_2,
                                           depress=is_on_2)
                op_2.group_key = group_key
                op_tri = header_row.operator("light_editor.toggle_group",
                                             text="",
                                             emboss=True,
                                             icon='TRIA_RIGHT' if collapsed else 'TRIA_DOWN')
                op_tri.group_key = group_key
                header_row.label(text=f"{grp_name}", icon='GROUP')
                if not collapsed:
                    for obj in group_objs:
                        draw_main_row(header_box, obj)
                        if obj.light_expanded:
                            extra_box = header_box.box()
                            extra_box.label(text="Extra Parameters:")
                            draw_extra_params(extra_box, obj, obj.data)

        else:
            # Alphabetical order mode
            sorted_lights = sorted(lights, key=lambda o: o.name.lower())
            box = layout.box()
            box.label(text="All Lights (Alphabetical)", icon='LIGHT_DATA')
            for obj in sorted_lights:
                draw_main_row(box, obj)
                if obj.light_expanded:  # Check if the light is expanded
                    extra_box = box.box()
                    extra_box.label(text="Extra Parameters:")
                    draw_extra_params(extra_box, obj, obj.data)  # Draw extra parameters

        layout.separator()
        layout.operator("light_editor.load_linking_editor", text="Light Linking Editor", icon='FILE_SCRIPT')
        
# Register the new operator and property
classes = (
    LIGHT_OT_ToggleGroup,
    LIGHT_OT_ToggleGroupAllOff,
    LIGHT_OT_ToggleGroupExclusive,
    LIGHT_OT_CreateNewLightgroup,
    LIGHT_OT_DeleteLightGroup,
    LIGHT_OT_LoadLinkingEditor,  # <-- Added here
    LIGHT_PT_editor,
)

def register():
    # Register scene properties
    bpy.types.Scene.current_active_light = bpy.props.PointerProperty(type=bpy.types.Object)
    bpy.types.Scene.current_exclusive_group = bpy.props.StringProperty()

    # Register other classes and properties
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register other properties (as shown in your original code)
    bpy.types.Scene.light_editor_filter = StringProperty(
        name="Filter",
        default="",
        description="Filter lights by name (wildcards allowed)"
    )
    bpy.types.Scene.light_editor_kind_alpha = BoolProperty(
        name="By Kind",
        description="Group lights by kind",
        default=False,
        update=update_group_by_kind
    )
    bpy.types.Scene.light_editor_group_by_collection = BoolProperty(
        name="By Collections",
        description="Group lights by collection",
        default=False,
        update=update_group_by_collection
    )
    bpy.types.Scene.light_editor_light_group = BoolProperty(
        name="By Light Groups",
        description="Group lights by their custom light group assignment",
        default=False,
        update=update_light_group
    )
    bpy.types.Scene.create_new_lightgroup = StringProperty(
        name="",
        default="",
        description="Enter a new light group name"
    )
    bpy.types.Scene.custom_lightgroups_list = StringProperty(
        name="Custom Lightgroups",
        default="",
        description="Comma separated list of custom light groups created without an active light"
    )
    
    bpy.types.Scene.light_editor_delete_group = EnumProperty(
        name="Delete Light Group",
        description="Select a light group to delete",
        items=get_light_group_items  # Pass the function directly (no parentheses)
    )

    # Register Light properties
    bpy.types.Light.soft_falloff = BoolProperty(default=False)
    bpy.types.Light.max_bounce = IntProperty(default=0, min=0, max=10)
    bpy.types.Light.multiple_instance = BoolProperty(default=False)
    bpy.types.Light.shadow_caustic = BoolProperty(default=False)
    bpy.types.Light.spread = FloatProperty(default=0.0, min=0.0, max=1.0)

    # Register custom properties on Object using unique names
    bpy.types.Object.custom_lightgroup = StringProperty(
        name="Light Group",
        description="The custom lightgroup attribute for this object",
        default=""
    )
    
    bpy.types.Object.custom_lightgroup_menu = EnumProperty(
        name="Light Group",
        description="Select the custom light group for this light",
        items=get_light_group_items,  # Pass the function directly (no parentheses)
        update=update_lightgroup_menu
    )
    
    bpy.types.Object.light_enabled = BoolProperty(
        name="Enabled",
        default=True,
        update=update_light_enabled
    )
    bpy.types.Object.light_turn_off_others = BoolProperty(
        name="Turn Off Others",
        default=False,
        update=update_light_turn_off_others
    )
    bpy.types.Object.light_expanded = BoolProperty(
        name="Expanded",
        default=False
    )

    # Migration: for each light, if it has an old "lightgroup" attribute, migrate it.
    # Migration: for each light, if it has an old "lightgroup" attribute, migrate it.
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            old_group = getattr(obj, "lightgroup", "")
            if old_group:
                obj.custom_lightgroup = old_group
            obj.custom_lightgroup_menu = obj.custom_lightgroup if obj.custom_lightgroup else "NoGroup"

def unregister():
    # Unregister scene properties
    del bpy.types.Scene.current_active_light
    del bpy.types.Scene.current_exclusive_group

    # Unregister other classes and properties
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # Unregister other properties (as shown in your original code)
    del bpy.types.Scene.light_editor_filter
    del bpy.types.Scene.light_editor_kind_alpha
    del bpy.types.Scene.light_editor_group_by_collection
    del bpy.types.Scene.light_editor_light_group
    del bpy.types.Scene.create_new_lightgroup
    del bpy.types.Scene.custom_lightgroups_list
    del bpy.types.Scene.light_editor_delete_group
    del bpy.types.Light.soft_falloff
    del bpy.types.Light.max_bounce
    del bpy.types.Light.multiple_instance
    del bpy.types.Light.shadow_caustic
    del bpy.types.Light.spread
    del bpy.types.Object.custom_lightgroup
    del bpy.types.Object.custom_lightgroup_menu
    del bpy.types.Object.light_enabled
    del bpy.types.Object.light_turn_off_others
    del bpy.types.Object.light_expanded
if __name__ == "__main__":
    register()
