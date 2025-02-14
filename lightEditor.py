import bpy
import fnmatch
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
)
from bpy.app.handlers import persistent
from bpy.app.translations import contexts as i18n_contexts
import re, os

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
            group_val = getattr(obj, "lightgroup", "")
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

def update_light_types(self, context):
    if self == 'group':
    # Collapse all expanded lights when switching to "By Light Groups" mode
        for obj in context.view_layer.objects:
            if obj.type == 'LIGHT':
                obj.light_expanded = False

# Used for MacOS
def get_device_type(context):
    return context.preferences.addons['cycles'].preferences.compute_device_type

def backend_has_active_gpu(context):
    return context.preferences.addons['cycles'].preferences.has_active_device()

def use_metal(context):
    cscene = context.scene.cycles

    return (get_device_type(context) == 'METAL' and cscene.device == 'GPU' and backend_has_active_gpu(context))

def use_mnee(context):
    # The MNEE kernel doesn't compile on macOS < 13.
    if use_metal(context):
        import platform
        version, _, _ = platform.mac_ver()
        major_version = version.split(".")[0]
        if int(major_version) < 13:
            return False
    return True

# -------------------------------------------------------------------------
# 2) Extra parameters drawing function (unchanged)
# -------------------------------------------------------------------------
def draw_extra_params(self, box, obj, light):
    # layout = self.layout
    # col = layout.column()
    col = box.column()

    col.prop(light, "color")
    col.prop(light, "energy")
    col.separator()


    # CYCLES
    if bpy.context.engine == 'CYCLES':
        clamp = light.cycles
        if light.type in {'POINT', 'SPOT'}:
            col.prop(light, "use_soft_falloff")
            col.prop(light, "shadow_soft_size", text="Radius")
        elif light.type == 'SUN':
            col.prop(light, "angle")
        elif light.type == 'AREA':
            col.prop(light, "shape", text="Shape")
            sub = col.column(align=True)

            if light.shape in {'SQUARE', 'DISK'}:
                sub.prop(light, "size")
            elif light.shape in {'RECTANGLE', 'ELLIPSE'}:
                sub.prop(light, "size", text="Size X")
                sub.prop(light, "size_y", text="Y")

        if not (light.type == 'AREA' and clamp.is_portal):
            col.separator()
            sub = col.column()
            sub.prop(clamp, "max_bounces")

        sub = col.column(align=True)
        sub.active = not (light.type == 'AREA' and clamp.is_portal)
        sub.prop(clamp, "cast_shadow")
        sub.prop(clamp, "use_multiple_importance_sampling", text="Multiple Importance")
        if use_mnee(bpy.context):
            sub.prop(clamp, "is_caustics_light", text="Shadow Caustics")

        if light.type == 'AREA':
            col.prop(clamp, "is_portal", text="Portal")

        if light.type == 'SPOT':
            col.separator()
            # Create a new row for the label and center-align it
            row = col.row(align=True)
            row.alignment = 'CENTER'
            row.label(text="Spot Shape")
            col.prop(light, "spot_size", text="Beam Size")
            col.prop(light, "spot_blend", text="Blend", slider=True)
            col.prop(light, "show_cone")

        elif light.type == 'AREA':
            col.separator()
            # Create a new row for the label and center-align it
            row = col.row(align=True)
            row.alignment = 'CENTER'
            row.label(text="Beam Shape")
            col.prop(light, "spread", text="Spread")

    # EEVEE
    # Compact layout for node editor
    if ((bpy.context.engine == 'BLENDER_EEVEE') or (bpy.context.engine =='BLENDER_EEVEE_NEXT')):
        col.separator()
        col.prop(light, "diffuse_factor", text="Diffuse")
        col.prop(light, "specular_factor", text="Specular")
        col.prop(light, "volume_factor", text="Volume", text_ctxt=i18n_contexts.id_id)

        col.separator()
        if light.type in {'POINT', 'SPOT'}:
            col.prop(light, "use_soft_falloff")
            col.prop(light, "shadow_soft_size", text="Radius")
        elif light.type == 'SUN':
            col.prop(light, "angle")
        elif light.type == 'AREA':
            col.prop(light, "shape")

            sub = col.column(align=True)

            if light.shape in {'SQUARE', 'DISK'}:
                sub.prop(light, "size")
            elif light.shape in {'RECTANGLE', 'ELLIPSE'}:
                sub.prop(light, "size", text="Size X")
                sub.prop(light, "size_y", text="Y")

        if bpy.context.engine == 'BLENDER_EEVEE_NEXT':
            col.separator()
            col.prop(light, "use_shadow", text="Cast Shadow")
            col.prop(light, "shadow_softness_factor", text="Shadow Softness")

            if light.type == 'SUN':
                col.prop(light, "shadow_trace_distance", text="Trace Distance")

        # Custom Distance
        if (light and light.type != 'SUN'): # and (bpy.context.engine == 'BLENDER_EEVEE' or 'BLENDER_EEVEE_NEXT')):
            col.separator()
            sub = col.column()
            sub.prop(light, "use_custom_distance", text="Custom Distance")

            sub.active = light.use_custom_distance
            sub.prop(light, "cutoff_distance", text="Distance")
        
        # Spot Shape
        if (light and light.type == 'SPOT'):
            col.separator()
            # Create a new row for the label and center-align it
            row = col.row(align=True)
            row.alignment = 'CENTER'
            row.label(text="Spot Shape")
            col.prop(light, "spot_size", text="Size")
            col.prop(light, "spot_blend", text="Blend", slider=True)

            col.prop(light, "show_cone")

        # Shadows
        if (light and light.type in {'POINT', 'SUN', 'SPOT', 'AREA'}):

            col.separator()
            subb = col.column()
            subb.prop(light, "use_shadow", text="Shadow")

            if light.type != 'SUN':
                subb.prop(light, "shadow_buffer_clip_start", text="Clip Start")
            subb.prop(light, "shadow_buffer_bias", text="Bias")
            subb.active = light.use_shadow

            # Cascaded Shadow Map
            if (light and light.type == 'SUN'):

                col.separator()
                # Create a new row for the label and center-align it
                row = col.row(align=True)
                row.alignment = 'CENTER'
                row.label(text="Cascaded Shadow Map")
                col.prop(light, "shadow_cascade_count", text="Count")
                col.prop(light, "shadow_cascade_fade", text="Fade")

                col.prop(light, "shadow_cascade_max_distance", text="Max Distance")
                col.prop(light, "shadow_cascade_exponent", text="Distribution")

            #Contact Shadows
            if (
            (light and light.type in {'POINT', 'SUN', 'SPOT', 'AREA'}) and
            (bpy.context.engine == 'BLENDER_EEVEE' or 'BLENDER_EEVEE_NEXT')):

                col.separator()
                subbb = col.column()
                subbb.active = light.use_shadow
                subbb.prop(light, "use_contact_shadow", text="Contact Shadows")

                col = subbb.column()
                col.active = light.use_shadow and light.use_contact_shadow

                col.prop(light, "contact_shadow_distance", text="Distance")
                col.prop(light, "contact_shadow_bias", text="Bias")
                col.prop(light, "contact_shadow_thickness", text="Thickness")


