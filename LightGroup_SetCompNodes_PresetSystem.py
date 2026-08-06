'''
    TODO
    Make it work on all nodegroups > now it works per single node groups
    add export method so we can reuse it perhaps on regeneration

'''
# Ray Mairlot
# StackExchange
# https://blender.stackexchange.com/a/24808/7631


import bpy, os, json
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, FloatVectorProperty, CollectionProperty 
from bpy.types import PropertyGroup, Operator, Menu


def addNodeInputs(context,ng, idx):
    inputList = {}
    i = 0
    inputList[i] = ng
    
    # print(f"len inputs {len(ng.inputs)}")
    set = []
    i+=0
     
    for nr in range(0,len(ng.inputs),3):
        # print(i)
        # print(f"nr {nr}")
        newPresetItem = ng.presetList_PG[f"Preset {idx}"].presetItemList.add()
#        newPresetItem = ng.presetList_PG[f"Preset {idx}"].presetItemList.add()
        inpt = ng.inputs[i]
        
        if inpt.type == 'VALUE':
            set.append((ng.inputs[i].default_value))
        newPresetItem.factor = ng.inputs[i].default_value
        
#        print(f"nr {nr+1} name {ng.inputs[4].name}")
#        print(f"nr {nr+1} name {ng.inputs[i+1].name}")
        if inpt.type == 'RGBA' and inpt.name != 'Color':
            set.append((ng.inputs[i].name))
        newPresetItem.name = ng.inputs[i+1].name
                
        if inpt.type == 'RGBA' and inpt.links == ():
            set.append((ng.inputs[i].default_value[0], ng.inputs[i+2].default_value[1], ng.inputs[i].default_value[2], ng.inputs[i].default_value[3]))
        newPresetItem.color = ng.inputs[i+2].default_value 
        
        i+=3
        
        
# Print Stats
#    i=0
#    j=1
#    print(f"set {set}")
#    print(f"len(set) {len(set)}")
#    #print(set[1*2])
#    for item in range(0,len(set), 3):
#        print(f"i {i}")
#        print(f"item {item}")
#        inputList[j] = set[i],set[i+1],set[i+2]
#        print(f"inputList {inputList}")
#        i+=3
#        j+=1
#        

#    print("\n\n")
#    print(inputList)

def addPreset_OP(context):
    scene = bpy.context.scene
#    ng = bpy.data.node_groups
    ng = context.active_node
    idx = len(ng.presetList_PG)+1
#    print(idx)
    newPresetList = ng.presetList_PG.add()
    newPresetList.name= f"Preset {idx}"
    newPresetList.description = "Stored preset"
    addNodeInputs(context,ng, idx)


class presetItem_PG(PropertyGroup):
    name : StringProperty(name="LG", description="Lightgroup Output channel.")
    factor : FloatProperty(name="Factor", description="Light influence, the slider sets the power of the light.")
    color: FloatVectorProperty(
            name='Color',
            description="Sets the color for the lightgroup, black is the original colors as setup in the scene. Any other color will override that.",
            size=4,
            precision=3,
            subtype='COLOR',
            min=0.0,
            max=1.0
        )


class presetList_PG(PropertyGroup):
    name : StringProperty(name="Preset", description="Stored preset Lightgroup Output channel.")
    presetItemList : CollectionProperty(type=presetItem_PG)    

# UIlist Example
# Source https://gist.github.com/dustractor/66cc0f990c2edaebc6b1f1d1f65838a2
bl_info = {
    "name": "CollectionProperty Test",
    "blender": (2,80,0),
    "category": "Test"
}


class LGH_OT_move(bpy.types.Operator):
    bl_idname = "nghelper.move"
    bl_label = "move"
    
    index_from: IntProperty(default=-1)
    index_to: IntProperty(default=-1)
    
    def execute(self,context):
#        context.active_object.testitems.move(self.index_from,self.index_to)
        
        node = context.active_node
        if node.type == 'GROUP':
            node.presetList_PG.move(self.index_from,self.index_to)
            node.presetList_PG_idx = self.index_to
        return {"FINISHED"}


#@_
class LGH_OT_add(bpy.types.Operator):
    bl_idname = "nghelper.add"
    bl_label = "add"
    
    def execute(self,context):
