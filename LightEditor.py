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

# Dictionaries to store states
group_checkbox_1_state = {}      # First button on/off per group_key (ON by default)
group_lights_original_state = {} # Stores original light states for each group
group_collapse_dict = {}         # Whether each group is collapsed

def update_render_layer(self, context):
    selected = self.selected_render_layer
    # Iterate over the scene’s view layers:
    for vl in context.scene.view_layers:
        if vl.name == selected:
            context.window.view_layer = vl
            break

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

def update_group_by_collection(self, context):
    if self.light_editor_group_by_collection:
        self.light_editor_kind_alpha = False

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
    # Draw the default light properties UI in the provided box
    if light and isinstance(light, bpy.types.Light):
        # Copy the layout drawing logic from DATA_PT_light
        layout = box

        # Display the 4 light type buttons in a single row
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

        # EEVEE
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
    """Default tooltip for Toggle Group All Off"""
    bl_idname = "light_editor.toggle_group_all_off"
    bl_label = "Toggle Group All Off"
    group_key: StringProperty()

    @classmethod
    def description(cls, context, properties):
        # Dynamically set the tooltip based on the grouping mode
        scene = context.scene
        if scene.filter_light_types == 'COLLECTION':
            return "Turn ON/OFF Collection"
        return "Toggle all lights in the group off or restore them"

    def execute(self, context):
        global group_checkbox_1_state, group_lights_original_state
        is_on = group_checkbox_1_state.get(self.group_key, True)
        group_objs = self._get_group_objects(context, self.group_key)

        if is_on:
            # Turn off lights or hide collections based on mode
            if self.group_key.startswith("coll_"):  # Collection Mode
                coll_name = self.group_key[5:]
                collection = bpy.data.collections.get(coll_name)
                if collection:
                    collection.hide_viewport = True
                    collection.hide_render = True
                    # Store the state so we can restore it later
                    collection_state = {'viewport': collection.hide_viewport, 'render': collection.hide_render}
                    group_lights_original_state[self.group_key] = collection_state
            elif self.group_key.startswith("kind_"):  # Kind Mode
                original_states = {}
                for obj in group_objs:
                    if obj.type == 'LIGHT':
                        original_states[obj.name] = obj.light_enabled
                        obj.light_enabled = False
                group_lights_original_state[self.group_key] = original_states
            group_checkbox_1_state[self.group_key] = False
        else:
            # Restore lights or collections visibility based on mode
            if self.group_key.startswith("coll_"):  # Collection Mode
                coll_name = self.group_key[5:]
                collection = bpy.data.collections.get(coll_name)
                if collection:
                    # Restore the collection visibility state
                    collection.hide_viewport = False
                    collection.hide_render = False
                    if self.group_key in group_lights_original_state:
                        del group_lights_original_state[self.group_key]
            elif self.group_key.startswith("kind_"):  # Kind Mode
                original_states = group_lights_original_state.get(self.group_key, {})
                for obj in group_objs:
                    if obj.type == 'LIGHT':
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
        
        # Get all lights in the current view layer
        if filter_pattern:
            all_lights = [obj for obj in context.view_layer.objects
                          if obj.type == 'LIGHT' and re.search(filter_pattern, obj.name, re.I)]
        else:
            all_lights = [obj for obj in context.view_layer.objects if obj.type == 'LIGHT']
        
        # Handle "Collection" mode
        if scene.filter_light_types == 'COLLECTION' and group_key.startswith("coll_"):
            coll_name = group_key[5:]
            return [obj for obj in all_lights
                    if (obj.users_collection and obj.users_collection[0].name == coll_name)
                    or (not obj.users_collection and coll_name == "No Collection")]
        
        # Handle "Kind" mode
        if scene.filter_light_types == 'KIND' and group_key.startswith("kind_"):
            kind = group_key[5:]
            return [obj for obj in all_lights if obj.data.type == kind]
        
        return []
    
    