# -------------------------------------------------------------------------
# Render layer menu
# -------------------------------------------------------------------------

def get_render_layer_items(self, context):
    """Return a list of render layer items for the EnumProperty."""
    items = []
    for view_layer in context.scene.view_layers:
        items.append((view_layer.name, view_layer.name, ""))
    return items

def update_render_layer(self, context):
    selected = self.selected_render_layer
    # Iterate over the scene’s view layers:
    for vl in context.scene.view_layers:
        if vl.name == selected:
            context.window.view_layer = vl
            break


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
            # all_lights = [obj for obj in context.view_layer.objects
            #               if obj.type == 'LIGHT' and fnmatch.fnmatch(obj.name.lower(), filter_pattern)]
            
            all_lights = [obj for obj in context.view_layer.objects
                          if obj.type == 'LIGHT' and re.search(filter_pattern, obj.name, re.I)]

            # for fn in sorted(files):
            #     if not fn.lower().startswith("._"):
            #         if fn.lower().endswith(".hdr") or fn.lower().endswith(".exr") or fn.lower().endswith(".jpg") or fn.lower().endswith(".png"):
            #             if not scn.easyhdr_filter or re.search(scn.easyhdr_filter, fn, re.I):
            #                 hdris.append(os.path.join(root, fn).replace(dir, ''))
            #                 no_match = False
        else:
            all_lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']
        if scene.filter_light_types == 'COLLECTION' and group_key.startswith("coll_"):
            coll_name = group_key[5:]
            return [obj for obj in all_lights
                    if (obj.users_collection and obj.users_collection[0].name == coll_name)
                    or (not obj.users_collection and coll_name == "No Collection")]
        if scene.filter_light_types == 'KIND' and group_key.startswith("kind_"):
            kind = group_key[5:]
            return [obj for obj in all_lights if obj.data.type == kind]
        if scene.filter_light_types == 'GROUP' and group_key.startswith("group_"):
            group_name = group_key[6:]
            return [obj for obj in all_lights if getattr(obj, "custom_lightgroup", "") == group_name]
        return []