#        ob = context.active_object
#        obs = [_.name for _ in context.selected_objects if _ != ob]
#        for eachob in obs:
#            newitem = ob.testitems.add()
#            newitem.name = eachob

        addPreset_OP(context)
        return {"FINISHED"}

class LGH_OT_clear(bpy.types.Operator):
    bl_idname = "nghelper.clear"
    bl_label = "clear"
    bl_description = "Clear all presets from list"
    
    def execute(self,context):
        node = context.active_node
        node.presetList_PG.clear()
        return {"FINISHED"}


#@_
class LGH_OT_remove(bpy.types.Operator):
    bl_idname = "nghelper.remove"
    bl_label = "remove"
    
    index: IntProperty(default=-1)
    
    def execute(self,context):
#        context.active_object.testitems.remove(self.index)
#        ng = context.nodes.active

        node = context.active_node
        if node.type == 'GROUP':
            node.presetList_PG.remove(self.index)
        return {"FINISHED"}

#@_
class LGH_PT_panel(bpy.types.Panel):
    bl_idname = "nghelper.panel"
    bl_label = "LGH LightGroup Relight"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Node"
#    bl_category = "LGH LightGroup Relight"
    
    @classmethod
    def poll(self,context):
        ng = context.active_node
        return ng is not None and ng.type =='GROUP'
    
    def draw(self,context):
        layout = self.layout
        node = context.active_node
        
        layout.use_property_split = True
        layout.use_property_decorate = False

#        split = layout.split(factor=0.92)
#        col1,col2 = split.column(),split.column(align=True)

#        col1.template_list("LGH_UL_uilist","custom_id_blah",
#                   node,"presetList_PG",
#                   node,"presetList_PG_idx")


#        col2.operator("nghelper.clear",text="",icon="PANEL_CLOSE")
#        col2.operator("nghelper.reset_colors",text="",icon="LOOP_BACK")
#        col2.operator("nghelper.add",text="",icon="ADD")
#        col2.operator("nghelper.remove",text="",icon="REMOVE").index = node.presetList_PG_idx
#        col2.separator()
        
        row = layout.row()
        row.template_list("LGH_UL_uilist","custom_id_blah",node,"presetList_PG",node,"presetList_PG_idx")

        col = row.column(align=True)
        col.operator("nghelper.clear",text="",icon="PANEL_CLOSE")
        col.operator("nghelper.reset_colors",text="",icon="LOOP_BACK")
        col.operator("nghelper.add",text="",icon="ADD")
        col.operator("nghelper.remove",text="",icon="REMOVE").index = node.presetList_PG_idx

        op = col.operator("nghelper.move",text="",icon="TRIA_UP")
        op.index_from = node.presetList_PG_idx
        op.index_to = node.presetList_PG_idx - 1
        op = col.operator("nghelper.move",text="",icon="TRIA_DOWN")
        op.index_from = node.presetList_PG_idx
        op.index_to = node.presetList_PG_idx + 1


class LGH_PT_Preset_Settings(bpy.types.Panel):
    bl_label = "Preset Settings"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_parent_id = "nghelper.panel"
    COMPAT_ENGINES = {'CYCLES'}
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        node = context.active_node
        
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        if node.presetList_PG_idx > -1:
#            box = layout.box()

            active_item = node.presetList_PG[node.presetList_PG_idx]
#            col = layout.column(align=True, heading=)
#            col.label(text=active_item.name)
#            col.prop(active_item, "name")
            for sub_item in active_item.presetItemList:
                heading = layout.column(align=True, heading=sub_item.name)
                heading = layout.column(align=True)                
                
                heading.prop(sub_item, "name", emboss=False)       
#                heading.label(text=sub_item.name)
                heading.prop(sub_item, "factor")
                heading.prop(sub_item,"color")
#                col.separator()

