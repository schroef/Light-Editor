'''
    TODO
    # ADD
    - preset system so we can store light setups
    
'''

import bpy
from bpy.props import EnumProperty


def get_renderlayers_exr(self, context):
    layers = []
    layers.append(("Choose...", "Choose...", "Select a collection this pose bone belongs to."))
    if bpy.app.version[0] >= 5:
            nt = context.scene.compositing_node_group
    else:
        nt = context.scene.node_tree

    # Check if its EXR multilayer
    if nt.nodes.active.bl_idname == 'CompositorNodeImage' and nt.nodes.active.layer !='':
        layer = nt.nodes.active.layer
        if len(layer) == 1:
            return layers.append((layer.name, layer.name, layer.name))
        else:
            for rlayer in layer:
                layers.append((layer.name, layer.name, layer.name))
            return layers

# def update_prop(self,context,prop): 
def set_bone_to_collection(self, context):
    bpy.ops.object.mode_set(mode='EDIT')
    arm = bpy.context.object.data
    boneCollections = {}
    bone_collections = arm.collections_all
    pbone = bpy.context.object.pose.bones[self.name]

    # print(f"pbone {pbone}")
    # print(f"self.name {pbone.pbone_collection}")

    bpy.ops.object.mode_set(mode='POSE')
    bone_collections[pbone.pbone_collection].assign(pbone)


def move_item_to_parent(context, parent, item):
    # from NODE_OT_interface_item_new > node.py > bl_operators
    snode = bpy.context.space_data
    tree = snode.edit_tree
    interface = tree.interface

    # Remember active item and position to determine target position.
    active_item = interface.active
    active_pos = active_item.position if active_item else -1

    if active_item:
        print("active_ite %s" % active_item.item_type)
        # Insert into active panel if possible, otherwise insert after active item.
        if active_item.item_type == 'PANEL' and item.item_type != 'PANEL':
            print("move to  panel")
            interface.move_to_parent(item, active_item, len(active_item.interface_items))
        else:
            print("move to none panel")
            print("interface %s" % interface)
            print("item %s" %item)
            print("active_item.parent %s" % active_item.parent)
            print("active_item %s" % active_item)
            interface.move_to_parent(item, active_item.parent, active_pos + 1)
    interface.active = item

    return