class LIGHT_OT_ToggleGroupExclusive(bpy.types.Operator):
    """
    Toggle exclusive mode for a group.
    When turned on, lights in other groups (including "Not Assigned") are turned off.
    When turned off, lights in other groups are restored to their previous states.
    """
    bl_idname = "light_editor.toggle_group_exclusive"
    bl_label = "Toggle Group Exclusive"
    group_key: StringProperty()

    def execute(self, context):
        global current_exclusive_group, group_checkbox_2_state, other_groups_original_state

        # Check if the current group is already in exclusive mode
        is_on = group_checkbox_2_state.get(self.group_key, False)

        if not is_on:
            # If another group is already in exclusive mode, turn it off first
            if current_exclusive_group and current_exclusive_group != self.group_key:
                group_checkbox_2_state[current_exclusive_group] = False
                saved_dict = other_groups_original_state.get(current_exclusive_group, {})
                for gk, light_dict in saved_dict.items():
                    grp_objs = self._get_group_objects(context, gk)
                    for obj in grp_objs:
                        obj.light_enabled = light_dict.get(obj.name, True)
                if current_exclusive_group in other_groups_original_state:
                    del other_groups_original_state[current_exclusive_group]

            # Turn off all other groups (including "Not Assigned") and store their current states
            others = self._get_all_other_groups(context, self.group_key)
            saved_dict = {}
            for gk in others:
                grp_objs = self._get_group_objects(context, gk)
                saved_dict[gk] = {obj.name: obj.light_enabled for obj in grp_objs}
                for obj in grp_objs:
                    obj.light_enabled = False

            # Store the saved states and mark the current group as exclusive
            other_groups_original_state[self.group_key] = saved_dict
            group_checkbox_2_state[self.group_key] = True
            current_exclusive_group = self.group_key

        else:
            # Restore the states of all other groups (including "Not Assigned")
            saved_dict = other_groups_original_state.get(self.group_key, {})
            for gk, light_dict in saved_dict.items():
                grp_objs = self._get_group_objects(context, gk)
                for obj in grp_objs:
                    obj.light_enabled = light_dict.get(obj.name, True)

            # Clear the saved states and mark the current group as non-exclusive
            if self.group_key in other_groups_original_state:
                del other_groups_original_state[self.group_key]
            group_checkbox_2_state[self.group_key] = False
            current_exclusive_group = None

        # Redraw the UI to reflect the changes
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}

    def _get_all_other_groups(self, context, current_key):
        """Get all group keys except the current one, including "Not Assigned"."""
        all_groups = self._get_all_group_keys(context)
        return [k for k in all_groups if k != current_key]

    def _get_all_group_keys(self, context):
        """Get all group keys, including "Not Assigned"."""
        scene = context.scene
        filter_pattern = scene.light_editor_filter.lower()
        if filter_pattern:
            lights = [obj for obj in context.view_layer.objects
                      if obj.type == 'LIGHT' and re.search(filter_pattern, obj.name, re.I)]
        else:
            lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']

        group_keys = set()
        if scene.filter_light_types == 'COLLECTION':
            for obj in lights:
                if obj.users_collection:
                    coll_name = obj.users_collection[0].name
                else:
                    coll_name = "No Collection"
                group_keys.add(f"coll_{coll_name}")
        elif scene.filter_light_types == 'KIND':
            for obj in lights:
                if obj.data.type in {'POINT', 'SPOT', 'SUN', 'AREA'}:
                    group_keys.add(f"kind_{obj.data.type}")
        elif scene.filter_light_types == 'GROUP':
            for obj in lights:
                group_name = getattr(obj, "lightgroup", "")
                if not group_name:
                    group_name = "Not Assigned"  # Explicitly handle "Not Assigned"
                group_keys.add(f"group_{group_name}")
        return list(group_keys)

    def _get_group_objects(self, context, group_key):
        """Get all objects in the specified group, including "Not Assigned"."""
        scene = context.scene
        filter_pattern = scene.light_editor_filter.lower()
        if filter_pattern:
            all_lights = [obj for obj in context.view_layer.objects
                          if obj.type == 'LIGHT' and re.search(filter_pattern, obj.name, re.I)]
        else:
            all_lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']

        if scene.filter_light_types == 'COLLECTION' and group_key.startswith("coll_"):
            coll_name = group_key[5:]
            return [obj for obj in all_lights
                    if (obj.users_collection and obj.users_collection[0].name == coll_name)
                    or (not obj.users_collection and coll_name == "No Collection")]
        if scene.filter_light_types == 'KIND' and group_key.startswith("kind_"):
            kind = group_key[5:]
            return [obj for obj in all_lights if obj.data.type == kind]
        if scene.filter_light_types == 'GROUP' and group_key.startswith("group_"):
            group_name = group_key[6:]
            if group_name == "Not Assigned":
                return [obj for obj in all_lights if not getattr(obj, "lightgroup", "")]
            else:
                return [obj for obj in all_lights if getattr(obj, "lightgroup", "") == group_name]
        return []

