import bpy
import fnmatch
import re, os
from bpy.props import (
    BoolProperty,
    IntProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
)
from bpy.app.handlers import persistent
from bpy.app.translations import contexts as i18n_contexts

# Global variables and dictionaries for group toggling
current_exclusive_group = None
group_checkbox_1_state = {}      # Not used in this snippet but kept for compatibility
group_lights_original_state = {} # Not used in this snippet but kept for compatibility
group_checkbox_2_state = {}      # For exclusive toggling per group key (OFF by default)
other_groups_original_state = {} # Stores states of other groups
group_collapse_dict = {}         # Per-group collapse state (keyed by group key)

# -------------------------------------------------------------------------
# New property: light_selected (to mirror the actual selection)
# -------------------------------------------------------------------------
def get_light_selected(self):
    return self.select_get()

def set_light_selected(self, value):
    self.select_set(value)

# -------------------------------------------------------------------------
# Update functions for lights
# -------------------------------------------------------------------------
def update_light_enabled(self, context):
    self.hide_viewport = not self.light_enabled
    self.hide_render = not self.light_enabled

def update_light_turn_off_others(self, context):
    scene = context.scene
    if self.light_turn_off_others:
        if scene.current_active_light and scene.current_active_light != self:
            scene.current_active_light.light_turn_off_others = False
        scene.current_active_light = self
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

# -------------------------------------------------------------------------
# Device and kernel utilities
# -------------------------------------------------------------------------
def get_device_type(context):
    return context.preferences.addons['cycles'].preferences.compute_device_type

def backend_has_active_gpu(context):
    return context.preferences.addons['cycles'].preferences.has_active_device()

def use_metal(context):
    cscene = context.scene.cycles
    return (get_device_type(context) == 'METAL' and cscene.device == 'GPU' and backend_has_active_gpu(context))

def use_mnee(context):
    if use_metal(context):
        import platform
        version, _, _ = platform.mac_ver()
        major_version = version.split(".")[0]
        if int(major_version) < 13:
            return False
    return True


def update_group_by_kind(self, context):
    if self.light_editor_kind_alpha:
        self.light_editor_group_by_collection = False

        
def update_group_by_collection(self, context):
    if self.light_editor_group_by_collection:
        self.light_editor_kind_alpha = False
      
def update_light_types(self, context):
    if self == 'group':
    # Collapse all expanded lights when switching to "By Light Groups" mode
        for obj in context.view_layer.objects:
            if obj.type == 'LIGHT':
                obj.light_expanded = False        
# -------------------------------------------------------------------------
# Extra parameters drawing function (unchanged)
# -------------------------------------------------------------------------
def draw_extra_params(self, box, obj, light):
    if light and isinstance(light, bpy.types.Light):
        layout = box
        row = layout.row()
        row.prop(light, "type", expand=True)
        col = layout.column()
        col.separator()
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
            sub.prop(light, "use_shadow", text="Cast Shadow")
            sub.prop(clamp, "use_multiple_importance_sampling", text="Multiple Importance")
            if use_mnee(bpy.context):
                sub.prop(clamp, "is_caustics_light", text="Shadow Caustics")
            if light.type == 'AREA':
                col.prop(clamp, "is_portal", text="Portal")
            if light.type == 'SPOT':
                col.separator()
                row = col.row(align=True)
                row.alignment = 'CENTER'
                row.label(text="Spot Shape")
                col.prop(light, "spot_size", text="Spot Size")
                col.prop(light, "spot_blend", text="Blend", slider=True)
                col.prop(light, "show_cone")
            elif light.type == 'AREA':
                col.separator()
                row = col.row(align=True)
                row.alignment = 'CENTER'
                row.label(text="Beam Shape")
                col.prop(light, "spread", text="Spread")
        if ((bpy.context.engine == 'BLENDER_EEVEE') or (bpy.context.engine == 'BLENDER_EEVEE_NEXT')):
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
                col.prop(light, "use_shadow_jitter")
                col.prop(light, "shadow_jitter_overblur", text="Overblur")
                col.prop(light, "shadow_filter_radius", text="Radius")
                col.prop(light, "shadow_maximum_resolution", text="Resolution Limit")
            if (light and light.type == 'SPOT'):
                col.separator()
                row = col.row(align=True)
                row.alignment = 'CENTER'
                row.label(text="Spot Shape")
                col.prop(light, "spot_size", text="Size")
                col.prop(light, "spot_blend", text="Blend", slider=True)
                col.prop(light, "show_cone")
            col.separator()
            col.prop(light, "diffuse_factor", text="Diffuse")
            col.prop(light, "specular_factor", text="Specular")
            col.prop(light, "volume_factor", text="Volume", text_ctxt=i18n_contexts.id_id)
            if (light and light.type != 'SUN'):
                col.separator()
                sub = col.column()
                sub.prop(light, "use_custom_distance", text="Custom Distance")
                sub.active = light.use_custom_distance
                sub.prop(light, "cutoff_distance", text="Distance")

