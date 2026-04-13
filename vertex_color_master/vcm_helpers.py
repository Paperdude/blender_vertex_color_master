#  ***** GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#  ***** GPL LICENSE BLOCK *****

# <pep8 compliant>

import bpy
import bmesh
import random
from math import fmod
from mathutils import Color, Vector
from .vcm_globals import *

def _is_corner_color_attribute(layer):
    return layer is not None and getattr(layer, 'domain', None) == 'CORNER' and \
        getattr(layer, 'data_type', None) in {'BYTE_COLOR', 'FLOAT_COLOR'}


def get_color_layers(mesh):
    if hasattr(mesh, 'color_attributes'):
        return [layer for layer in mesh.color_attributes if _is_corner_color_attribute(layer)]
    if hasattr(mesh, 'vertex_colors'):
        return list(mesh.vertex_colors)
    return []


def has_any_color_layers(mesh):
    return len(get_color_layers(mesh)) > 0


def get_active_color_layer(mesh):
    if hasattr(mesh, 'color_attributes'):
        active = getattr(mesh.color_attributes, 'active_color', None)
        if _is_corner_color_attribute(active):
            return active

        active = getattr(mesh.color_attributes, 'active', None)
        if _is_corner_color_attribute(active):
            return active

        layers = get_color_layers(mesh)
        return layers[0] if len(layers) > 0 else None

    if hasattr(mesh, 'vertex_colors'):
        return mesh.vertex_colors.active

    return None


def get_color_layer_by_name(mesh, layer_name):
    for layer in get_color_layers(mesh):
        if layer.name == layer_name:
            return layer
    return None


def ensure_active_color_layer(mesh, layer_name="Col"):
    layer = get_active_color_layer(mesh)
    if layer is not None:
        return layer
    return create_color_layer(mesh, layer_name)


def create_color_layer(mesh, layer_name):
    if hasattr(mesh, 'color_attributes'):
        layer = mesh.color_attributes.new(name=layer_name, type='BYTE_COLOR', domain='CORNER')
        set_active_color_layer(mesh, layer)
        return layer
    if hasattr(mesh, 'vertex_colors'):
        return mesh.vertex_colors.new(name=layer_name)
    return None


def set_active_color_layer(mesh, layer):
    if layer is None:
        return
    if hasattr(mesh, 'color_attributes'):
        if hasattr(mesh.color_attributes, 'active_color'):
            mesh.color_attributes.active_color = layer
        if hasattr(mesh.color_attributes, 'active'):
            mesh.color_attributes.active = layer
        return
    if hasattr(mesh, 'vertex_colors'):
        mesh.vertex_colors.active = layer


def remove_color_layer(mesh, layer):
    if layer is None:
        return
    if hasattr(mesh, 'color_attributes'):
        mesh.color_attributes.remove(layer)
        return
    if hasattr(mesh, 'vertex_colors'):
        mesh.vertex_colors.remove(layer)


def get_bmesh_active_color_layer(bm, layer_name=None):
    if layer_name:
        if layer_name in bm.loops.layers.color:
            return bm.loops.layers.color[layer_name]
        if layer_name in bm.loops.layers.float_color:
            return bm.loops.layers.float_color[layer_name]

    color_layer = bm.loops.layers.color.active
    if color_layer is not None:
        return color_layer

    float_color_layer = bm.loops.layers.float_color.active
    if float_color_layer is not None:
        return float_color_layer

    if len(bm.loops.layers.color) > 0:
        return bm.loops.layers.color[0]
    if len(bm.loops.layers.float_color) > 0:
        return bm.loops.layers.float_color[0]

    return None


def get_active_vertex_paint_brush(context):
    tool_settings = getattr(context, 'tool_settings', None)
    vertex_paint = getattr(tool_settings, 'vertex_paint', None)
    return getattr(vertex_paint, 'brush', None)