class LIGHT_OT_ClearFilter(bpy.types.Operator):
    """Clear Filter Types"""
    bl_idname = "le.clear_light_filter"
    bl_label = "Clear Filter"

    @classmethod
    def poll(cls, context):
        return context.scene.light_editor_filter

    def execute(self, context):
        if context.scene.light_editor_filter:
            context.scene.light_editor_filter = ""
        return {'FINISHED'}


class LIGHT_OT_SelectLight(bpy.types.Operator):
    """Selects light from UI and deselects everything else"""
    bl_idname = "le.select_light"
    bl_label = "Select Light"

    name : StringProperty()  # Name of the light to select

    def execute(self, context):
        # Get the view layer objects
        vob = context.view_layer.objects

        # Check if the light is already selected
        if self.name in vob:
            light = vob[self.name]
            if light.select_get():  # If the light is already selected
                # Deselect everything
                bpy.ops.object.select_all(action='DESELECT')
                self.report({'INFO'}, f"Deselected all objects")
            else:
                # Deselect all objects first
                bpy.ops.object.select_all(action='DESELECT')
                # Select the specified light
                light.select_set(True)
                vob.active = light  # Set the light as the active object
                self.report({'INFO'}, f"Selected light: {self.name}")
        else:
            self.report({'ERROR'}, f"Light '{self.name}' not found")

        return {'FINISHED'}



