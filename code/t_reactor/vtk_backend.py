import os
from typing import Dict, List, Tuple

import vtk

from .geometry_core import (
    TReactorParams,
    t_shape_outline,
    main_body_wall_rects,
    port_specs,
    cap_rects,
)


def _polygon_cell(points_3d: List[Tuple[float, float, float]],
                  desired_normal: Tuple[float, float, float]) -> vtk.vtkPolyData:
    """Строит один плоский полигон (грань) по списку вершин, автоматически
    подбирая порядок обхода так, чтобы нормаль грани совпадала по
    направлению с desired_normal (наружу тела).
    """
    pts = vtk.vtkPoints()
    for x, y, z in points_3d:
        pts.InsertNextPoint(x, y, z)

    # нормаль по первым трём вершинам (все наши грани -- плоские
    # прямоугольники или простой Т-контур, этого достаточно)
    p0 = points_3d[0]
    p1 = points_3d[1]
    p2 = points_3d[2]
    v1 = tuple(p1[i] - p0[i] for i in range(3))
    v2 = tuple(p2[i] - p0[i] for i in range(3))
    n = (
        v1[1] * v2[2] - v1[2] * v2[1],
        v1[2] * v2[0] - v1[0] * v2[2],
        v1[0] * v2[1] - v1[1] * v2[0],
    )
    dot = sum(n[i] * desired_normal[i] for i in range(3))
    order = list(range(len(points_3d)))
    if dot < 0:
        order = order[::-1]

    poly = vtk.vtkPolygon()
    poly.GetPointIds().SetNumberOfIds(len(order))
    for i, idx in enumerate(order):
        poly.GetPointIds().SetId(i, idx)

    cells = vtk.vtkCellArray()
    cells.InsertNextCell(poly)

    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(cells)
    return pd


def build_main_body_polydata(p: TReactorParams) -> vtk.vtkPolyData:
    """Строит полигональное тело канала как открытую (с 3 отверстиями
    под порты) призму: верх + низ (Т-образный контур) + боковые
    стенки, ИСКЛЮЧАЯ три торца портов (inlet_1, inlet_2, outlet) --
    там остаются открытые отверстия, которые закрываются отдельными
    "крышками" (см. build_cap_polydata).

    Грани строятся явно (не через 3D-булеву операцию и не через
    vtkLinearExtrusionFilter) -- геометрия целиком прямоугольная
    (Manhattan-подобная), поэтому явное построение граней надёжнее
    и не подвержено численным сбоям, характерным для CSG-фильтров
    VTK на тонких/высоко-аспектных объектах.
    """
    outline = t_shape_outline(p)

    pieces = []

    # верх и низ (Т-образный контур)
    top_pts = [(x, y, p.h) for x, y in outline]
    bottom_pts = [(x, y, 0.0) for x, y in outline]
    pieces.append(_polygon_cell(top_pts, desired_normal=(0.0, 0.0, 1.0)))
    pieces.append(_polygon_cell(bottom_pts, desired_normal=(0.0, 0.0, -1.0)))

    # Ориентация контура (по формуле площади многоугольника Гаусса):
    # для ПРОСТОГО многоугольника внешняя нормаль ребра однозначно
    # выражается через направление ребра и общую ориентацию обхода
    # -- это точная формула, а не эвристика, и она корректна и для
    # невыпуклых контуров (в отличие от подхода "от центра масс",
    # который для узкого длинного Т-контура даёт неверный знак).
    n_pts = len(outline)
    signed_area2 = sum(
        outline[i][0] * outline[(i + 1) % n_pts][1] - outline[(i + 1) % n_pts][0] * outline[i][1]
        for i in range(n_pts)
    )
    ccw = signed_area2 > 0  # True если контур обходится против часовой стрелки

    # боковые стенки (за исключением 3 портов)
    for wall in main_body_wall_rects(p):
        (x1, y1, _), (x2, y2, _) = wall[0], wall[1]
        dx, dy = x2 - x1, y2 - y1
        if ccw:
            outward = (dy, -dx, 0.0)
        else:
            outward = (-dy, dx, 0.0)
        pieces.append(_polygon_cell(wall, desired_normal=outward))

    append = vtk.vtkAppendPolyData()
    for piece in pieces:
        append.AddInputData(piece)
    append.Update()

    tri = vtk.vtkTriangleFilter()
    tri.SetInputData(append.GetOutput())
    tri.Update()

    clean = vtk.vtkCleanPolyData()
    clean.SetInputData(tri.GetOutput())
    clean.Update()

    out = vtk.vtkPolyData()
    out.DeepCopy(clean.GetOutput())
    return out


def build_cap_polydata(p: TReactorParams) -> Dict[str, vtk.vtkPolyData]:
    """Строит плоские (нулевой толщины) грани трёх крышек портов.

    Каждая крышка -- один плоский четырёхугольник (2 треугольника),
    лежащий ровно в плоскости соответствующего торца канала, с
    нормалью, направленной НАРУЖУ (в сторону, противоположную
    основному телу) -- как и полагается грани, "закрывающей" отверстие
    порта снаружи.
    """
    ports = port_specs(p)
    rects = cap_rects(p)
    caps: Dict[str, vtk.vtkPolyData] = {}
    for name, pts in rects.items():
        spec = ports[name]
        axis = spec["axis"]
        sign = spec["sign"]
        desired_normal = [0.0, 0.0, 0.0]
        desired_normal[axis] = float(sign)
        pd = _polygon_cell(pts, desired_normal=tuple(desired_normal))
        tri = vtk.vtkTriangleFilter()
        tri.SetInputData(pd)
        tri.Update()
        out = vtk.vtkPolyData()
        out.DeepCopy(tri.GetOutput())
        caps[name] = out
    return caps


def write_stl(polydata: vtk.vtkPolyData, filepath: str, binary: bool = True) -> None:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(filepath)
    writer.SetInputData(polydata)
    if binary:
        writer.SetFileTypeToBinary()
    else:
        writer.SetFileTypeToASCII()
    writer.Write()


def check_manifold(polydata: vtk.vtkPolyData) -> dict:
    """Быстрая диагностика сетки: количество открытых ("свободных") рёбер.

    0 свободных рёбер = сетка замкнута (watertight), что важно для
    последующего объёмного построения сетки в CFD-солвере.
    """
    feat = vtk.vtkFeatureEdges()
    feat.SetInputData(polydata)
    feat.BoundaryEdgesOn()
    feat.NonManifoldEdgesOn()
    feat.FeatureEdgesOff()
    feat.ManifoldEdgesOff()
    feat.Update()
    n_open = feat.GetOutput().GetNumberOfCells()
    return {
        "n_points": polydata.GetNumberOfPoints(),
        "n_cells": polydata.GetNumberOfCells(),
        "n_open_edges": n_open,
        "watertight": n_open == 0,
    }


def generate_all_stl(p: TReactorParams, outdir: str) -> Dict[str, str]:
    """Строит основное тело и 3 крышки и сохраняет их в STL.

    Возвращает словарь {название_детали: путь_к_файлу}.
    """
    os.makedirs(outdir, exist_ok=True)
    paths: Dict[str, str] = {}

    body = build_main_body_polydata(p)
    body_path = os.path.join(outdir, "reactor_main_body.stl")
    write_stl(body, body_path)
    paths["main_body"] = body_path

    caps = build_cap_polydata(p)
    for name, pd in caps.items():
        cap_path = os.path.join(outdir, f"cap_{name}.stl")
        write_stl(pd, cap_path)
        paths[f"cap_{name}"] = cap_path

    return paths