class LGH_UL_uilist(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
#        props = context.active_object.testitems
        props = context.active_node.presetList_PG
#        cam = item
#        print(cam.name)
        row = layout.row(align=True)

        row.label(text="",icon="COLOR")
        
        applyPreset = row.operator("nghelper.apply_preset",text="", icon="BRUSH_DATA", emboss=False)
        applyPreset.index = index 
        
        row.separator()
        row.prop(item, "name", text="")


class LGH_OT_reset_colors(Operator):
    bl_idname = "nghelper.reset_colors"
    bl_label = "Reset Colors"
    bl_description = "Reset colors & inputs to original value"

    index : IntProperty(default=0,name="Item")

#    @classmethod
#    def poll(cls, context):
#        return (len(context.scene.save_cam_collection) > 0)

    def execute(self, context):  
        ng = context.active_node
        idx = self.index
        i=0
        for inp in ng.inputs:
#            print(inp)
            if inp.type == 'VALUE':
                inp.default_value = 1
                
            if inp.type == 'RGBA' and inp.links == ():
                inp.default_value =[0,0,0,1]
            i+=1
            
        self.report({'INFO'}, "Colors Reset")
        return{'FINISHED'}

      
class LGH_OT_apply_preset(Operator):
    bl_idname = "nghelper.apply_preset"
    bl_label = "Apply Colors"
    bl_description = "Applies the recorded colors"

    index : IntProperty(default=0,name="Item")

#    @classmethod
#    def poll(cls, context):
#        return (len(context.scene.save_cam_collection) > 0)

    def execute(self, context):  
        ng = context.active_node
        idx = self.index
        newPresetItem = ng.presetList_PG[idx].presetItemList
#        print(newPresetItem.keys)
#        print(len(newPresetItem.keys()))

        i = 0
        for inp in range(0,len(newPresetItem.keys())):
            # get name from color input
            name = newPresetItem.keys()[i]
#            print(f"name {name}")
            # get idx from input
            # https://devtalk.blender.org/t/get-inputs-index-of-the-node-connected-to-the-output-of-a-given-node-etc/19594/2?u=romboutversluijs
            idx = int(ng.inputs[name].path_from_id()[:-1].split("[")[-1])
#            print(idx)
#            print(newPresetItem[i].factor)
#            print(newPresetItem[i].color)
            ng.inputs[idx].name = newPresetItem[inp].name
            ng.inputs[idx-1].default_value = newPresetItem[inp].factor
            ng.inputs[idx+1].default_value = newPresetItem[inp].color
#            print(newPresetItem.keys()[i+1])
#            print(newPresetItem.keys()[i+2])
#            print(inp)
            i+=1
            
        self.report({'INFO'}, "Applied Preset")
        return{'FINISHED'}

# Settings Menu
class LGH_MT_settings_menu(Menu):
    bl_idname = "LGH_MT_settings_menu"
    bl_label = "Settings"
    bl_description = "Settings"

    def draw(self, context):
        scn = context.scene        
        layout = self.layout

        layout.menu("LGH_MT_ImportExport")
        layout.menu("LGH_MT_RenderViews")
        # layout.label(text = 'Import / Export:')
        


# Addon path
addon_dir = os.path.dirname(__file__)

## set output path and file name (set your own)
save_path = 'C:/Users/romboutversluijs/Desktop/'
file_name = os.path.join(addon_dir, "savecams_camera_settings.json")

def get_active_camera(context):
    # 1 - Export data as JSON file
    # dict with all your data
    scn = context.scene
    cam = scn.save_cam_collection[scn.save_cam_collection_index]
    return cam

def export_camera_settings(context):
    scn = context.scene
    props = scn.save_cam_other
#    print(cam.camRots[0])
#    print(cam.camRots[1])
#    print(cam.camRots[2])
#    a, b, c = map(degrees, (cam.camLocs[0], cam.camLocs[1], cam.camLocs[2]))
#    print (a, b, c)
#    print(bpy.context.active_object.rotation_euler)

#    print(bpy.context.active_object.rotation_euler[0])
#    print(degrees(bpy.context.active_object.rotation_euler[0]))
    #solution saving sub list
    # https://stackoverflow.com/a/24077013/2175375
    # if props.all_cameras:
    scn = context.scene
    export = scn.tmp_list_cam_collection
    cam_export_settings_list = []
    for cam in range(len(scn.save_cam_collection)):
        if export[cam].import_camera:
            cam = scn.save_cam_collection[cam]
            cam_export_settings = {
            "cams" : {
                "cindex": cam.cindex,
                "name": cam.name,
                "camLocs": [
        #    #        creat_sub_list(cam.camLocs)
                    {"0" : cam.camLocs[0]},
                    {"1" : cam.camLocs[1]},
                    {"2" : cam.camLocs[2]}
                ],
                "camRots": [
                    {"0" : cam.camRots[0]},
                    {"1" : cam.camRots[1]},
                    {"2" : cam.camRots[2]}
                ],
                "type": cam.type,
                "flen": cam.flen,
                "fow": cam.fow,
                "lens_unit": cam.lens_unit,
                "ortho_scale": cam.ortho_scale,
                "shift_x": cam.shift_x,
                "shift_y": cam.shift_y,
                "res_x": cam.res_x,
                "res_y": cam.res_y,
                
                "camFilmW": cam.camFilmW,
                "camFilmH": cam.camFilmH,
                "sensFit": cam.sensFit,
                "dof": cam.dof,
                "dofDist": cam.dofDist,
                "aper_fstop" : cam.aper_fstop,
                "aper_blades" : cam.aper_blades,
                "aper_rotation" : cam.aper_rotation,
                "aper_ratio" : cam.aper_ratio,
                
                "save_cam_collection_index": scn.save_cam_collection_index,
                },
            }
            cam_export_settings_list.append(cam_export_settings)
    return cam_export_settings_list


# Export camera settings
class SAVECAMS_OT_export_camera_settings(Operator):
    bl_idname = "savecams.export_camera_settings"
    bl_label = "Export Camera Settings"
    bl_description = "Export active camera settings or cameras"
    # bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (len(context.scene.save_cam_collection) > 0)

    def execute(self, context):
        # return error
        # TypeError: Object of type bpy_prop_array is not JSON serializable
        data = json.dumps(export_camera_settings(context), indent=1, ensure_ascii=True)
        if save_json_data(file_name, data):
            self.report({'INFO'}, 'Camera data exported')
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        scn = context.scene
        props = scn.save_cam_other
        data = scn.save_cam_collection
        scn.tmp_list_cam_collection.clear()

        try:
            # if len(data[0]['cams']):
            for cam in range(len(data)):
                export_camera_list(context, data[cam])
            # else:
        except Exception as e:
            export_camera_list(context, data)
            # print("Camera settings is %s" % e)

        return wm.invoke_props_dialog(self, width=450) #
        # return {'RUNNING_MODAL'} 
        # return wm.invoke_popup(self, width=600) #

    def draw(self, context):
        layout = self.layout
        # layout.use_property_split = True
        # layout.use_property_decorate = False

        scn = context.scene
        props = context.scene.save_cam_other

        layout.label(text="Select camera's to be exported")
        col = layout.column()
        col.template_list("SAVECAMS_UL_tmp_list_cam_settings", "", context.scene, "tmp_list_cam_collection", context.scene, "tmp_list_cam_collection_index")


def save_json_data(file_name, data):
    ## write JSON file
    with open(file_name, 'w') as outfile:
       outfile.write(data + '\n')
    return True


def load_json_data(file_name):
    # 2 - Import data from JSON file
    # read JSON file
    with open(file_name, 'r') as fp:
        data_file = json.load(fp)
    return data_file



# Import camera settings
class SAVECAMS_OT_import_camera_settings(Operator):
    bl_idname = "savecams.import_camera_settings"
    bl_label = "Import Camera Settings"
    bl_description = "Import active camera settings or cameras"
    bl_options = {'UNDO'}
    # bl_options = {'UNDO', 'REGISTER'}
    
    all_cameras : BoolProperty(default=True)
    as_camera : BoolProperty(description="Import the camera data as real camera's, if unchecked, camera data will be added tp the existing list.")

    @classmethod
    def poll(cls, context):
        return os.path.exists(file_name)

    # def cancel(self, context):
    # 	scn = context.scene
    # 	scn.tmp_list_cam_collection.clear()
    # 	self.report({'WARNING'}, "Cancelled")

    def execute(self, context):
        scn = context.scene
        props = context.scene.save_cam_other
        import_camera = context.scene.tmp_list_cam_collection
        data = load_json_data(file_name)

        try:
            if len(data[0]['cams']):
                for cam in range(len(data)):
                    if import_camera[cam]['import_camera']:
                        tmp_list_camera_settings_item(context, data[cam]['cams'])
        except Exception as e:
            tmp_list_camera_settings_item(context, data)
            print("Error importing camera data \rError > %s" % e)


        # os.remove(file_name)
        # scn.tmp_list_cam_collection.clear()
        self.report({'INFO'}, "Camera data imported")
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        scn = context.scene
        props = scn.save_cam_other
        scn.tmp_list_cam_collection.clear()

        data = load_json_data(file_name)

        try:
            if len(data[0]['cams']):
                for cam in range(len(data)):
                    import_camera_list(context, data[cam]['cams'])
            # else:
        except Exception as e:
            import_camera_list(context, data)
            print("Camera settings is %s" % e)

        # return self.execute(context)
        # if wm.invoke_props_dialog(self, width=600): 
        # # context.window_manager.invoke_confirm(self, event):
        # 	return self.execute(context)
        # else:
        # 	return {'CANCELLED'}
        return wm.invoke_props_dialog(self, width=450) #
        # return {'RUNNING_MODAL'} 
        # return wm.invoke_popup(self, width=600) #

    def draw(self, context):
        layout = self.layout
        # layout.use_property_split = True
        # layout.use_property_decorate = False

        scn = context.scene
        props = context.scene.save_cam_other
        layout.label(text="Select camera's to be imported")
        layout.prop(props, "as_camera")
        col = layout.column()
        col.template_list("SAVECAMS_UL_tmp_list_cam_settings", "", context.scene, "tmp_list_cam_collection", context.scene, "tmp_list_cam_collection_index")


def tmp_list_camera_settings_item(context, data):
    scn = context.scene
    props = context.scene.save_cam_other

    if not props.as_camera:
        item = context.scene.save_cam_collection.add()
        item.name =data['name']
        item.camLocs = [data['camLocs'][0]['0'],data['camLocs'][1]['1'],data['camLocs'][2]['2']]
        item.camRots = [data['camRots'][0]['0'],data['camRots'][1]['1'],data['camRots'][2]['2']]
        item.type = data['type']
        try:
            print("Focal Length %s" % data['flen'])
            item.lens_unit = data['lens_unit']
            if item.lens_unit == 'MILLIMETERS':
                item.flen = data['flen']
            else:
                item.angle = data['fow'] 
        except Exception as e:
            item.flen = data['flen']
            item.lens_unit = "MILLIMETERS"
            # print("Focal lengt setting %s" % data['flen'])
            # if data['flen']:
            # else:
            # 	item.flen = 50
            print("\n[{}]\n{}\n\nError:\n{}".format(__name__, "Field of View was not set, reset to default 50", e))
            pass
        try:
            item.ortho_scale = data['ortho_scale'] 
        except Exception as e:
            item.ortho_scale = 5
            print("\n[{}]\n{}\n\nError:\n{}".format(__name__, "Orthographic Scaling was not saved, reset to default 6", e))
            pass
        item.shift_x = data['shift_x']
        item.shift_y = data['shift_y']
        item.camFilmW = data['camFilmW']
        item.camFilmH = data['camFilmH']
        item.sensFit = data['sensFit']
        # if data["dof"]:
        try:
            item.dofDist = data['dofDist']
            item.aper_fstop = data['aper_fstop']
            item.aper_blades = data['aper_blades']
            item.aper_rotation = data['aper_rotation']
            item.aper_ratio = data['aper_ratio']
            # do as last, if fails, we do have other settings
            item.dof = data['dof'] # if data['dof'] != "" else ""
        except Exception as e:
            print("\n[{}]\n{}\n\nError:\n{}".format(__name__, "DOF object or data not found", e))
            pass

        item.res_x = data['res_x']
        item.res_y = data['res_y']
        context.scene.save_cam_collection_index = len(context.scene.save_cam_collection)-1
    else:
        # cam
        bpy.ops.object.camera_add(enter_editmode=False, align='VIEW', location=(0, 0, -0), rotation=(0,0,0), scale=(1, 1, 1))
        camA = context.active_object

        # set Camera   
        camA.name = data['name']
        camA.data.name = data['name']

        # Loc & Rot
        camA.location[0] = float(data['camLocs'][0]['0'])
        camA.location[1] = float(data['camLocs'][1]['1'])
        camA.location[2] = float(data['camLocs'][2]['2'])
        camA.rotation_euler[0] = float(data['camRots'][0]['0'])
        camA.rotation_euler[1] = float(data['camRots'][1]['1'])
        camA.rotation_euler[2] = float(data['camRots'][2]['2'])

        #    print(degrees(float(data['camRots'][0]['0'])))
        #    print(degrees(float(data['camRots'][1]['1'])))
        #    print(degrees(float(data['camRots'][2]['2'])))
        #    camA.rotation_euler[0] = 1.5

        # cam data
        camA.data.type = data['type']
        camA.data.lens = data['flen']
        try:
            camA.data.ortho_scale = data['ortho_scale'] 
        except Exception as e:
            camA.data.ortho_scale = 5
            print("\n[{}]\n{}\n\nError:\n{}".format(__name__, "Orthographic Scaling was not saved, reset to default 6", e))
            pass
        try:
            camA.data.lens_unit = data['lens_unit']
            if camA.data.lens_unit == 'MILLIMETERS':
                camA.data.lens = data['flen']
            else:
                camA.data.angle = data['angle']
        except Exception as e:
            camA.data.lens_unit = "MILLIMETERS"
            if data['flen']:
                camA.data.lens = data['flen']
            else:
                camA.data.lens = 50
            print("\n[{}]\n{}\n\nError:\n{}".format(__name__, "Field of View was not set", e))
            pass
        camA.data.shift_x = data['shift_x']
        camA.data.shift_y = data['shift_y']

        camA.data.sensor_width = data['camFilmW']
        camA.data.sensor_height = data['camFilmH']
        # print(data['dof'] != "")
        # print(data['dof'])
        camA.data.sensor_fit = data['sensFit']
        if data["dof"]:
            camA.data.dof.use_dof = True
            try:
                camA.data.dof.focus_distance = data['dofDist']
                camA.data.dof.aperture_fstop = data['aper_fstop']
                camA.data.dof.aperture_blades = data['aper_blades']
                camA.data.dof.aperture_rotation = data['aper_rotation']
                camA.data.dof.aperture_ratio = data['aper_ratio']
                # do as last, if fails, we do have other settings
                camA.data.dof.focus_object = bpy.data.objects[data['dof']]
            except Exception as e:
                print("\n[{}]\n{}\n\nError:\n{}".format(__name__, "DOF object not found: %s" % data['dof'], e))
                pass
        else:
            camA.data.dof.use_dof = False
        context.scene.render.resolution_x = data['res_x']
        context.scene.render.resolution_y = data['res_y']


# class SAVECAMS_OT_import_cam_add(Operator):
# 	bl_idname = "savecams.import_cam_add"
# 	bl_label = "Add"
# 	bl_description = "Add cam"

# 	def execute(self, context):
def import_camera_list(context, data):
    scn = context.scene
    # cam = obj.data
    item = context.scene.tmp_list_cam_collection.add()
    item.import_camera = True
    item.name = data['name']
    item.type = data['type']
    item.flen = data['flen']
    item.res_x = data['res_x']
    item.res_y = data['res_y']
    context.scene.tmp_list_cam_collection_index = len(context.scene.tmp_list_cam_collection)-1

def export_camera_list(context, data):
    scn = context.scene
    # cam = obj.data
    item = context.scene.tmp_list_cam_collection.add()
    item.import_camera = True
    item.name = data.name
    item.type = data.type
    item.flen = data.flen
    item.res_x = data.res_x
    item.res_y = data.res_y


classes = [
    presetItem_PG,
    presetList_PG,
    LGH_OT_move,
    LGH_OT_add,
    LGH_OT_clear,
    LGH_OT_remove,
    LGH_OT_apply_preset,
    LGH_OT_reset_colors,
    LGH_PT_panel,
    LGH_PT_Preset_Settings,
    LGH_UL_uilist
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    #    bpy.utils.register_class(LGH_UL_uilist)
#    list(map(bpy.utils.register_class,_()))
#    bpy.types.Object.testitems = CollectionProperty(type=TestItem)
#    bpy.types.Object.presetList_PG_idx = IntProperty(min=-1,default=-1)
    
    bpy.types.CompositorNodeGroup.presetList_PG = CollectionProperty(type=presetList_PG)
    bpy.types.CompositorNodeGroup.presetList_PG_idx = IntProperty(min=-1,default=-1)


def unregister():
#    del bpy.types.Object.testitems_i
#    del bpy.types.Object.testitems
    del bpy.types.CompositorNodeGroup.presetList_PG
    del bpy.types.CompositorNodeGroup.presetList_PG_idx

    
#    list(map(bpy.utils.unregister_class,_()))
    for cls in classes:
        bpy.utils.unregister_class(cls)