# -------------------------------------------------------------------------
# 4) The main row UI: use custom_lightgroup property when in Light Group mode
# -------------------------------------------------------------------------
def draw_main_row(box, obj):
    light = obj.data
    context = bpy.context
    scene = bpy.context.scene
    row = box.row(align=True)
    controls_row = row.row(align=True)
    
    # The enabled and "turn off others" toggles remain:
    controls_row.prop(obj, "light_enabled", text="",
            icon="OUTLINER_OB_LIGHT" if obj.light_enabled else "LIGHT_DATA")
    controls_row.active = obj.light_enabled == True                  
    controls_row.prop(obj, "light_turn_off_others", text="",
            icon="RADIOBUT_ON" if obj.light_turn_off_others else "RADIOBUT_OFF")

    if not scene.filter_light_types == 'GROUP':
        selected_true = custom_icons["SELECT_TRUE"].icon_id
        selected_false = custom_icons["SELECT_FALSE"].icon_id
        controls_row.operator("le.select_light", text="", 
                icon_value=selected_true if obj.select_get() == True else selected_false).name = obj.name

    # -- Only show the triangle if NOT in Light Group mode --
    if not scene.filter_light_types == 'GROUP':
        controls_row.prop(obj, "light_expanded", text="",
                          emboss=True,
                          icon='DOWNARROW_HLT' if obj.light_expanded else 'RIGHTARROW')
    
    # Apply 50-50 split only in Light Group mode
    if scene.filter_light_types == 'GROUP':
        split = row.split(factor=0.5)
        col_name = split.column(align=True)
        col_name.prop(obj, "name", text="")  # Default width in Light Group mode

        col_group = split.column(align=True)
        view_layer = context.view_layer
        
        row_group = col_group.row(align=True)
        sub = row_group.column(align=True)
        sub.prop_search(obj, "lightgroup", view_layer, "lightgroups", text="", results_are_suggestions=True)
        
        sub = row_group.column(align=True)
        sub.enabled = bool(obj.lightgroup) and not any(lg.name == obj.lightgroup for lg in view_layer.lightgroups)
        sub.operator("scene.view_layer_add_lightgroup", icon='ADD', text="").name = obj.lightgroup

    else:
        # Original layout for other modes, with a shorter name field
        col_name = row.column(align=True)
        col_name.scale_x = 0.4  # Make the name field shorter
        col_name.prop(obj, "name", text="")

        col_color = row.column(align=True)
        col_color.scale_x = 0.25
        col_color.prop(light, "color", text="")
        col_energy = row.column(align=True)
        col_energy.scale_x = 0.35
        col_energy.prop(light, "energy", text="")

# class DataButtonsPanel:
#     bl_space_type = 'PROPERTIES'
#     bl_region_type = 'WINDOW'
#     bl_context = "data"