# -------------------------------------------------------------------------
# Operators for group toggling
# -------------------------------------------------------------------------
class LIGHT_OT_ToggleGroup(bpy.types.Operator):
    """Collapse or expand a group header."""
    bl_idname = "light_editor.toggle_group"
    bl_label = "Toggle Group"
    group_key: StringProperty()

    def execute(self, context):
        global group_collapse_dict
        current = group_collapse_dict.get(self.group_key, False)
        group_collapse_dict[self.group_key] = not current  # Toggle the collapse state
        self.report({'INFO'}, f"Group '{self.group_key}' toggled to {group_collapse_dict[self.group_key]}")
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}

class LIGHT_OT_ToggleGroupExclusive(bpy.types.Operator):
    """
    Toggle exclusive mode for a group.
    When turned on, lights in other groups are turned off.
    When turned off, lights in other groups are restored.
    """
    bl_idname = "light_editor.toggle_group_exclusive"
    bl_label = "Toggle Group Exclusive"
    group_key: StringProperty()

    def execute(self, context):
        global current_exclusive_group, group_checkbox_2_state, other_groups_original_state
        is_on = group_checkbox_2_state.get(self.group_key, False)

        if not is_on:
            if current_exclusive_group and current_exclusive_group != self.group_key:
                self._restore_other_groups(current_exclusive_group)
                group_checkbox_2_state[current_exclusive_group] = False

            others = self._get_all_other_groups(context, self.group_key)
            saved_dict = {}
            for gk in others:
                grp_objs = self._get_group_objects(context, gk)
                saved_dict[gk] = {obj.name: {'enabled': obj.light_enabled, 
                                             'selected': obj.light_selected, 
                                             'expanded': obj.light_expanded} for obj in grp_objs}
                for obj in grp_objs:
                    obj.light_enabled = False
                    obj.light_selected = False
            other_groups_original_state[self.group_key] = saved_dict
            group_checkbox_2_state[self.group_key] = True
            current_exclusive_group = self.group_key
        else:
            self._restore_other_groups(self.group_key)
            if self.group_key in other_groups_original_state:
                del other_groups_original_state[self.group_key]
            group_checkbox_2_state[self.group_key] = False
            current_exclusive_group = None

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}

    def _get_all_other_groups(self, context, current_key):
        all_groups = self._get_all_group_keys(context)
        return [k for k in all_groups if k != current_key]

    def _get_all_group_keys(self, context):
        scene = context.scene
        view_layer = context.view_layer
        filter_pattern = scene.light_editor_filter.lower()
        if filter_pattern:
            lights = [obj for obj in view_layer.objects if obj.type == 'LIGHT' and re.search(filter_pattern, obj.name, re.I)]
        else:
            lights = [obj for obj in view_layer.objects if obj.type == 'LIGHT']

        group_keys = set()
        if scene.filter_light_types == 'COLLECTION':
            for obj in lights:
                coll_name = obj.users_collection[0].name if obj.users_collection else "No Collection"
                group_keys.add(f"coll_{coll_name}")
        elif scene.filter_light_types == 'KIND':
            for obj in lights:
                group_keys.add(f"kind_{obj.data.type}")

        return list(group_keys)

    def _get_group_objects(self, context, group_key):
        scene = context.scene
        view_layer = context.view_layer
        filter_pattern = scene.light_editor_filter.lower()
        if filter_pattern:
            all_lights = [obj for obj in view_layer.objects if obj.type == 'LIGHT' and re.search(filter_pattern, obj.name, re.I)]
        else:
            all_lights = [obj for obj in view_layer.objects if obj.type == 'LIGHT']

        if scene.filter_light_types == 'COLLECTION' and group_key.startswith("coll_"):
            coll_name = group_key[5:]
            return [obj for obj in all_lights if (obj.users_collection and obj.users_collection[0].name == coll_name) or (not obj.users_collection and coll_name == "No Collection")]
        elif scene.filter_light_types == 'KIND' and group_key.startswith("kind_"):
            kind = group_key[5:]
            return [obj for obj in all_lights if obj.data.type == kind]
        return []

    def _restore_other_groups(self, group_key):
        saved_dict = other_groups_original_state.get(group_key, {})
        for gk, light_dict in saved_dict.items():
            grp_objs = self._get_group_objects(bpy.context, gk)
            for obj in grp_objs:
                if obj.name in light_dict:
                    obj.light_enabled = light_dict[obj.name]['enabled']
                    obj.light_selected = light_dict[obj.name]['selected']
                    obj.light_expanded = light_dict[obj.name]['expanded']

