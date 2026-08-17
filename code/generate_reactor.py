#!/usr/bin/env python3

import argparse
import json
import os
import sys

from t_reactor.geometry_core import TReactorParams
from t_reactor.vtk_backend import generate_all_stl, build_main_body_polydata, check_manifold



def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Генератор геометрии Т-образного микрофлюидного реактора (STL + STEP)"
    )
    ap.add_argument(
        "config", nargs="?", default=None,
        help="Путь к JSON-файлу с параметрами (если не указан, используются значения по умолчанию)"
    )
    return ap


def load_params_from_json(config_path: str) -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    params = {}
    for key, value in data.items():
        params[key] = value
    return params

def main(argv=None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)

    default_params = {
        "reactor": "T",
        'L1': 10.0,
        'L2': 8.0,
        'L3': 30.0,
        'w': 0.2,
        'wd': 0.1,
        'h': 0.1,
        'cap_thickness': 0.3,
        'outdir': 'stl/try',
    }

    params = default_params.copy()

    if args.config:
        json_params = load_params_from_json(args.config)
        params.update(json_params)
    else:
        print("Предупреждение: не указан --config, используются параметры по умолчанию.", file=sys.stderr)

    reactor_params = TReactorParams(
        L1=params['L1'],
        L2=params['L2'],
        L3=params['L3'],
        w=params['w'],
        wd=params['wd'],
        h=params['h'],
        cap_thickness=params['cap_thickness'],
    )

    outdir = params['outdir']

    os.makedirs(outdir, exist_ok=True)

    results = {}

    print("== Построение STL (VTK) ==")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    outdir_path = os.path.join(project_root, params['outdir'])
    stl_paths = generate_all_stl(reactor_params, outdir_path)

    with open(os.path.join(outdir_path, "params.json"), "w", encoding="utf-8") as f:
        json.dump(reactor_params.__dict__, f, ensure_ascii=False, indent=2)
    # диагностика замкнутости сетки основного тела
    body_pd = build_main_body_polydata(reactor_params)
    diag = check_manifold(body_pd)
    print(f"  Основное тело: {diag['n_points']} точек, {diag['n_cells']} треугольников, "
          f"открытых рёбер: {diag['n_open_edges']} "
          f"({'ЗАМКНУТО' if diag['watertight'] else 'ЕСТЬ ОТВЕРСТИЯ -- ожидаемо: 3 порта'})")
    for name, path in stl_paths.items():
        print(f"  {name}: {path}")
    results["stl"] = stl_paths

    return 0


if __name__ == "__main__":
    sys.exit(main())