#     @classmethod
#     def poll(cls, context):
#         engine = context.engine
#         return context.light and (engine in cls.COMPAT_ENGINES)

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
        
        layout.row().prop(scene, "filter_light_types", expand=True)
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        
        # Top toggles with new labels.
        # row = layout.row(align=True)
        # row.prop(scene, "light_editor_kind_alpha", text="By Kind")
        # row.prop(scene, "light_editor_group_by_collection", text="By Collections")
        # row.prop(scene, "light_editor_light_group", text="By Light Groups")
        

        row = layout.row(align=True)
        row.prop(scene, "light_editor_filter", text="", icon="VIEWZOOM")
        row.operator("le.clear_light_filter", text="", icon='PANEL_CLOSE')
        
        # Only display the render layer dropdown when in Collection mode.
        if scene.filter_light_types == 'COLLECTION':
            row = layout.row()
            row.prop(scene, "selected_render_layer", text="Render Layer")

        # Only show these rows if in Light Group mode.
        if scene.filter_light_types == 'GROUP':
            # # Row for adding a new light group.
            # row = layout.row(align=True)
            # row.prop(scene, "create_new_lightgroup", text="")
            # row.operator("light_editor.create_new_lightgroup", text="Add Lightgroup")

            # # Row for selecting and deleting a light group.
            # row = layout.row(align=True)
            # row.prop(scene, "light_editor_delete_group", text="")
            # row.operator("light_editor.delete_light_group", text="Delete Light Group")

            # copy from passes panel
            view_layer = context.view_layer

            # layout.label(text="Light Groups")
            # layout.alignment = 'CENTER'
            row = layout.row()
            col = row.column()
            col.template_list("UI_UL_list", "lightgroups", view_layer,
                            "lightgroups", view_layer, "active_lightgroup_index", rows=3)

            col = row.column()
            sub = col.column(align=True)
            sub.operator("scene.view_layer_add_lightgroup", icon='ADD', text="")
            sub.operator("scene.view_layer_remove_lightgroup", icon='REMOVE', text="")
            sub.separator()
            sub.menu("VIEWLAYER_MT_lightgroup_sync", icon='DOWNARROW_HLT', text="")


        # Get lights from the active view layer
        if scene.light_editor_filter:
            lights = [obj for obj in context.view_layer.objects
            if obj.type == 'LIGHT' and re.search(scene.light_editor_filter.lower(), obj.name.lower(), re.I)]
            # if obj.type == 'LIGHT' and fnmatch.fnmatch(obj.name.lower(), scene.light_editor_filter.lower())]
        else:
            lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']

        if scene.filter_light_types == 'COLLECTION':
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
                header_row.active = is_on_1 == True
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
                                             icon='RIGHTARROW' if collapsed else 'DOWNARROW_HLT')
                op_tri.group_key = group_key
                header_row.label(text=group_name, icon='OUTLINER_COLLECTION')

                if not collapsed and not scene.filter_light_types == 'GROUP':
                    for obj in group_objs:
                        draw_main_row(header_box, obj)
                        if obj.light_expanded:
                            extra_box = header_box.box()
                            # extra_box.label(text="Extra Parameters:")
                            draw_extra_params(self, extra_box, obj, obj.data)
                            
        elif scene.filter_light_types == 'KIND':
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
                    header_row.active = is_on_1 == True
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
                                                 icon='RIGHTARROW' if collapsed else 'DOWNARROW_HLT')
                    op_tri.group_key = group_key
                    header_row.label(text=f"{kind} Lights", icon=f"LIGHT_{kind}")
                    if not collapsed:
                        for obj in groups[kind]:
                            draw_main_row(header_box, obj)
                            if obj.light_expanded:
                                extra_box = header_box.box()
                                # extra_box.label(text="Extra Parameters:")
                                draw_extra_params(self, extra_box, obj, obj.data)
                                
        elif scene.filter_light_types == 'GROUP':
            groups = {}
            for obj in lights:
                # Try the migrated property; fallback to old property if needed.
                grp = getattr(obj, "lightgroup", "")
                if not grp:
                    grp = getattr(obj, "lightgroup", "")
                if not grp:
                    grp = "Not Assigned"
                groups.setdefault(grp, []).append(obj)
            for grp_name, group_objs in groups.items():
                group_key = f"group_{grp_name}"
                collapsed = group_collapse_dict.get(group_key, False)
                header_box = layout.box()
                header_row = header_box.row(align=True)
                is_on_1 = group_checkbox_1_state.get(group_key, True)
                header_row.active = is_on_1 == True
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
                                             icon='RIGHTARROW' if collapsed else 'DOWNARROW_HLT')
                op_tri.group_key = group_key
                header_row.label(text=f"{grp_name}", icon='GROUP')
                if not collapsed:
                    for obj in group_objs:
                        draw_main_row(header_box, obj)
                        # We dont show extra light props in this mode
                        # if obj.light_expanded:
                        #     extra_box = header_box.box()
                        #     # extra_box.label(text="Extra Parameters:")
                        #     draw_extra_params(self, extra_box, obj, obj.data)
        else:
            # Alphabetical order mode
            sorted_lights = sorted(lights, key=lambda o: o.name.lower())
            box = layout.box()
            box.label(text="All Lights (Alphabetical)", icon='LIGHT_DATA')
            for obj in sorted_lights:
                draw_main_row(box, obj)
                if obj.light_expanded: # Check if the light is expanded
                    extra_box = box.box()
                    # extra_box.label(text="Extra Parameters:")
                    draw_extra_params(self, extra_box, obj, obj.data) # Draw extra parameters