class LIGHT_OT_ClearFilter(bpy.types.Operator):
    """Clear Filter Types"""
    bl_idname = "le.clear_light_filter"
    bl_label = "Clear Filter"

    @classmethod
    def description(cls, context, properties):
        scene = context.scene
        if scene.filter_light_types == 'COLLECTION':
            return "Turn ON/OFF Collection"
        elif scene.filter_light_types == 'KIND':
            return "Turn ON/OFF All Lights of This Kind"
        return "Toggle all lights in the group off or restore them"

    def execute(self, context):
        global group_checkbox_1_state, group_lights_original_state
        is_on = group_checkbox_1_state.get(self.group_key, True)
        group_objs = self._get_group_objects(context, self.group_key)
        
        if is_on:
            # Turn off all lights/collections in the group
            if self.group_key.startswith("coll_"):  # Collection Mode
                coll_name = self.group_key[5:]
                collection = bpy.data.collections.get(coll_name)
                if collection:
                    collection.hide_viewport = True
                    collection.hide_render = True
                    # Store the state so we can restore it later
                    collection_state = {'viewport': collection.hide_viewport, 'render': collection.hide_render}
                    group_lights_original_state[self.group_key] = collection_state
            elif self.group_key.startswith("kind_"):  # Kind Mode
                for obj in group_objs:
                    if obj.type == 'LIGHT':
                        obj.hide_viewport = True
                        obj.hide_render = True
                        # Store the original state
                        group_lights_original_state.setdefault(self.group_key, {})[obj.name] = {
                            'viewport': obj.hide_viewport,
                            'render': obj.hide_render
                        }
            group_checkbox_1_state[self.group_key] = False
        else:
            # Restore the original state of all lights/collections in the group
            if self.group_key.startswith("coll_"):  # Collection Mode
                coll_name = self.group_key[5:]
                collection = bpy.data.collections.get(coll_name)
                if collection:
                    collection.hide_viewport = False
                    collection.hide_render = False
                    if self.group_key in group_lights_original_state:
                        del group_lights_original_state[self.group_key]
            elif self.group_key.startswith("kind_"):  # Kind Mode
                for obj in group_objs:
                    if obj.type == 'LIGHT':
                        obj.hide_viewport = False
                        obj.hide_render = False
                        # Remove the stored state
                        if self.group_key in group_lights_original_state and obj.name in group_lights_original_state[self.group_key]:
                            del group_lights_original_state[self.group_key][obj.name]
            group_checkbox_1_state[self.group_key] = True
        
        # Redraw the UI
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
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

# -------------------------------------------------------------------------
# 5) The main panel
# -------------------------------------------------------------------------
class LIGHT_PT_editor(bpy.types.Panel): 
    """Panel to view/edit lights with grouping, filtering, and per-group toggles."""
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

        row = layout.row(align=True)
        row.prop(scene, "light_editor_filter", text="", icon="VIEWZOOM")
        row.operator("le.clear_light_filter", text="", icon='PANEL_CLOSE')
        
        # Only display the render layer dropdown when in Collection mode.
        if scene.filter_light_types == 'COLLECTION':
            row = layout.row()
            row.prop(scene, "selected_render_layer", text="Render Layer")

        # Get lights from the active view layer
        if scene.light_editor_filter:
            lights = [obj for obj in context.view_layer.objects
                      if obj.type == 'LIGHT' and re.search(scene.light_editor_filter.lower(), obj.name.lower(), re.I)]
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
                op_tri = header_row.operator("light_editor.toggle_group",
                                             text="",
                                             emboss=True,
                                             icon='RIGHTARROW' if collapsed else 'DOWNARROW_HLT')
                op_tri.group_key = group_key
                header_row.label(text=group_name, icon='OUTLINER_COLLECTION')

                if not collapsed:
                    for obj in group_objs:
                        draw_main_row(header_box, obj)
                        if obj.light_expanded:
                            extra_box = header_box.box()
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
                                draw_extra_params(self, extra_box, obj, obj.data)
                                
        else:
            # Alphabetical order mode
            sorted_lights = sorted(lights, key=lambda o: o.name.lower())
            box = layout.box()
            box.label(text="All Lights (Alphabetical)", icon='LIGHT_DATA')
            for obj in sorted_lights:
                draw_main_row(box, obj)
                if obj.light_expanded: # Check if the light is expanded
                    extra_box = box.box()
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
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            # Set enable correct
            if (obj.hide_viewport == False and obj.hide_render == False):
                context.view_layer.objects[obj.name].light_enabled = True
            else:
                context.view_layer.objects[obj.name].light_enabled = False

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
    LIGHT_OT_ClearFilter,
    LIGHT_OT_SelectLight,
    LIGHT_PT_editor,
)