class LIGHT_OT_ClearFilter(bpy.types.Operator):
    """Clear Filter Types"""
    bl_idname = "le.clear_light_filter"
    bl_label = "Clear Filter"

    @classmethod
    def poll(cls, context):
        return context.scene.light_editor_filter

    def execute(self, context):
        context.scene.light_editor_filter = ""
        return {'FINISHED'}

class LIGHT_OT_SelectLight(bpy.types.Operator):
    """Selects light from UI and deselects everything else"""
    bl_idname = "le.select_light"
    bl_label = "Select Light"

    name: StringProperty()

    def execute(self, context):
        vob = context.view_layer.objects
        if self.name in vob:
            light = vob[self.name]
            if light.select_get():
                bpy.ops.object.select_all(action='DESELECT')
                self.report({'INFO'}, f"Deselected all objects")
            else:
                bpy.ops.object.select_all(action='DESELECT')
                light.select_set(True)
                vob.active = light
                self.report({'INFO'}, f"Selected light: {self.name}")
        else:
            self.report({'ERROR'}, f"Light '{self.name}' not found")
        return {'FINISHED'}

# -------------------------------------------------------------------------
# The main row UI drawing function
# -------------------------------------------------------------------------
def draw_main_row(box, obj):
    scene = bpy.context.scene
    row = box.row(align=True)
    light = obj.data
    controls_row = row.row(align=True)
    controls_row.prop(obj, "light_enabled", text="",
                      icon="OUTLINER_OB_LIGHT" if obj.light_enabled else "LIGHT_DATA")
    controls_row.active = obj.light_enabled
    controls_row.prop(obj, "light_turn_off_others", text="", icon_only=False,
                      icon='RADIOBUT_ON' if obj.light_turn_off_others else 'RADIOBUT_OFF')
    try:
        selected_true = custom_icons["SELECT_TRUE"].icon_id
        selected_false = custom_icons["SELECT_FALSE"].icon_id
    except Exception:
        selected_true = selected_false = 0
    op = controls_row.operator("le.select_light", text="", 
                               icon_value=selected_true if obj.select_get() else selected_false)
    op.name = obj.name
    controls_row.prop(obj, "light_expanded", text="", emboss=True,
                      icon='DOWNARROW_HLT' if obj.light_expanded else 'RIGHTARROW')
    col_name = row.column(align=True)
    col_name.scale_x = 0.4
    col_name.prop(obj, "name", text="")
    col_color = row.column(align=True)
    col_color.scale_x = 0.25
    if light.use_nodes and light.node_tree:
        color_node = next((node for node in light.node_tree.nodes if node.type == 'EMISSION'), None)
        if color_node:
            col_color.prop(color_node.inputs[0], "default_value", text="")
    else:
        col_color.prop(light, "color", text="")
    col_energy = row.column(align=True)
    col_energy.scale_x = 0.35
    if light.use_nodes and light.node_tree:
        strength_node = next((node for node in light.node_tree.nodes if node.type == 'EMISSION'), None)
        if strength_node:
            col_energy.prop(strength_node.inputs[1], "default_value", text="")
    else:
        col_energy.prop(light, "energy", text="")