# generate composite nodes for viewlayer lightgroup
class NODE_OT_set_lightgroup_postprocess_nodes(bpy.types.Operator):
    bl_idname = "node.set_lightgroup_postprocess_nodes"
    bl_label = "Set Lightgroup Postprocess Nodes"

    render_layers : EnumProperty(items=get_renderlayers_exr) #, update=set_bone_to_collection)

    @classmethod
    def poll(cls, context):
        scene = bpy.context.scene
        if bpy.app.version[0] >= 5:
            nt = scene.compositing_node_group.nodes
            return (scene.compositing_node_group and
                    context.scene.render.engine == 'CYCLES' and
                    nt.active.bl_idname == 'CompositorNodeRLayers' or
                    nt.active.bl_idname == 'CompositorNodeImage' and nt.active.layer)
                    
        else:
            return (scene.use_nodes and
                    scene.render.engine == 'CYCLES' and
                    scene.node_tree.nodes.active.bl_idname == 'CompositorNodeRLayers')

    def execute(self, context):
        # get viewlayer node in composite node tree
        if bpy.app.version[0] >= 5:
            nt = context.scene.compositing_node_group
        else:
            nt = context.scene.node_tree

        viewlayer_node = nt.nodes.active
        viewlayer_name = viewlayer_node.layer

        # new nodes
        # Check if its EXR multilayer
        if nt.nodes.active.bl_idname == 'CompositorNodeImage' and nt.nodes.active.layer !='':
            print(nt.nodes.active.layer)
            if nt.nodes.active.layer == 'Composite':
                self.report({'INFO'}, "Please choose correct Render Layer from EXR layer")
                return {'CANCELLED'}
            # nt.nodes.active.layer = 'RenderLayer'
            lg_list = [output_item.name for output_item in nt.nodes.active.outputs if not output_item.name.find("Combined_")] # in output_item.name]
            lg_passes = [pass_name for pass_name in lg_list]
            print(f"lg_passes {lg_passes}")
        else:
            # get lightgroup passes in viewlayer node
            lg_list = [lightgroup_item.name for lightgroup_item in context.scene.view_layers[viewlayer_name].lightgroups]
            lg_passes = ['Combined_' + lightgroup_name for lightgroup_name in lg_list]
            print(f"lg_passes {lg_passes}")

        # when there is no lightgroup
        if len(lg_list) == 0:
        # if len(lg_list) == 0 or len(lg_list) == 1:
            self.report({'INFO'}, "No Lightgroup Items found")
            return {'CANCELLED'}

        # create group node
        group_node = nt.nodes.new(type='CompositorNodeGroup')
        group_node.location = (viewlayer_node.location[0] + 300, viewlayer_node.location[1])
        group_nt = bpy.data.node_groups.new(name='LG_' + viewlayer_name, type='CompositorNodeTree')
        group_node.node_tree = group_nt
        
        # Make active Node
        group_node.select = True
        nt.nodes.active = group_node 

        # create group input node and output node
        group_input_node = group_nt.nodes.new(type='NodeGroupInput')
        group_output_node = group_nt.nodes.new(type='NodeGroupOutput')
        group_input_node.location = (0, 0)
        group_output_node.location = (500, 0)

        new_nodes = list()
        color_nodes = list()

        # when there is muiltiple lightgroups, we need to add lightgroup nodes with mix rgb node(ADD)
        j = 0
        for i in range(len(lg_list)):
            j = i
            if bpy.app.version[0] >= 5:
                add_node = self.create_lightgroup_pass_nodes(group_nt, location=(
                    viewlayer_node.location[0] -group_input_node.location[0]+(i + 2) * 175, viewlayer_node.location[1] - (i + 1) * 100), dataType='RGBA', blendType='ADD')
                # print(f"J {j}")
                add_color_node = self.create_lightgroup_pass_nodes(group_nt, location=(
                    viewlayer_node.location[0] + (i + 2) * 175, viewlayer_node.location[1] + (add_node.location[1]) + 150), dataType='RGBA', blendType='COLOR')
            else:
                add_node = self.create_lightgroup_pass_nodes(group_nt, location=(
                    viewlayer_node.location[0] -group_input_node.location[0]+(i + 2) * 175, viewlayer_node.location[1] - (i + 1) * 100),dataType=None, blendType='ADD')
                # print(f"J {j}")
                add_color_node = self.create_lightgroup_pass_nodes(group_nt, location=(
                    viewlayer_node.location[0] + (i + 2) * 175, viewlayer_node.location[1] + (add_node.location[1]) + 150), dataType=None, blendType='COLOR')
            new_nodes.append(add_node)
            color_nodes.append(add_color_node)

        # add add node to combine lightgroup passes
        last_add_node = None
        
        # Enter groupnode
        bpy.ops.node.group_edit(exit=False)
        
        # Set groupinput as active
        group_input_node.select = True
        nt.nodes.active = group_input_node 
        
        i = 0
        j = 0
        for j, add_node in enumerate(new_nodes):
            if last_add_node is None:
                panel = group_nt.interface.new_panel(name=lg_list[j].replace('Combined_', ''))
                # Set groupinput as active
                group_input_node.select = True
                nt.nodes.active = group_input_node

                # add mix input
                if bpy.app.version[0] >= 5:
                    add_node.inputs[6].default_value = (0, 0, 0, 1)  # set black color for the first node
                else:
                    add_node.inputs[1].default_value = (0, 0, 0, 1)  # set black color for the first node

                factor = group_nt.interface.new_socket(name="Factor", in_out="INPUT", socket_type="NodeSocketFloat")
                factor.subtype = 'FACTOR'
                factor.min_value = 0
                # if bpy.app.version[0] >= 5:
                #     factor.max_value = 100
                #     factor.default_value = 100
                # else:
                factor.max_value = 1
                factor.default_value = 1
                if bpy.app.version[0] >= 5:
                    group_nt.links.new(group_input_node.outputs[i], add_node.inputs[0])
                else:
                    group_nt.links.new(group_input_node.outputs[i], add_node.inputs[0])
                

                # NOT EXPOASED IN API
                # move_item_to_parent(bpy.context, panel, factor)
                # print("first i: %s" % i)

                # Image Color
                lg_list[j] = group_nt.interface.new_socket(name=lg_list[j].replace('Combined_',''), in_out="INPUT", socket_type="NodeSocketColor")
                color = group_nt.interface.new_socket(name="Color", in_out="INPUT", socket_type="NodeSocketColor")
                # Group color node to color node
                if bpy.app.version[0] >= 5:
                    group_nt.links.new(group_input_node.outputs[i+1], color_nodes[i].inputs[6])
                else:
                    group_nt.links.new(group_input_node.outputs[i+1], color_nodes[i].inputs[1])
                # Connect color node to add node
                if bpy.app.version[0] >= 5:
                    group_nt.links.new(color_nodes[i].outputs[2], add_node.inputs[7])
                else:
                    group_nt.links.new(color_nodes[i].outputs[0], add_node.inputs[2])
                # i = i+1
                # group_nt.links.new(group_input_node.outputs[i], color_nodes[i].inputs[2])

                # link Light to color
                if bpy.app.version[0] >= 5:
                    group_nt.links.new(group_input_node.outputs[i+2], color_nodes[i].inputs[7])
                else:
                    group_nt.links.new(group_input_node.outputs[i+2], color_nodes[i].inputs[2])


                # Move socket to the panel
                # WIP > needs updated fix for linking
                # group_nt.interface.move_to_parent(item=factor,parent=panel,to_position=i)
                # group_nt.interface.move_to_parent(item=lg_list[j],parent=panel,to_position=i+1)
                # group_nt.interface.move_to_parent(item=color,parent=panel,to_position=i+2)
                
                # group_nt.links.new(group_input_node.outputs[i+1], color_nodes[i].inputs[1])

                # NOT EXPOASED IN API
                # move_item_to_parent(bpy.context, panel, color)
                # print("first i: %s" % i)
                # i = 2
            else:
                panel = group_nt.interface.new_panel(name=lg_list[j].replace('Combined_', ''))
                # j = i
                # i = i+j+1
                i = i+1
                # print("follow up i: %s" % i)
                factor = group_nt.interface.new_socket(name="Factor", in_out="INPUT", socket_type="NodeSocketFloat")
                factor.subtype = 'FACTOR'
                factor.min_value = 0
                factor.max_value = 1
                factor.default_value = 1
                group_nt.links.new(group_input_node.outputs[i*3], add_node.inputs[0])
                if bpy.app.version[0] >= 5:
                    group_nt.links.new(last_add_node.outputs[2], add_node.inputs[6])
                else:
                    group_nt.links.new(last_add_node.outputs[0], add_node.inputs[1])
                # i = i+j+1
                
                # print(color_nodes[i].name)
                # Image Color
                lg_list[j] = group_nt.interface.new_socket(name=lg_list[j].replace('Combined_', ''), in_out="INPUT", socket_type="NodeSocketColor")
                color = group_nt.interface.new_socket(name="Color", in_out="INPUT", socket_type="NodeSocketColor")
                if bpy.app.version[0] >= 5:
                    group_nt.links.new(group_input_node.outputs[i*3+1], color_nodes[i].inputs[6])
                    group_nt.links.new(color_nodes[i].outputs[2], add_node.inputs[7])
                else:
                    group_nt.links.new(group_input_node.outputs[i*3+1], color_nodes[i].inputs[1])
                    group_nt.links.new(color_nodes[i].outputs[0], add_node.inputs[2])
                
                # link Light to color
                if bpy.app.version[0] >= 5:
                    group_nt.links.new(group_input_node.outputs[i*3+2], color_nodes[i].inputs[7])
                else:
                    group_nt.links.new(group_input_node.outputs[i*3+2], color_nodes[i].inputs[2])

                # Move socket to the panel
                # WIP > needs updated fix for linking
                # group_nt.interface.move_to_parent(item=factor,parent=panel,to_position=i*3)
                # group_nt.interface.move_to_parent(item=lg_list[j],parent=panel,to_position=i*3+1)
                # group_nt.interface.move_to_parent(item=color,parent=panel,to_position=i*3+2)
                
                # print("follow up i: %s" % i)

                # group_nt.links.new(group_input_node.outputs[i], color_nodes[i].inputs[2])
                
                # link Light to color
                # i = i+1
                # group_nt.links.new(group_input_node.outputs[i], color_nodes[i].inputs[1])
                # group_nt.links.new(group_input_node.outputs[i], add_node.inputs[2])
                # i = i+j+1
                # i = i+1
                # print("follow up i: %s" % i)

            last_add_node = add_node

        group_input_node.location = viewlayer_node.location
        group_output_node.location = (last_add_node.location[0]+200, last_add_node.location[1])
        #####################################################
        # basic setup works
        # for j, add_node in enumerate(new_nodes):
        #     if last_add_node is None:
        #         panel = group_nt.interface.new_panel(name=lg_list[j])
        #         # Set groupinput as active
        #         group_input_node.select = True
        #         nt.nodes.active = group_input_node 
                
        #         # add mix input
        #         add_node.inputs[1].default_value = (0, 0, 0, 1)  # set black color for the first node
                
        #         factor = group_nt.interface.new_socket(name="Factor", in_out="INPUT", socket_type="NodeSocketFloat")
        #         factor.subtype = 'FACTOR'
        #         factor.min_value = 0
        #         factor.max_value = 1
        #         factor.default_value = 1
        #         group_nt.links.new(group_input_node.outputs[i], add_node.inputs[0])
                
        #         # NOT EXPOASED IN API
        #         # move_item_to_parent(bpy.context, panel, factor)

        #         # Image Color
        #         group_nt.interface.new_socket(name="Color", in_out="INPUT", socket_type="NodeSocketColor")
        #         i = i+1
        #         group_nt.links.new(group_input_node.outputs[i], add_node.inputs[2])
        #     else:
        #         # panel = group_nt.interface.new_panel(name=lg_list[j])
        #         i = i+1
        #         factor = group_nt.interface.new_socket(name="Factor", in_out="INPUT", socket_type="NodeSocketFloat")
        #         factor.subtype = 'FACTOR'
        #         factor.min_value = 0
        #         factor.max_value = 1
        #         factor.default_value = 1
        #         group_nt.links.new(group_input_node.outputs[i], add_node.inputs[0])
        #         group_nt.links.new(last_add_node.outputs[0], add_node.inputs[1])
                
        #         # Image Color
        #         group_nt.interface.new_socket(name="Color", in_out="INPUT", socket_type="NodeSocketColor")
        #         i = i+1
        #         group_nt.links.new(group_input_node.outputs[i], add_node.inputs[2])

        #     last_add_node = add_node
        #####################################################

        # link to output
        group_nt.interface.new_socket(name="Color", in_out="OUTPUT", socket_type="NodeSocketColor")
        if bpy.app.version[0] >= 5:
            group_nt.links.new(last_add_node.outputs[2], group_output_node.inputs[0])
        else:
            group_nt.links.new(last_add_node.outputs[0], group_output_node.inputs[0])

        # link viewlayer node to group node
        for i, lg_pass in enumerate(lg_passes):
            print(f"{i}-{lg_pass }")
            nt.links.new(viewlayer_node.outputs[lg_pass], group_node.inputs[i * 3 + 1])
            
            # Reset default to 1 > seems broken if we preset it
            group_node.inputs[i * 3].default_value = 1

            # For testing add colors > Purple, BLack, Terquoise, Orange, Yellow, Fuchia
            #colors_lights = [[0.151923, 0.043528, 0.627410, 1.000000],[0.000000, 0.000000, 0.000000, 1.000000],[0.017181, 0.774650, 0.609955, 1.000000],[0.713283, 0.173523, 0.015980, 1.000000],[1.000000, 0.940560, 0.000000, 1.000000],[0.712989, 0.016579, 0.572969, 1.000000]]

            # Set test colors
            #group_node.inputs[(i*3)+2].default_value = colors_lights[i]

            # Move light name to top > easier understanding panel
            # # see here; https://blenderartists.org/t/how-to-move-a-socket-into-a-panel-in-the-nodetree-in-blender-4-0-python/1509176
            # print("move to index %s - type %s" % ((group_nt.interface.items_tree[i*3+1].index-1), (group_nt.interface.items_tree[i*3+1].index)))
            # if (i==0):
            #     print("First %s" % (group_nt.interface.items_tree[i*3+1].index-1))
            #     group_nt.interface.move(group_nt.interface.items_tree[1] , 0)
            # elif (i == (len(lg_passes)-1)):
            #     print("skip last")
            #     # group_nt.interface.move(group_nt.interface.items_tree[i*3+1] , group_nt.interface.items_tree[i*3+1].index-2)
            # else:
            #     print("move to index %s" % (group_nt.interface.items_tree[i*3+1].index-1))
            #     print("name %s" % (group_nt.interface.items_tree[i*3+1].name))
            #     group_nt.interface.move(group_nt.interface.items_tree[i*3+1] , group_nt.interface.items_tree[i*3+1].index-1)

            # bpy.context.scene.node_tree.nodes.active.node_tree.interface.move(bpy.context.scene.node_tree.nodes.active.node_tree.interface.items_tree[4],0)

        
        # Exit groupnode
        bpy.ops.node.group_edit(exit=True)

        return {'FINISHED'}
        
    def create_lightgroup_pass_nodes(self, nt, location=(0, 0), dataType=None, blendType=None):
        if bpy.app.version[0] >= 5:
            # add_node = nt.nodes.new(type='ShaderNodeColorMixRGB')
            add_node = nt.nodes.new(type='ShaderNodeMix')
            add_node.data_type = dataType
            add_node.blend_type = blendType
            # if blendType =='ADD':
            add_node.inputs['Factor'].default_value = 1
            add_node.clamp_factor = False
                
        else: 
            add_node = nt.nodes.new(type='CompositorNodeMixRGB')
            add_node.use_alpha = True
            add_node.blend_type = blendType
        add_node.location = location
        return add_node

    # WIP need to check how to read node.layer its a str not an enum
    # def check(self, context):
    #     return True

    # def invoke(self, context, event):
    #     return context.window_manager.invoke_props_dialog(self, width=300)

    # def draw(self, context):
    #     layout = self.layout
    #     scn = context.scene
    #     layout.label(text="Choose render layer to set Relight NodeGroup", icon='INFO')

    #     row = layout.row()
    #     row.prop(self, "render_layers")



def menu_fun(self, context):
    nt = context.space_data.node_tree
    if nt and nt.nodes.active:
        if nt.nodes.active.bl_idname == 'CompositorNodeRLayers' or nt.nodes.active.bl_idname == 'CompositorNodeImage' and nt.nodes.active.layer !='':
            self.layout.separator()
            op = self.layout
            op.operator_context = "INVOKE_DEFAULT"
            op.operator(NODE_OT_set_lightgroup_postprocess_nodes.bl_idname, text="Combine Lightgroup Passes")

def register():
    bpy.utils.register_class(NODE_OT_set_lightgroup_postprocess_nodes)
    # add to context menu
    bpy.types.NODE_MT_context_menu.append(menu_fun)
    bpy.types.NODE_MT_editor_menus.append(menu_fun)


def unregister():
    bpy.utils.unregister_class(NODE_OT_set_lightgroup_postprocess_nodes)

    bpy.types.NODE_MT_context_menu.remove(menu_fun)