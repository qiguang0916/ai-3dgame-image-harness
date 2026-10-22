#!/usr/bin/env python3
"""Optional deterministic glossy-enamel face retouch on a real native PNG.

This IS NOT an image generator, artist signoff, rights review or Steam approval.
It is a strictly source/Mask-bounded secondary derivation with byte-for-byte
independent recomputation in production_audit. Raw model bytes stay immutable.
"""
from __future__ import annotations

import io
import json
import math
import os
from pathlib import Path
from typing import Any

from artifact_integrity import canonical_json_bytes, resolve_in_workspace, sha256_bytes, sha256_file
from region_quality import _pixel_rect
from validate_project import ValidationError


PRESET = "smooth_nonmetallic_enamel_face_v1"
MAX_FACES = 8


def _shape(recipe: dict[str, Any], width: int, height: int,
           editable: Any) -> list[dict[str, Any]]:
    import numpy as np
    if not isinstance(recipe, dict) or set(recipe) != {"preset", "faces"} or recipe.get("preset") != PRESET:
        raise ValidationError("unsupported or unversioned material finish recipe")
    faces = recipe.get("faces")
    if not isinstance(faces, list) or not 1 <= len(faces) <= MAX_FACES:
        raise ValidationError("material finish faces must be a bounded nonempty list")
    ids: set[str] = set()
    normalized = []
    for item in faces:
        if not isinstance(item, dict) or set(item) != {"id", "center_uv", "radius_uv"}:
            raise ValidationError("material face requires exactly id/center_uv/radius_uv")
        name=item["id"]
        if not isinstance(name,str) or not name or len(name)>72 or name in ids:
            raise ValidationError("material face ID missing/duplicated")
        ids.add(name)
        center=item["center_uv"];rad=item["radius_uv"]
        if (not isinstance(center,list) or len(center)!=2
                or not isinstance(rad,list) or len(rad)!=2
                or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
                       for v in [*center,*rad])
                or not all(0.0 < u < 1.0 for u in center)
                or not all(0.003 <= v <= 0.12 for v in rad)):
            raise ValidationError("material face normalized coordinate/radius invalid")
        cx,cy=center[0]*width,center[1]*height
        rx,ry=rad[0]*width,rad[1]*height
        if rx<3 or ry<3:
            raise ValidationError("material face ellipse too small to fit safely")
        ix=min(width-1,int(cx));iy=min(height-1,int(cy))
        if ix<0 or iy<0 or not bool(editable[iy,ix]):
            raise ValidationError("material face center is not inside approved editable Mask")
        normalized.append({"id":name,"center":[cx,cy],"radius":[rx,ry]})
    # Overlaps would make output ordering matter and complicate independent QA.
    for i,a in enumerate(normalized):
        for b in normalized[:i]:
            if ((a["center"][0]-b["center"][0])/(a["radius"][0]+b["radius"][0]))**2 + ((a["center"][1]-b["center"][1])/(a["radius"][1]+b["radius"][1]))**2 < 1:
                raise ValidationError("material face ellipses may not overlap")
    return normalized


def _load(source: Path, native: Path, mask: Path, contract: dict[str,Any]):
    import numpy as np
    from PIL import Image
    if not isinstance(contract,dict) or not isinstance(contract.get("strict_mask"),dict):
        raise ValidationError("material finish requires frozen strict_mask contract")
    sha=contract["strict_mask"]
    if sha.get("reference_sha256")!=sha256_file(source) or sha.get("sha256")!=sha256_file(mask):
        raise ValidationError("material finish Master/approved Mask SHA mismatch")
    with Image.open(source) as im:
        im.load()
        if im.format!="PNG" or im.mode!="RGB":
            raise ValidationError("enamel preset requires RGB PNG Master")
        size=im.size;icc=im.info.get("icc_profile")
    with Image.open(native) as im:
        im.load()
        if (im.format,im.mode,im.size,im.info.get("icc_profile"))!=("PNG","RGB",size,icc):
            raise ValidationError("material finish native PNG coordinate/ICC mismatch")
        pixels=np.asarray(im,dtype=np.uint8).copy()
    with Image.open(mask) as im:
        im.load()
        if im.format!="PNG" or im.mode!="L" or im.size!=size:
            raise ValidationError("material finish mask must be same-size 8-bit PNG")
        locked=np.asarray(im,dtype=np.uint8).copy()
    if not np.all((locked==0)|(locked==255)):
        raise ValidationError("material finish strict mask must be binary")
    width,height=size
    target=np.zeros((height,width),dtype=bool)
    for item in contract.get("targets",[]):
        x0,y0,x1,y1=_pixel_rect(item["bbox"],width,height)
        target[y0:y1,x0:x1]=True
    editable=target&(locked==0)
    if not editable.any():
        raise ValidationError("no allowed material finish target pixels")
    return pixels,editable,locked,icc


