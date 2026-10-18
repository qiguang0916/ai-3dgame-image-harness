#!/usr/bin/env python3
"""Blender-only read-only geometry view exporter (not an AI image generator)."""
import bpy
import json
import os
import sys
import math
import hashlib
from mathutils import Vector,Matrix
from pathlib import Path
# Invoke with: blender -b --python scripts/blender_canonical_views.py -- \
#   --source /path/model.glb --out /path/NEW_VIEW_FOLDER
import argparse
args_raw = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
parser=argparse.ArgumentParser(description='Export read-only, source-bound canonical GLB QA renders')
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args(args_raw)
source=args.source.expanduser().resolve()
output=args.out.expanduser().resolve()
if not source.is_file() or source.suffix.lower()!='.glb':
    raise RuntimeError('source must be existing .glb file')
if output.exists() and any(output.iterdir()):
    raise RuntimeError('refusing to overwrite existing canonical evidence folder')
output.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
bpy.context.view_layer.update()
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(objects)>=1, 'GLB must contain at least one renderable mesh'
corners=[obj.matrix_world@Vector(v) for obj in objects for v in obj.bound_box]
minimum=[min(p[k] for p in corners) for k in range(3)]
maximum=[max(p[k] for p in corners) for k in range(3)]
mid=Vector([(a+b)/2 for a,b in zip(minimum,maximum)])
spans=[b-a for a,b in zip(minimum,maximum)]
axes=sorted(range(3),key=lambda x:spans[x],reverse=True)
length_axis=axes[0]; width_axis=axes[1]; thickness_axis=axes[2]
scene=bpy.context.scene
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=960
scene.render.resolution_y=720
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.display.shading.light='STUDIO'
scene.display.shading.color_type='SINGLE'
scene.display.shading.single_color=(0.72,0.74,0.76)
scene.display.shading.show_cavity=True
scene.display.shading.cavity_type='BOTH'
scene.render.film_transparent=False
scene.display.shading.background_type='WORLD'
scene.world=bpy.data.worlds.new('VIEW_BACKGROUND')
scene.world.color=(0.14,0.16,0.18)
scene.camera=None
camera_data=bpy.data.cameras.new('CANONICAL_TEST_CAMERA')
camera=bpy.data.objects.new('CANONICAL_TEST_CAMERA',camera_data)
scene.collection.objects.link(camera)
scene.camera=camera
camera_data.type='ORTHO'
camera_data.ortho_scale=max(spans)*1.48
camera.rotation_mode='QUATERNION'
def unit_axis(k,positive=True):
 xyz=[0.0,0.0,0.0];xyz[k]=1.0 if positive else -1.0
 return Vector(xyz)
# Use stable camera up-vector from model's width/thickness axes; for top/edge
# orientations, ensure the long axis visually remains horizontal.
views=[
 ('BROAD_A',unit_axis(thickness_axis)),
 ('BROAD_B',unit_axis(thickness_axis,False)),
 ('SPINE',unit_axis(width_axis)),
 ('QUARTER',unit_axis(width_axis)+unit_axis(thickness_axis)),
]
results=[]
for name,direction in views:
 direction.normalize()
 camera.location=mid+direction*max(spans)*3
 right=unit_axis(length_axis)
 up=direction.cross(right).normalized()
 # Camera X=long-axis, Y=screen-up, Z=viewpoint vector.
 mat=Matrix(((right.x,up.x,direction.x),(right.y,up.y,direction.y),(right.z,up.z,direction.z)))
 camera.rotation_quaternion=mat.to_quaternion()
 target=output/(name+'.png')
 scene.render.filepath=str(target)
 bpy.ops.render.render(write_still=True)
 results.append({'name':name,'image':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'width':960,'height':720})
metadata={
 'source_glb':str(source),
 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'generator':'blender-workbench-static-geometry-reference',
 'blender_version':bpy.app.version_string,
 'views':results,'camera_type':'ORTHO',
 'bbox_span':spans,'long_axis':length_axis,'width_axis':width_axis,'thickness_axis':thickness_axis,
 'mesh_names':[o.name for o in objects],
 'authoritative':'CANDIDATE_ONLY: deterministic reference from named GLB, not user-approved Master or commercial signoff',
}
(output/'manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print('CANONICAL_EVIDENCE:'+json.dumps({'meshes':len(objects),'spans':spans,'views':len(results),'out':str(output)}))