def get_workspace_vertex_tool_brush(context):
    workspace = getattr(context, 'workspace', None)
    tools = getattr(workspace, 'tools', None)
    if tools is None:
        return None

    tool = None
    try:
        tool = tools.from_space_view3d_mode(mode='PAINT_VERTEX', create=False)
    except Exception:
        return None

    if tool is None:
        return None

    # Common case: builtin_brush.<BrushName>
    idname = getattr(tool, 'idname', '')
    if isinstance(idname, str) and idname.startswith('builtin_brush.'):
        brush_name = idname.split('.', 1)[1]
        brush = bpy.data.brushes.get(brush_name)
        if brush is not None:
            return brush

    # Fallback: inspect tool operator props for a brush name.
    for op_id in ('paint.brush_select', 'paint.vertex_paint'):
        try:
            props = tool.operator_properties(op_id)
        except Exception:
            continue
        for attr_name in ('brush', 'tool'):
            value = getattr(props, attr_name, None)
            if isinstance(value, str):
                brush = bpy.data.brushes.get(value)
                if brush is not None:
                    return brush

    return None


def get_paint_brush_candidates(context):
    tool_settings = getattr(context, 'tool_settings', None)
    if tool_settings is None:
        return []

    brushes = []

    workspace_brush = get_workspace_vertex_tool_brush(context)
    if workspace_brush is not None:
        brushes.append(workspace_brush)

    # Vertex paint is the primary target for this addon.
    vertex_paint = getattr(tool_settings, 'vertex_paint', None)
    vertex_brush = getattr(vertex_paint, 'brush', None)
    if vertex_brush is not None:
        brushes.append(vertex_brush)

    # Blender 5 tools can internally reuse paint brush datablocks from other paint slots.
    for slot_name in ('image_paint', 'sculpt', 'weight_paint'):
        slot = getattr(tool_settings, slot_name, None)
        brush = getattr(slot, 'brush', None)
        if brush is not None and brush not in brushes:
            brushes.append(brush)

    return brushes


def get_unified_paint_settings(context):
    tool_settings = getattr(context, 'tool_settings', None)
    vertex_paint = getattr(tool_settings, 'vertex_paint', None)
    unified = getattr(vertex_paint, 'unified_paint_settings', None)
    if unified is not None:
        return unified

    # Fallback for older Blender APIs.
    return getattr(tool_settings, 'unified_paint_settings', None)


def get_effective_paint_colors(context):
    brushes = get_paint_brush_candidates(context)
    unified = get_unified_paint_settings(context)

    if unified is not None and getattr(unified, 'use_unified_color', False):
        if hasattr(unified, 'color') and hasattr(unified, 'secondary_color'):
            return Color(unified.color), Color(unified.secondary_color)

    # In practice (Blender 5 vertex paint), brush colors are the most reliable source.
    for brush in brushes:
        if hasattr(brush, 'color') and hasattr(brush, 'secondary_color'):
            return Color(brush.color), Color(brush.secondary_color)

    if unified is not None and hasattr(unified, 'color') and hasattr(unified, 'secondary_color'):
        return Color(unified.color), Color(unified.secondary_color)

    return Color((1.0, 1.0, 1.0)), Color((0.0, 0.0, 0.0))


def set_paint_colors(context, primary=None, secondary=None):
    if context is None:
        return

    brushes = get_paint_brush_candidates(context)
    unified = get_unified_paint_settings(context)

    primary_value = tuple(primary[:3]) if primary is not None else None
    secondary_value = tuple(secondary[:3]) if secondary is not None else None

    for brush in brushes:
        if hasattr(brush, 'color_type'):
            try:
                brush.color_type = 'COLOR'
            except Exception:
                pass

    if primary_value is not None:
        for brush in brushes:
            if hasattr(brush, 'color'):
                brush.color = primary_value
        if unified is not None:
            if hasattr(unified, 'color'):
                unified.color = primary_value

    if secondary_value is not None:
        for brush in brushes:
            if hasattr(brush, 'secondary_color'):
                brush.secondary_color = secondary_value
        if unified is not None:
            if hasattr(unified, 'secondary_color'):
                unified.secondary_color = secondary_value