# -------------------------------------------------------------------------
# The main panel
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
        view_layer = context.view_layer

        # Top row: switch mode buttons and filter
        layout.row().prop(scene, "filter_light_types", expand=True)
        layout.use_property_split = True
        layout.use_property_decorate = False
        row = layout.row(align=True)
        row.prop(scene, "light_editor_filter", text="", icon="VIEWZOOM")
        row.operator("le.clear_light_filter", text="", icon='PANEL_CLOSE')
        if scene.filter_light_types == 'COLLECTION':
            row = layout.row()
            row.prop(scene, "selected_render_layer", text="Render Layer")

        # Get lights (filtered if needed)
        if scene.light_editor_filter:
            lights = [obj for obj in view_layer.objects if obj.type == 'LIGHT' and re.search(scene.light_editor_filter.lower(), obj.name.lower(), re.I)]
        else:
            lights = [obj for obj in view_layer.objects if obj.type == 'LIGHT']

        # Group lights by collection or kind
        if scene.filter_light_types == 'COLLECTION':
            groups = {}
            for obj in lights:
                group_name = obj.users_collection[0].name if obj.users_collection else "No Collection"
                groups.setdefault(group_name, []).append(obj)
            for group_name, group_objs in groups.items():
                group_key = f"coll_{group_name}"
                collapsed = group_collapse_dict.get(group_key, False)
                header_box = layout.box()
                header_row = header_box.row(align=True)
                is_on_2 = group_checkbox_2_state.get(group_key, False)
                icon_2 = 'RADIOBUT_ON' if is_on_2 else 'RADIOBUT_OFF'
                op_2 = header_row.operator("light_editor.toggle_group_exclusive", text="", icon=icon_2, depress=is_on_2)
                op_2.group_key = group_key
                op_tri = header_row.operator("light_editor.toggle_group", text="",
                                             emboss=True, icon='DOWNARROW_HLT' if not collapsed else 'RIGHTARROW')
                op_tri.group_key = group_key
                header_row.label(text=group_name, icon='OUTLINER_COLLECTION')
                if not collapsed:
                    for obj in group_objs:
                        draw_main_row(header_box, obj)
                        if obj.light_expanded:
                            extra_box = header_box.box()
                            draw_extra_params(self, extra_box, obj, obj.data)
        elif scene.filter_light_types == 'KIND':
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
                    is_on_2 = group_checkbox_2_state.get(group_key, False)
                    icon_2 = 'RADIOBUT_ON' if is_on_2 else 'RADIOBUT_OFF'
                    op_2 = header_row.operator("light_editor.toggle_group_exclusive", text="", icon=icon_2, depress=is_on_2)
                    op_2.group_key = group_key
                    op_tri = header_row.operator("light_editor.toggle_group", text="",
                                                 emboss=True, icon='DOWNARROW_HLT' if not collapsed else 'RIGHTARROW')
                    op_tri.group_key = group_key
                    header_row.label(text=f"{kind} Lights", icon=f"LIGHT_{kind}")
                    if not collapsed:
                        for obj in groups[kind]:
                            draw_main_row(header_box, obj)
                            if obj.light_expanded:
                                extra_box = header_box.box()
                                draw_extra_params(self, extra_box, obj, obj.data)
        else:
            sorted_lights = sorted(lights, key=lambda o: o.name.lower())
            box = layout.box()
            box.label(text="All Lights (Alphabetical)", icon='LIGHT_DATA')
            for obj in sorted_lights:
                draw_main_row(box, obj)
                if obj.light_expanded:
                    extra_box = box.box()
                    draw_extra_params(self, extra_box, obj, obj.data)

@persistent
def LE_check_lights_enabled(dummy):
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            if obj.type == 'LIGHT':
                if obj.hide_viewport and obj.hide_render:
                    obj.light_enabled = False
                else:
                    obj.light_enabled = True

@persistent
def LE_clear_handler(dummy):
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            obj.light_enabled = not (obj.hide_viewport and obj.hide_render)
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            old_group = getattr(obj, "lightgroup", "")
            if old_group:
                obj.lightgroup = old_group
            obj.light_enabled = not (obj.hide_viewport and obj.hide_render)