def register():
    icon_Load()
    # Register scene properties
    print("Light Editor add-on registered successfully.")
    bpy.types.Scene.current_active_light = bpy.props.PointerProperty(type=bpy.types.Object)
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

    bpy.types.Scene.filter_light_types = EnumProperty(
        name="Type",
        description="Filter light by type",
        items=(('NO_FILTER', 'All', 'Show All no filter (Alphabetical)', 'NONE', 0), 
               ('KIND', 'Kind', 'Filter lights by Kind', 'LIGHT_DATA', 1),
               ('COLLECTION', 'Collection', 'Filter lights by Collections', 'OUTLINER_COLLECTION', 2)),
    )

    # Register Light properties
    bpy.types.Light.soft_falloff = BoolProperty(default=False)
    bpy.types.Light.max_bounce = IntProperty(default=0, min=0, max=10)
    bpy.types.Light.multiple_instance = BoolProperty(default=False)
    bpy.types.Light.shadow_caustic = BoolProperty(default=False)
    bpy.types.Light.spread = FloatProperty(default=0.0, min=0.0, max=1.0)
    
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
    bpy.app.handlers.load_post.append(LE_check_lights_enabled)

def unregister():
    global custom_icons

    # Remove custom icons
    if custom_icons:
        bpy.utils.previews.remove(custom_icons)
        custom_icons = None

    # Remove handlers
    if LE_clear_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(LE_clear_handler)
    if LE_check_lights_enabled in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(LE_check_lights_enabled)

    # Unregister scene properties
    if hasattr(bpy.types.Scene, 'current_active_light'):
        del bpy.types.Scene.current_active_light
    if hasattr(bpy.types.Scene, 'selected_render_layer'):
        del bpy.types.Scene.selected_render_layer

    # Unregister other properties
    if hasattr(bpy.types.Scene, 'light_editor_filter'):
        del bpy.types.Scene.light_editor_filter
    if hasattr(bpy.types.Scene, 'light_editor_kind_alpha'):
        del bpy.types.Scene.light_editor_kind_alpha
    if hasattr(bpy.types.Scene, 'light_editor_group_by_collection'):
        del bpy.types.Scene.light_editor_group_by_collection
    if hasattr(bpy.types.Light, 'soft_falloff'):
        del bpy.types.Light.soft_falloff
    if hasattr(bpy.types.Light, 'max_bounce'):
        del bpy.types.Light.max_bounce
    if hasattr(bpy.types.Light, 'multiple_instance'):
        del bpy.types.Light.multiple_instance
    if hasattr(bpy.types.Light, 'shadow_caustic'):
        del bpy.types.Light.shadow_caustic
    if hasattr(bpy.types.Light, 'spread'):
        del bpy.types.Light.spread
    if hasattr(bpy.types.Object, 'light_enabled'):
        del bpy.types.Object.light_enabled
    if hasattr(bpy.types.Object, 'light_turn_off_others'):
        del bpy.types.Object.light_turn_off_others
    if hasattr(bpy.types.Object, 'light_expanded'):
        del bpy.types.Object.light_expanded

    # Unregister classes
    for cls in reversed(classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()