def sync_paint_color_sources(context):
    if context is None:
        return

    brushes = get_paint_brush_candidates(context)
    unified = get_unified_paint_settings(context)
    if len(brushes) == 0 or unified is None:
        return

    # Mirror first valid paint brush colors into unified storage only (non-invasive).
    source_brush = None
    for brush in brushes:
        if hasattr(brush, 'color') and hasattr(brush, 'secondary_color'):
            source_brush = brush
            break

    if source_brush is None:
        return

    primary = source_brush.color
    secondary = source_brush.secondary_color
    if hasattr(unified, 'color'):
        unified.color = primary
    if hasattr(unified, 'secondary_color'):
        unified.secondary_color = secondary


def posterize(value, steps):
    return round(value * steps) / steps


def remap(value, min0, max0, min1, max1):
    r0 = max0 - min0
    if r0 == 0:
        return min1
    r1 = max1 - min1
    return ((value - min0) * r1) / r0 + min1


def channel_id_to_idx(id):
    if id == red_id:
        return 0
    if id == green_id:
        return 1
    if id == blue_id:
        return 2
    if id == alpha_id:
        return 3
    # default to red
    return 0


def get_active_channel_mask(active_channels):
    rgba_mask = [True if cid in active_channels else False for cid in valid_channel_ids]
    return rgba_mask


def get_isolated_channel_ids(vcol):
    if vcol is None:
        return None

    vcol_id = vcol.name
    prefix = isolate_mode_name_prefix
    prefix_len = len(prefix)

    if vcol_id.startswith(prefix) and len(vcol_id) > prefix_len + 3:
        iso_vcol_id = vcol_id[prefix_len + 3:] # get vcol id from end of string
        iso_channel_id = vcol_id[prefix_len + 1] # get channel id
        if iso_channel_id in valid_channel_ids:
            return [iso_vcol_id, iso_channel_id]

    return None


def rgb_to_luminosity(color):
    # Y = 0.299 R + 0.587 G + 0.114 B
    return color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114


def convert_rgb_to_luminosity(mesh, src_vcol, dst_vcol, dst_channel_idx, dst_all_channels=False):
    if dst_all_channels:
        for loop_index, loop in enumerate(mesh.loops):
            c = src_vcol.data[loop_index].color
            luminosity = rgb_to_luminosity(c)
            c[0] = luminosity # assigning this way will preserve alpha
            c[1] = luminosity
            c[2] = luminosity
            dst_vcol.data[loop_index].color = c
    else:
        for loop_index, loop in enumerate(mesh.loops):
            luminosity = rgb_to_luminosity(src_vcol.data[loop_index].color)
            dst_vcol.data[loop_index].color[dst_channel_idx] = luminosity


# alpha_mode
# 'OVERWRITE' - replace with copied channel value
# 'PRESERVE' - keep existing alpha value
# 'FILL' - fill alpha with 1.0
def copy_channel(mesh, src_vcol, dst_vcol, src_channel_idx, dst_channel_idx, swap=False,
                 dst_all_channels=False, alpha_mode='PRESERVE'):
    if dst_all_channels:
        color_size = len(src_vcol.data[0].color) if len(src_vcol.data) > 0 else 3
        if alpha_mode == 'OVERWRITE' or color_size < 4:
            for loop_index, loop in enumerate(mesh.loops):
                src_val = src_vcol.data[loop_index].color[src_channel_idx]
                dst_vcol.data[loop_index].color = [src_val] * color_size
        elif alpha_mode == 'FILL':
            for loop_index, loop in enumerate(mesh.loops):
                src_val = src_vcol.data[loop_index].color[src_channel_idx]
                dst_vcol.data[loop_index].color = [src_val, src_val, src_val, 1.0]
        else: # default to preserve
            for loop_index, loop in enumerate(mesh.loops):
                c = src_vcol.data[loop_index].color
                src_val = c[src_channel_idx]
                c[0] = src_val
                c[1] = src_val
                c[2] = src_val
                dst_vcol.data[loop_index].color = c
    else:
        if swap:
            for loop_index, loop in enumerate(mesh.loops):
                src_val = src_vcol.data[loop_index].color[src_channel_idx]
                dst_val = dst_vcol.data[loop_index].color[dst_channel_idx]
                dst_vcol.data[loop_index].color[dst_channel_idx] = src_val
                src_vcol.data[loop_index].color[src_channel_idx] = dst_val
        else:
            for loop_index, loop in enumerate(mesh.loops):
                dst_vcol.data[loop_index].color[dst_channel_idx] = src_vcol.data[loop_index].color[src_channel_idx]

    mesh.update()