def _render(source: Path, native: Path, mask: Path, contract: dict[str,Any],
            recipe: dict[str,Any]) -> tuple[bytes,dict[str,Any]]:
    import numpy as np
    from PIL import Image, ImageFilter
    native_data,editable,locked,icc=_load(source,native,mask,contract)
    original=native_data.copy()
    height,width=editable.shape
    shapes=_shape(recipe,width,height,editable)
    measurements=[]
    for face in shapes:
        cx,cy=face["center"];rx,ry=face["radius"]
        left=max(0,int(math.floor(cx-rx*1.04))-4)
        right=min(width,int(math.ceil(cx+rx*1.04))+5)
        top=max(0,int(math.floor(cy-ry*1.04))-4)
        bottom=min(height,int(math.ceil(cy+ry*1.04))+5)
        if right<=left or bottom<=top:
            raise ValidationError("material face crop invalid")
        Y,X=np.mgrid[top:bottom,left:right]
        dx=(X-cx)/rx;dy=(Y-cy)/ry
        radius=np.sqrt(dx*dx+dy*dy)
        panel=native_data[top:bottom,left:right,:].astype(np.float64)
        legal=editable[top:bottom,left:right]
        red=(panel[:,:,0]>50)&(panel[:,:,0]>panel[:,:,1]*1.45)&(panel[:,:,0]>panel[:,:,2]*1.3)
        fit=(radius<=0.75)&red&(panel[:,:,1]<35)&legal
        work=(radius<=1.01)&red&legal
        if int(fit.sum()) < 25 or int(work.sum()) < 40:
            raise ValidationError("native face is not sufficiently red/enamel-shaped")
        u=dx[fit];v=dy[fit]
        D=np.column_stack((np.ones(len(u)),u,v,u*u,u*v,v*v))
        pix=panel[fit]
        coeff=np.linalg.lstsq(D,pix,rcond=None)[0]
        for _ in range(3):
            err=np.max(np.abs(pix-D@coeff),axis=1)
            keep=err<np.percentile(err,85)
            if int(keep.sum())<20:
                raise ValidationError("material face has insufficient robust samples")
            coeff=np.linalg.lstsq(D[keep],pix[keep],rcond=None)[0]
        coeff=np.round(coeff,4)
        coord=np.stack((np.ones_like(dx),dx,dy,dx*dx,dx*dy,dy*dy),axis=-1)
        plane=np.clip(coord@coeff,0,255)
        t=np.clip((1.005-radius)/0.14,0,1)
        strength=t*t*(3-2*t)
        strength*=work.astype(np.float64)
        # Preserve genuine softbox highlights from the generated image, not
        # low-frequency metallic wedges or radial/concentric surface texture.
        bright=(panel[:,:,1]>42)&(panel[:,:,0]>125)&(dy<-0.30)&(dx>-0.82)&(dx<0.45)&(radius<1.03)
        high=np.asarray(Image.fromarray((bright.astype(np.uint8)*255),"L")
                        .filter(ImageFilter.GaussianBlur(radius=2.0)),dtype=np.float64)/255.
        strength*=1-np.clip(high,0,1)
        mixed=panel*(1-strength[:,:,None])+plane*strength[:,:,None]
        native_data[top:bottom,left:right,:]=np.rint(np.clip(mixed,0,255)).astype(np.uint8)
        measurements.append({"id":face["id"],"center_xy":[round(cx,5),round(cy,5)],
                             "radius_px":[round(rx,5),round(ry,5)],
                             "robust_fit_pixels":int(fit.sum()),"eligible_face_pixels":int(work.sum()),
                             "coefficients":coeff.tolist()})
    different=np.any(original!=native_data,axis=2)
    locked_changes=int((different&(locked==255)).sum())
    outside_changes=int((different&~editable).sum())
    changed=int(different.sum())
    if locked_changes or outside_changes or changed==0:
        raise ValidationError("material retouch escaped approved Mask or made no effective edit")
    memory=io.BytesIO()
    parameters={"format":"PNG"}
    if icc:parameters["icc_profile"]=icc
    Image.fromarray(native_data,"RGB").save(memory,**parameters)
    payload=memory.getvalue()
    metrics={"schema_version":1,"preset":PRESET,"status":"CANDIDATE_NEEDS_VISUAL_REVIEW",
             "recipe_sha256":sha256_bytes(canonical_json_bytes(recipe)),
             "approved_master_sha256":sha256_file(source),
             "native_sha256":sha256_file(native),
             "approved_mask_sha256":sha256_file(mask),
             "finished_sha256":sha256_bytes(payload),
             "changed_inside_editable":changed,"changed_outside_editable":outside_changes,
             "protected_pixel_mismatches":locked_changes,
             "faces":measurements,"human_art_approved":False,"steam_approved":False}
    return payload,metrics