@persistent
def LE_check_lights_enabled(dummy):
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            if (obj.hide_viewport and obj.hide_render):
                bpy.context.view_layer.objects[obj.name].light_enabled = False
            else:
                bpy.context.view_layer.objects[obj.name].light_enabled = True


@persistent
def LE_clear_handler(dummy):
    context = bpy.context
    # Migration: for each light, if it has an old "lightgroup" attribute, migrate it.
    if bpy and bpy.data:
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT':
                old_group = getattr(obj, "lightgroup", "")
                if old_group:
                    obj.lightgroup = old_group
                # obj.custom_lightgroup_menu = obj.lightgroup if obj.lightgroup else "NoGroup"
                # if old_group:
                #     obj.custom_lightgroup = old_group
                # obj.custom_lightgroup_menu = obj.custom_lightgroup if obj.custom_lightgroup else "NoGroup"

                # Set enable correct
                if (obj.hide_viewport == False and obj.hide_render == False):
                    context.view_layer.objects[obj.name].light_enabled = True
                else:
                    context.view_layer.objects[obj.name].light_enabled = False
            # self.hide_render = not self.light_enabled


def icon_Load():
    # importing icons
    import bpy.utils.previews
    global custom_icons
    custom_icons = bpy.utils.previews.new()

    # path to the folder where the icon is
    # the path is calculated relative to this py file inside the addon folder
    icons_dir = os.path.join(os.path.dirname(__file__), 'icons')

    # load a preview thumbnail of a file and store in the previews collection
    custom_icons.load("SELECT_TRUE", os.path.join(icons_dir, "select_true.png"), 'IMAGE')
    custom_icons.load("SELECT_FALSE", os.path.join(icons_dir, "select_false.png"), 'IMAGE')

# global variable to store icons in
custom_icons = None

# Register the new operator and property
classes = (
    LIGHT_OT_ToggleGroup,
    LIGHT_OT_ToggleGroupAllOff,
    LIGHT_OT_ToggleGroupExclusive,
    # LIGHT_OT_CreateNewLightgroup,
    # LIGHT_OT_DeleteLightGroup,
    LIGHT_OT_ClearFilter,
    LIGHT_OT_SelectLight,
    LIGHT_PT_editor,
)