def blend_channels(mesh, src_vcol, dst_vcol, src_channel_idx, dst_channel_idx, result_channel_idx, operation='ADD'):
    if operation == 'ADD':
        for loop_index, loop in enumerate(mesh.loops):
            val = src_vcol.data[loop_index].color[src_channel_idx] + dst_vcol.data[loop_index].color[dst_channel_idx]
            dst_vcol.data[loop_index].color[result_channel_idx] = max(0.0, min(val, 1.0))  # clamp
    elif operation == 'SUB':
        for loop_index, loop in enumerate(mesh.loops):
            val = src_vcol.data[loop_index].color[src_channel_idx] - dst_vcol.data[loop_index].color[dst_channel_idx]
            dst_vcol.data[loop_index].color[result_channel_idx] = max(0.0, min(val, 1.0))  # clamp
    elif operation == 'MUL':
        for loop_index, loop in enumerate(mesh.loops):
            val = src_vcol.data[loop_index].color[src_channel_idx] * dst_vcol.data[loop_index].color[dst_channel_idx]
            dst_vcol.data[loop_index].color[result_channel_idx] = val
    elif operation == 'DIV':
        for loop_index, loop in enumerate(mesh.loops):
            src = src_vcol.data[loop_index].color[src_channel_idx]
            dst = dst_vcol.data[loop_index].color[dst_channel_idx]
            val = 0.0 if src == 0.0 else 1.0 if dst == 0.0 else src / dst
            dst_vcol.data[loop_index].color[result_channel_idx] = val
    elif operation == 'LIGHTEN':
        for loop_index, loop in enumerate(mesh.loops):
            src = src_vcol.data[loop_index].color[src_channel_idx]
            dst = dst_vcol.data[loop_index].color[dst_channel_idx]
            dst_vcol.data[loop_index].color[result_channel_idx] = src if src > dst else dst
    elif operation == 'DARKEN':
        for loop_index, loop in enumerate(mesh.loops):
            src = src_vcol.data[loop_index].color[src_channel_idx]
            dst = dst_vcol.data[loop_index].color[dst_channel_idx]
            dst_vcol.data[loop_index].color[result_channel_idx] = src if src < dst else dst
    elif operation == 'MIX':
        for loop_index, loop in enumerate(mesh.loops):
            dst_vcol.data[loop_index].color[result_channel_idx] = src_vcol.data[loop_index].color[src_channel_idx]
    else:
        return

    mesh.update()


def uvs_to_color(mesh, src_uv, dst_vcol, dst_u_idx=0, dst_v_idx=1):
    # by default copy u->r and v->g
    # uv range is -inf, inf so use fmod to remap to 0-1
    for loop_index, loop in enumerate(mesh.loops):
        c = dst_vcol.data[loop_index].color
        uv = src_uv.data[loop_index].uv
        u = fmod(uv[0], 1.0)
        v = fmod(uv[1], 1.0)
        c[dst_u_idx] = u + 1.0 if u < 0 else u
        c[dst_v_idx] = v + 1.0 if v < 0 else v
        dst_vcol.data[loop_index].color = c

    mesh.update()


def color_to_uvs(mesh, src_vcol, dst_uv, src_u_idx=0, src_v_idx=1):
    # by default copy r->u and g->v
    for loop_index, loop in enumerate(mesh.loops):
        c = src_vcol.data[loop_index].color
        uv = [c[src_u_idx], c[src_v_idx]]
        dst_uv.data[loop_index].uv = uv

    mesh.update()


def get_custom_normals(obj):
    # Not entirely sure why this works and [loop.normal for loop in obj.data.loops] doesn't work...
    # note that these normals are in world space... seems to be a huge pain to get tangent space normals
    normals = [loop.normal for loop in [obj.data.calc_normals_split(), obj][1].data.loops]

    return normals