def _write_new(path:Path,value:bytes)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as f:
        f.write(value);f.flush();os.fsync(f.fileno())


def finish_material(root:Path,source:Path,native:Path,mask:Path,
                    contract:dict[str,Any],recipe:dict[str,Any],
                    output:Path,report:Path)->dict[str,Any]:
    root=Path(root).resolve()
    paths=[resolve_in_workspace(root,p) for p in (source,native,mask,output,report)]
    if len(set(paths))!=5:
        raise ValidationError("material finish source/native/mask/output/report paths collide")
    source,native,mask,output,report=paths
    if output.suffix.lower()!=".png" or report.suffix.lower()!=".json":
        raise ValidationError("material finish artifacts require .png/.json")
    if (output.exists() or output.is_symlink() or report.exists() or report.is_symlink()):
        raise ValidationError("material finish artifacts must never overwrite originals")
    rendered,summary=_render(source,native,mask,contract,recipe)
    _write_new(output,rendered)
    _write_new(report,(json.dumps(summary,sort_keys=True,indent=2)+"\n").encode())
    return summary


def verify_finished_material(root:Path,source:Path,native:Path,mask:Path,
                             contract:dict[str,Any],recipe:dict[str,Any],
                             output:Path,report:Path)->dict[str,Any]:
    root=Path(root).resolve()
    source,native,mask,output,report=[resolve_in_workspace(root,p) for p in (source,native,mask,output,report)]
    if any(not p.is_file() or p.is_symlink() for p in (source,native,mask,output,report)):
        raise ValidationError("material finish evidence missing or symlinked")
    payload,expected=_render(source,native,mask,contract,recipe)
    if payload!=output.read_bytes():
        raise ValidationError("material finish bytes differ from independent deterministic replay")
    try:
        stored=json.loads(report.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise ValidationError("material finish report malformed") from exc
    if stored!=expected:
        raise ValidationError("material finish report differs from recomputed source/recipe")
    return {"status":"PASS_REPLAYED_NATIVE_MATERIAL_FINISH",
            "material_sha256":sha256_file(output),"recipe_sha256":expected["recipe_sha256"],
            "protected_pixel_mismatches":0,"changed_inside_editable":expected["changed_inside_editable"],
            "human_art_approved":False}

