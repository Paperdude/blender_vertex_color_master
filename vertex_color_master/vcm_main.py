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
from bpy.props import *
from mathutils import Color
from .vcm_globals import *
from .vcm_helpers import (
    get_effective_paint_colors,
    get_color_layers,
    get_paint_brush_candidates,
    set_paint_colors,
    sync_paint_color_sources,
    rgb_to_luminosity,
)

# VERTEXCOLORMASTER_Properties
class VertexColorMasterProperties(bpy.types.PropertyGroup):

    def get_brush_color_ui(self):
        color, _ = get_effective_paint_colors(bpy.context)
        return (color[0], color[1], color[2])

    def set_brush_color_ui(self, value):
        ctx = bpy.context
        set_paint_colors(ctx, primary=value)

    def get_brush_secondary_color_ui(self):
        _, secondary_color = get_effective_paint_colors(bpy.context)
        return (secondary_color[0], secondary_color[1], secondary_color[2])

    def set_brush_secondary_color_ui(self, value):
        ctx = bpy.context
        set_paint_colors(ctx, secondary=value)

    def update_active_channels(self, context):
        sync_paint_color_sources(context)
        if self.use_grayscale or not self.match_brush_to_active_channels:
            return None

        active_channels = self.active_channels
        alpha_only = active_channels == {alpha_id}

        # set draw color based on mask
        if alpha_only:
            value = 1.0 - self.brush_value_isolate
            draw_color = [value, value, value]
        else:
            draw_color = [0.0, 0.0, 0.0]
            if red_id in active_channels:
                draw_color[0] = 1.0
            if green_id in active_channels:
                draw_color[1] = 1.0
            if blue_id in active_channels:
                draw_color[2] = 1.0

        for brush in get_paint_brush_candidates(context):
            if hasattr(brush, 'use_alpha'):
                try:
                    if alpha_id in active_channels:
                        brush.use_alpha = True
                except Exception:
                    pass

        set_paint_colors(context, primary=draw_color)

        return None

    def update_brush_value_isolate(self, context):
        sync_paint_color_sources(context)
        v1 = self.brush_value_isolate
        v2 = self.brush_secondary_value_isolate
        set_paint_colors(context, primary=Color((v1, v1, v1)), secondary=Color((v2, v2, v2)))

        return None

    def toggle_grayscale(self, context):
        sync_paint_color_sources(context)
        if self.use_grayscale:
            color, secondary_color = get_effective_paint_colors(context)
            self.brush_color = color
            self.brush_secondary_color = secondary_color

            v1 = self.brush_value_isolate
            v2 = self.brush_secondary_value_isolate
            set_paint_colors(context, primary=Color((v1, v1, v1)), secondary=Color((v2, v2, v2)))
        else:
            set_paint_colors(context, primary=self.brush_color, secondary=self.brush_secondary_color)

        return None

    active_channels: EnumProperty(
        name="Active Channels",
        options={'ENUM_FLAG'},
        items=channel_items,
        description="Which channels to enable.",
        default={'R', 'G', 'B'},
        update=update_active_channels
    )

    match_brush_to_active_channels: BoolProperty(
        name="Match Active Channels",
        default=True,
        description="Change the brush color to match the active channels.",
        update=update_active_channels
    )

    use_grayscale: BoolProperty(
        name="Use Grayscale",
        default=False,
        description="Show grayscale values instead of RGB colors.",
        update=toggle_grayscale
    )

    # Used only to store the color between RGBA and isolate modes
    brush_color: FloatVectorProperty(
        name="Brush Color",
        description="Brush primary color.",
        default=(1, 0, 0)
    )

    brush_secondary_color: FloatVectorProperty(
        name="Brush Secondary Color",
        description="Brush secondary color.",
        default=(1, 0, 0)
    )

    brush_color_ui: FloatVectorProperty(
        name="Brush Color",
        description="Brush primary color.",
        subtype='COLOR',
        min=0.0, max=1.0,
        default=(1, 0, 0),
        get=get_brush_color_ui,
        set=set_brush_color_ui
    )

    brush_secondary_color_ui: FloatVectorProperty(
        name="Brush Secondary Color",
        description="Brush secondary color.",
        subtype='COLOR',
        min=0.0, max=1.0,
        default=(0, 0, 0),
        get=get_brush_secondary_color_ui,
        set=set_brush_secondary_color_ui
    )

    # Replacement for color in the isolate mode UI
    brush_value_isolate: FloatProperty(
        name="Brush Value",
        description="Value of the brush color.",
        default=1.0,
        min=0.0, max=1.0,
        update=update_brush_value_isolate
    )

    brush_secondary_value_isolate: FloatProperty(
        name="Brush Value",
        description="Value of the brush secondary color.",
        default=0.0,
        min=0.0, max=1.0,
        update=update_brush_value_isolate
    )

    def vcol_layer_items(self, context):
        obj = context.active_object
        mesh = obj.data

        color_layers = get_color_layers(mesh)
        items = [
            ("{0} {1}".format(type_vcol, vcol.name), 
             vcol.name, "") for vcol in color_layers]
        ext = [] if obj.vertex_groups is None else [
            ("{0} {1}".format(type_vgroup, group.name),
             "W: " + group.name, "") for group in obj.vertex_groups]
        items.extend(ext)
        ext = [] if mesh.uv_layers is None else [
            ("{0} {1}".format(type_uv, uv.name),
             "UV: " + uv.name, "") for uv in mesh.uv_layers]
        items.extend(ext)
        ext = [("{0} {1}".format(type_normal, "Normals"), "Normals", "")]
        items.extend(ext)

        return items

    src_vcol_id: EnumProperty(
        name="Source Layer",
        items=vcol_layer_items,
        description="Source (Src) vertex color layer.",
    )

    src_channel_id: EnumProperty(
        name="Source Channel",
        items=channel_items,
        # default=red_id,
        description="Source (Src) color channel."
    )

    dst_vcol_id: EnumProperty(
        name="Destination Layer",
        items=vcol_layer_items,
        description="Destination (Dst) vertex color layer.",
    )

    dst_channel_id: EnumProperty(
        name="Destination Channel",
        items=channel_items,
        # default=green_id,
        description="Destination (Dst) color channel."
    )

    channel_blend_mode: bpy.props.EnumProperty(
        name="Channel Blend Mode",
        items=channel_blend_mode_items,
        description="Channel blending operation.",
    )
   