def normals_to_color(mesh, normals, dst_vcol):
    # copy normal xyz to color rgb
    for loop_index, loop in enumerate(mesh.loops):
        c = dst_vcol.data[loop_index].color
        n = normals[loop_index]
        # remap to values that can be displayed
        c[0] = remap(n[0], -1.0, 1.0, 0.0, 1.0)
        c[1] = remap(n[1], -1.0, 1.0, 0.0, 1.0)
        c[2] = remap(n[2], -1.0, 1.0, 0.0, 1.0)
        dst_vcol.data[loop_index].color = c

    mesh.update()


def color_to_normals(mesh, src_vcol):
    # ensure the mesh has empty split normals
    if not mesh.has_custom_normals:
        if hasattr(mesh, 'create_normals_split'):
            mesh.create_normals_split()
        if hasattr(mesh, 'use_auto_smooth'):
            mesh.use_auto_smooth = True

    # create a structure that matches the required input of the normals_split_custom_set function
    clnors = [Vector()] * len(mesh.loops)

    for loop_index, loop in enumerate(mesh.loops):
        c = src_vcol.data[loop_index].color
        # remap color to normal range
        n = Vector([remap(channel, 0.0, 1.0, -1.0, 1.0) for channel in c[0:3]])
        n.normalize()
        clnors[loop_index] = n   

    mesh.normals_split_custom_set(clnors)
    mesh.update()  


def weights_to_color(mesh, src_vgroup_idx, dst_vcol, dst_channel_idx, all_channels=False):
    vertex_weights = [0.0] * len(mesh.vertices)

    # build list of weights for vertex indices
    for i, vert in enumerate(mesh.vertices):
        for group in vert.groups:
            if group.group == src_vgroup_idx:
                vertex_weights[i] = group.weight
                break

    # copy weights to channel of dst color layer
    if not all_channels:
        for loop_index, loop in enumerate(mesh.loops):
            weight = vertex_weights[loop.vertex_index]
            dst_vcol.data[loop_index].color[dst_channel_idx] = weight
    else:
        for loop_index, loop in enumerate(mesh.loops):
            weight = vertex_weights[loop.vertex_index]
            dst_vcol.data[loop_index].color[:3] = [weight]*3

    mesh.update()


def color_to_weights(obj, src_vcol, src_channel_idx, dst_vgroup_idx):
    mesh = obj.data

    # build 2d array containing sum of color channel value, number of values
    # used to calculate average for vertex when setting weights
    vertex_values = [[0.0, 0] for i in range(0, len(mesh.vertices))]

    for loop_index, loop in enumerate(mesh.loops):
        vi = loop.vertex_index
        vertex_values[vi][0] += src_vcol.data[loop_index].color[src_channel_idx]
        vertex_values[vi][1] += 1

    # replace weights of the destination group
    group = obj.vertex_groups[dst_vgroup_idx]
    mode = 'REPLACE'

    for i in range(0, len(mesh.vertices)):
        cnt = vertex_values[i][1]
        weight = 0.0 if cnt == 0.0 else vertex_values[i][0] / cnt
        group.add([i], weight, mode)

    mesh.update()


# no channel checking. Designed to more efficiently apply a color to mesh
def quick_fill_selected(mesh, vcol, color):
    vcol_data = vcol.data
    if mesh.use_paint_mask:
        selected_faces = [face for face in mesh.polygons if face.select]
        for face in selected_faces:
            for loop_index in face.loop_indices:
                c = vcol_data[loop_index].color
                c[0] = color[0]
                c[1] = color[1]
                c[2] = color[2]
                vcol_data[loop_index].color = c
    elif mesh.use_paint_mask_vertex:
        verts = mesh.vertices
        for loop_index, loop in enumerate(mesh.loops):
            if verts[loop.vertex_index].select:
                c = vcol_data[loop_index].color
                c[0] = color[0]
                c[1] = color[1]
                c[2] = color[2]
                vcol_data[loop_index].color = c
    else: # mask == 'NONE'
        for loop_index, loop in enumerate(mesh.loops):
            c = vcol_data[loop_index].color
            c[0] = color[0]
            c[1] = color[1]
            c[2] = color[2]
            vcol_data[loop_index].color = c