def icon_Load():
    import bpy.utils.previews
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
    custom_icons.load("SELECT_TRUE", os.path.join(icons_dir, "select_true.png"), 'IMAGE')
    custom_icons.load("SELECT_FALSE", os.path.join(icons_dir, "select_false.png"), 'IMAGE')

custom_icons = None

# -------------------------------------------------------------------------
# Register operators used in the panel (switch mode buttons etc.)
# -------------------------------------------------------------------------
classes = (
    LIGHT_OT_ToggleGroup,
    LIGHT_OT_ToggleGroupExclusive,
    LIGHT_OT_ClearFilter,
    LIGHT_OT_SelectLight,
    LIGHT_PT_editor,
)

# Global to keep track of whether classes are registered
class_registration_status = {}

# Initialize global variables
custom_icons = None
class_registration_status = {}

def register():
    global custom_icons, class_registration_status
    print("Starting registration process")

    # Load icons
    if custom_icons is None:
        icon_Load()

    # Initialize class registration status
    if not class_registration_status:
        class_registration_status = {cls.__name__: False for cls in classes}

    # Register properties
    bpy.types.Scene.current_active_light = bpy.props.PointerProperty(type=bpy.types.Object)
    bpy.types.Scene.current_exclusive_group = bpy.props.StringProperty()

    bpy.types.Light.lightgroup = bpy.props.StringProperty(name="Light Group", default="")
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

    bpy.types.Scene.filter_light_types = EnumProperty(
        name="Type",
        description="Filter light by type",
        items=(
            ('NO_FILTER', 'All', 'Show all lights alphabetically'),
            ('KIND', 'Kind', 'Filter lights by Kind'),
            ('COLLECTION', 'Collection', 'Filter lights by Collections'),
        ),
        update=update_light_types
    )
    bpy.types.Object.light_selected = BoolProperty(
        name="Selected",
        get=get_light_selected,
        set=set_light_selected
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
    bpy.types.Light.soft_falloff = BoolProperty(default=False)
    bpy.types.Light.max_bounce = IntProperty(default=0, min=0, max=10)
    bpy.types.Light.multiple_instance = BoolProperty(default=False)
    bpy.types.Light.shadow_caustic = BoolProperty(default=False)
    bpy.types.Light.spread = FloatProperty(default=0.0, min=0.0, max=1.0)

    # Register handlers
    if LE_clear_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(LE_clear_handler)
    if LE_check_lights_enabled not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(LE_check_lights_enabled)

    # Register classes
    for cls in classes:
        if not class_registration_status[cls.__name__]:
            try:
                bpy.utils.register_class(cls)
                class_registration_status[cls.__name__] = True
            except Exception as e:
                print(f"Failed to register {cls.__name__}: {e}")

def unregister():
    global custom_icons, class_registration_status
    print("Starting unregistration process")

    # Remove handlers
    if LE_clear_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(LE_clear_handler)
    if LE_check_lights_enabled in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(LE_check_lights_enabled)

    # Unregister properties
    for prop in ['current_active_light', 'current_exclusive_group', 'light_editor_filter', 'filter_light_types']:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for prop in ['light_selected', 'light_enabled', 'light_turn_off_others', 'light_expanded']:
        if hasattr(bpy.types.Object, prop):
            delattr(bpy.types.Object, prop)
    for prop in ['soft_falloff', 'max_bounce', 'multiple_instance', 'shadow_caustic', 'spread']:
        if hasattr(bpy.types.Light, prop):
            delattr(bpy.types.Light, prop)

    # Unregister classes
    for cls in reversed(classes):
        if class_registration_status.get(cls.__name__, False):
            try:
                bpy.utils.unregister_class(cls)
                class_registration_status[cls.__name__] = False
            except Exception as e:
                print(f"Failed to unregister {cls.__name__}: {e}")

    # Remove icons
    if custom_icons:
        bpy.utils.previews.remove(custom_icons)
        custom_icons = None

if __name__ == "__main__":
    if not bpy.app.background:
        if not hasattr(bpy.types, "LIGHT_PT_editor"):
            register()