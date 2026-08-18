

import os
from typing import Dict

import cadquery as cq

from geometry_core import (
    TReactorParams,
    BoxSpec,
    t_shape_outline,
    cap_boxes,
)


def _box_from_spec(box: BoxSpec) -> cq.Workplane:
    xmin, xmax, ymin, ymax, zmin, zmax = box
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    cx, cy, cz = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0
    return (
        cq.Workplane("XY")
        .box(dx, dy, dz, centered=(True, True, True))
        .translate((cx, cy, cz))
    )


def build_main_body_solid(p: TReactorParams) -> cq.Workplane:

    outline = t_shape_outline(p)
    sketch = cq.Workplane("XY").polyline(outline).close()
    solid = sketch.extrude(p.h)
    return solid


def build_cap_solids(p: TReactorParams) -> Dict[str, cq.Workplane]:
    boxes = cap_boxes(p)
    return {name: _box_from_spec(box) for name, box in boxes.items()}


def write_step(shape: cq.Workplane, filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    cq.exporters.export(shape, filepath, exportType="STEP")


def generate_all_step(p: TReactorParams, outdir: str) -> Dict[str, str]:
    os.makedirs(outdir, exist_ok=True)
    paths: Dict[str, str] = {}

    body = build_main_body_solid(p)
    body_path = os.path.join(outdir, "reactor_main_body.step")
    write_step(body, body_path)
    paths["main_body"] = body_path

    caps = build_cap_solids(p)
    for name, solid in caps.items():
        cap_path = os.path.join(outdir, f"cap_{name}.step")
        write_step(solid, cap_path)
        paths[f"cap_{name}"] = cap_path

    return paths