def fill_selected(mesh, vcol, color, active_channels):
    if mesh.use_paint_mask:
        selected_faces = [face for face in mesh.polygons if face.select]
        for face in selected_faces:
            for loop_index in face.loop_indices:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = color[0]
                if green_id in active_channels:
                    c[1] = color[1]
                if blue_id in active_channels:
                    c[2] = color[2]
                if alpha_id in active_channels:
                    c[3] = color[3]
                vcol.data[loop_index].color = c
    else:
        vertex_mask = True if mesh.use_paint_mask_vertex else False
        verts = mesh.vertices

        for loop_index, loop in enumerate(mesh.loops):
            if not vertex_mask or verts[loop.vertex_index].select:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = color[0]
                if green_id in active_channels:
                    c[1] = color[1]
                if blue_id in active_channels:
                    c[2] = color[2]
                if alpha_id in active_channels:
                    c[3] = color[3]
                vcol.data[loop_index].color = c

    mesh.update()


def invert_selected(mesh, vcol, active_channels):
    if mesh.use_paint_mask:
        selected_faces = [face for face in mesh.polygons if face.select]
        for face in selected_faces:
            for loop_index in face.loop_indices:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = 1 - c[0]
                if green_id in active_channels:
                    c[1] = 1 - c[1]
                if blue_id in active_channels:
                    c[2] = 1 - c[2]
                if alpha_id in active_channels:
                    c[3] = 1 - c[3]
                vcol.data[loop_index].color = c
    else:
        vertex_mask = True if mesh.use_paint_mask_vertex else False
        verts = mesh.vertices

        for loop_index, loop in enumerate(mesh.loops):
            if not vertex_mask or verts[loop.vertex_index].select:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = 1 - c[0]
                if green_id in active_channels:
                    c[1] = 1 - c[1]
                if blue_id in active_channels:
                    c[2] = 1 - c[2]
                if alpha_id in active_channels:
                    c[3] = 1 - c[3]
                vcol.data[loop_index].color = c

    mesh.update()


def posterize_selected(mesh, vcol, steps, active_channels):
    if mesh.use_paint_mask:
        selected_faces = [face for face in mesh.polygons if face.select]
        for face in selected_faces:
            for loop_index in face.loop_indices:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = posterize(c[0], steps)
                if green_id in active_channels:
                    c[1] = posterize(c[1], steps)
                if blue_id in active_channels:
                    c[2] = posterize(c[2], steps)
                if alpha_id in active_channels:
                    c[3] = posterize(c[3], steps)
                vcol.data[loop_index].color = c
    else:
        vertex_mask = True if mesh.use_paint_mask_vertex else False
        verts = mesh.vertices

        for loop_index, loop in enumerate(mesh.loops):
            if not vertex_mask or verts[loop.vertex_index].select:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = posterize(c[0], steps)
                if green_id in active_channels:
                    c[1] = posterize(c[1], steps)
                if blue_id in active_channels:
                    c[2] = posterize(c[2], steps)
                if alpha_id in active_channels:
                    c[3] = posterize(c[3], steps)
                vcol.data[loop_index].color = c

    mesh.update()


def remap_selected(mesh, vcol, min0, max0, min1, max1, active_channels):
    if mesh.use_paint_mask:
        selected_faces = [face for face in mesh.polygons if face.select]
        for face in selected_faces:
            for loop_index in face.loop_indices:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = remap(c[0], min0, max0, min1, max1)
                if green_id in active_channels:
                    c[1] = remap(c[1], min0, max0, min1, max1)
                if blue_id in active_channels:
                    c[2] = remap(c[2], min0, max0, min1, max1)
                if alpha_id in active_channels:
                    c[3] = remap(c[3], min0, max0, min1, max1)
                vcol.data[loop_index].color = c
    else:
        vertex_mask = True if mesh.use_paint_mask_vertex else False
        verts = mesh.vertices

        for loop_index, loop in enumerate(mesh.loops):
            if not vertex_mask or verts[loop.vertex_index].select:
                c = vcol.data[loop_index].color
                if red_id in active_channels:
                    c[0] = remap(c[0], min0, max0, min1, max1)
                if green_id in active_channels:
                    c[1] = remap(c[1], min0, max0, min1, max1)
                if blue_id in active_channels:
                    c[2] = remap(c[2], min0, max0, min1, max1)
                if alpha_id in active_channels:
                    c[3] = remap(c[3], min0, max0, min1, max1)
                vcol.data[loop_index].color = c

    mesh.update()