def register():
    icon_Load()
    # Register scene properties
    bpy.types.Scene.current_active_light = bpy.props.PointerProperty(type=bpy.types.Object)
    bpy.types.Scene.current_exclusive_group = bpy.props.StringProperty()
    bpy.types.Scene.selected_render_layer = EnumProperty(
        name="Render Layer",
        description="Select the render layer",
        items=get_render_layer_items,  # Your function that lists view layers.
        update=update_render_layer
    )

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
        default=False,  # Ensure this is False by default
        update=update_group_by_kind
    )
    bpy.types.Scene.light_editor_group_by_collection = BoolProperty(
        name="By Collections",
        description="Group lights by collection",
        default=False,  # Ensure this is False by default
        update=update_group_by_collection
    )
    bpy.types.Scene.light_editor_light_group = BoolProperty(
        name="By Light Groups",
        description="Group lights by their custom light group assignment",
        default=False,  # Ensure this is False by default
        update=update_light_group
    )
    # bpy.types.Scene.create_new_lightgroup = StringProperty(
    #     name="",
    #     default="",
    #     description="Enter a new light group name"
    # )
    bpy.types.Scene.custom_lightgroups_list = StringProperty(
        name="Custom Lightgroups",
        default="",
        description="Comma separated list of custom light groups created without an active light"
    )
    
    # bpy.types.Scene.light_editor_delete_group = EnumProperty(
    #     name="Delete Light Group",
    #     description="Select a light group to delete",
    #     items=get_light_group_items  # Pass the function directly (no parentheses)
    # )

    bpy.types.Scene.filter_light_types = EnumProperty(
        name="Type",
        description="Filter light by type",
        items=(('NO_FILTER', 'All', 'Show All no filter (Alphabetical)', 'NONE', 0), ('KIND', 'Kind', 'FIlter lights by Kind', 'LIGHT_DATA', 1),('COLLECTION', 'Collection', 'FIlter lights by Collections', 'OUTLINER_COLLECTION', 2),('GROUP', 'Light Group', 'Filter lights by Light Groups', 'GROUP', 3)),
        update=update_light_types
    )

    # Register Light properties
    bpy.types.Light.soft_falloff = BoolProperty(default=False)
    bpy.types.Light.max_bounce = IntProperty(default=0, min=0, max=10)
    bpy.types.Light.multiple_instance = BoolProperty(default=False)
    bpy.types.Light.shadow_caustic = BoolProperty(default=False)
    bpy.types.Light.spread = FloatProperty(default=0.0, min=0.0, max=1.0)

    
    # Register custom properties on Object using unique names
    # bpy.types.Object.custom_lightgroup = StringProperty(
    #     name="Light Group",
    #     description="The custom lightgroup attribute for this object",
    #     default=""
    # )
    
    # bpy.types.Object.custom_lightgroup_menu = EnumProperty(
    #     name="Light Group",
    #     description="Select the custom light group for this light",
    #     items=get_light_group_items,  # Pass the function directly (no parentheses)
    #     update=update_lightgroup_menu
    # )
    
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
        default=False  # Ensure this is False by default
    )

    #add handler post load > see @persistent
    bpy.app.handlers.load_post.append(LE_clear_handler)
    # bpy.app.handlers.depsgraph_update_post.append(LE_check_lights_enabled)
    bpy.app.handlers.load_post.append(LE_check_lights_enabled)
    
    


def unregister():
    global custom_icons
    bpy.utils.previews.remove(custom_icons)

    #removove handler post load > see @persistent
    bpy.app.handlers.load_post.remove(LE_clear_handler)
    bpy.app.handlers.load_post.remove(LE_check_lights_enabled)

    # Unregister scene properties
    del bpy.types.Scene.current_active_light
    del bpy.types.Scene.current_exclusive_group
    del bpy.types.Scene.selected_render_layer

    # Unregister other classes and properties
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # Unregister other properties (as shown in your original code)
    del bpy.types.Scene.light_editor_filter
    del bpy.types.Scene.light_editor_kind_alpha
    del bpy.types.Scene.light_editor_group_by_collection
    del bpy.types.Scene.light_editor_light_group
    # del bpy.types.Scene.create_new_lightgroup
    # del bpy.types.Scene.custom_lightgroups_list
    del bpy.types.Scene.light_editor_delete_group
    del bpy.types.Light.soft_falloff
    del bpy.types.Light.max_bounce
    del bpy.types.Light.multiple_instance
    del bpy.types.Light.shadow_caustic
    del bpy.types.Light.spread
    # del bpy.types.Object.custom_lightgroup
    # del bpy.types.Object.custom_lightgroup_menu
    del bpy.types.Object.light_enabled
    del bpy.types.Object.light_turn_off_others
    del bpy.types.Object.light_expanded

if __name__ == "__main__":
    register()