def normalize_blend_mask(mesh, vcol):
    if mesh.use_paint_mask:
        loop_indices = [loop_index for face in mesh.polygons if face.select for loop_index in face.loop_indices]
    else:
        vertex_mask = True if mesh.use_paint_mask_vertex else False
        verts = mesh.vertices
        loop_indices = [
            loop_index for loop_index, loop in enumerate(mesh.loops)
            if not vertex_mask or verts[loop.vertex_index].select
        ]

    for loop_index in loop_indices:
        c = list(vcol.data[loop_index].color)
        rgb = [max(0.0, min(1.0, c[i])) for i in range(3)]
        rgb_sum = rgb[0] + rgb[1] + rgb[2]

        if rgb_sum > 1.0:
            scale = 1.0 / rgb_sum
            rgb = [channel * scale for channel in rgb]
            rgb_sum = 1.0

        c[0] = rgb[0]
        c[1] = rgb[1]
        c[2] = rgb[2]
        c[3] = max(0.0, min(1.0, 1.0 - rgb_sum))
        vcol.data[loop_index].color = c

    mesh.update()


def adjust_hsv(mesh, vcol, h_offset, s_offset, v_offset, colorize):
    if mesh.use_paint_mask:
        selected_faces = [face for face in mesh.polygons if face.select]
        for face in selected_faces:
            for loop_index in face.loop_indices:
                c = Color(vcol.data[loop_index].color[:3])
                if colorize:
                    c.h = fmod(0.5 + h_offset, 1.0)
                else:
                    c.h = fmod(1.0 + c.h + h_offset, 1.0)
                c.s = max(0.0, min(c.s + s_offset, 1.0))
                c.v = max(0.0, min(c.v + v_offset, 1.0))

                new_color = vcol.data[loop_index].color
                new_color[:3] = c
                vcol.data[loop_index].color = new_color
    else:
        vertex_mask = True if mesh.use_paint_mask_vertex else False
        verts = mesh.vertices

        for loop_index, loop in enumerate(mesh.loops):
            if not vertex_mask or verts[loop.vertex_index].select:
                c = Color(vcol.data[loop_index].color[:3])
                if colorize:
                    c.h = fmod(0.5 + h_offset, 1.0)
                else:
                    c.h = fmod(1.0 + c.h + h_offset, 1.0)
                c.s = max(0.0, min(c.s + s_offset, 1.0))
                c.v = max(0.0, min(c.v + v_offset, 1.0))

                new_color = vcol.data[loop_index].color
                new_color[:3] = c
                vcol.data[loop_index].color = new_color

    mesh.update()


# check isolate mode (shouldn't work in isolate mode...)
# set random seed in parent function
def set_island_colors_per_channel(mesh, rgba_mask, merge_similar, vmin, vmax):
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)

    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    active_vcol = get_active_color_layer(mesh)
    layer_name = active_vcol.name if active_vcol is not None else None
    color_layer = get_bmesh_active_color_layer(bm, layer_name)
    if color_layer is None:
        bm.free()
        bpy.ops.object.mode_set(mode='VERTEX_PAINT', toggle=False)
        return

    # Find all islands in the mesh
    mesh_islands = []
    selected_faces = ([f for f in bm.faces if f.select])
    faces = selected_faces if mesh.use_paint_mask or mesh.use_paint_mask_vertex else bm.faces
    bpy.ops.mesh.select_all(action="DESELECT")

    while len(faces) > 0:
        # Select linked faces to find island
        faces[0].select_set(True)
        bpy.ops.mesh.select_linked()
        mesh_islands.append([f for f in faces if f.select])
        # Hide the island and update faces
        bpy.ops.mesh.hide(unselected=False)
        faces = [f for f in faces if not f.hide]

    bpy.ops.mesh.reveal()  

    island_colors = {} # Island face count : Random color pairs

    for index, island in enumerate(mesh_islands):
        rgba_values = []

        face_count = len(island)
        if merge_similar and face_count in island_colors.keys():
            rgba_values = island_colors[face_count]
        else:
            vrange = abs(vmax - vmin)
            rgba_values = [(vmin + random.random() * vrange) for i in range(4)]
            island_colors[face_count] = rgba_values

        # Set island face colors (probably quite slow, due to list comprehension per face loop)
        for face in island:
            for loop in face.loops:
                c = loop[color_layer]
                c = [v if rgba_mask[i] else c[i] for i, v in enumerate(rgba_values)]
                loop[color_layer] = c

    # Restore selection
    for f in selected_faces:
        f.select = True

    bm.free()
    bpy.ops.object.mode_set(mode='VERTEX_PAINT', toggle=False)


def get_layer_info(context):
    settings = context.scene.vertex_color_master_settings

    d = ' ' # delimiter
    s = settings.src_vcol_id
    src_type = s[:s.find(d)]
    src_id = s[s.find(d) + 1:]

    s = settings.dst_vcol_id
    dst_type = s[:s.find(d)]
    dst_id = s[s.find(d) + 1:]

    return [src_type, src_id, dst_type, dst_id]


def get_validated_input(context, get_src, get_dst):
    settings = context.scene.vertex_color_master_settings
    obj = context.active_object
    mesh = obj.data

    rv = {}
    message = None

    layer_info = get_layer_info(context)
    src_type = layer_info[0]
    src_id = layer_info[1]
    dst_type = layer_info[2]
    dst_id = layer_info[3]

    # are these conditions actually possible?
    if message is None:
        if (src_type == type_vcol or dst_type == type_vcol) and not has_any_color_layers(mesh):
            message = "Object has no vertex colors."
        if (src_type == type_vgroup or dst_type == type_vgroup) and obj.vertex_groups is None:
            message = "Object has no vertex groups."
        if (src_type == type_uv or dst_type == type_uv) and mesh.uv_layers is None:
            message = "Object has no uv layers."

    # validate src
    if get_src and message is None:
        if src_type == type_vcol:
            src_vcol = get_color_layer_by_name(mesh, src_id)
            if src_vcol is not None:
                rv['src_vcol'] = src_vcol
                rv['src_channel_idx'] = channel_id_to_idx(settings.src_channel_id)
            else:
                message = "Src color layer is not valid."
        elif src_type == type_uv:
            if src_id in mesh.uv_layers:
                rv['src_uv'] = mesh.uv_layers[src_id]
            else:
                message = "Src UV layer is not valid."            
        else:
            src_vgroup_idx = -1
            for group in obj.vertex_groups:
                if group.name == src_id:
                    src_vgroup_idx = group.index
                    rv['src_vgroup_idx'] = src_vgroup_idx
                    break
            if src_vgroup_idx < 0:
                message = "Src vertex group is not valid."

    # validate dst
    if get_dst and message is None:
        if dst_type == type_vcol:
            dst_vcol = get_color_layer_by_name(mesh, dst_id)
            if dst_vcol is not None:
                rv['dst_vcol'] = dst_vcol
                rv['dst_channel_idx'] = channel_id_to_idx(settings.dst_channel_id)
            else:
                message = "Dst color layer is not valid."
        elif dst_type == type_uv:
            if dst_id in mesh.uv_layers:
                rv['dst_uv'] = mesh.uv_layers[dst_id]
            else:
                message = "Dst UV layer is not valid." 
        else:
            dst_vgroup_idx = -1
            for group in obj.vertex_groups:
                if group.name == dst_id:
                    dst_vgroup_idx = group.index
                    rv['dst_vgroup_idx'] = dst_vgroup_idx
                    break
            if dst_vgroup_idx < 0:
                message = "Dst vertex group is not valid."

    rv['error'] = message
    return rv
