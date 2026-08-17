#!/usr/bin/env python3
"""
generate_reactor.py
====================

Инструмент генерации геометрии Т-образного микрофлюидного реактора
для генерации капель (см. чертёж "Лабораторный Т-образный
микрофлюидный реактор").

На выходе:
  - reactor_main_body.stl / .step  -- основное тело канала
  - cap_inlet_1.stl / .step        -- крышка входа 1 (левый торец гл. канала)
  - cap_inlet_2.stl / .step        -- крышка входа 2 (торец бокового канала)
  - cap_outlet.stl  / .step        -- крышка выхода (правый торец гл. канала)

STL строится через VTK (булево объединение боксов), STEP -- через
CadQuery/OpenCASCADE (точный BREP), см. geometry_core.py -- это
единый источник геометрии для обоих бэкендов.

Использование
-------------
    # значения по умолчанию = точно как на чертеже
    python3 generate_reactor.py --outdir out

    # варьирование параметров (например, для исследования влияния
    # длины бокового канала на генерацию капель)
    python3 generate_reactor.py --L2 12.0 --w 0.25 --outdir out_L2_12

Все размеры -- в миллиметрах.
"""

import configargparse
import argparse
import json
import os
import sys

from geometry_core import TReactorParams, bounding_box
from vtk_backend import generate_all_stl, build_main_body_polydata, check_manifold
# from step_backend import generate_all_step


# def build_arg_parser() -> argparse.ArgumentParser:
#     ap = argparse.ArgumentParser(
#         description="Генератор геометрии Т-образного микрофлюидного реактора (STL + STEP)"
#     )
#     ap.add_argument("--L1", type=float, default=10.0, help="Длина левого плеча главного канала, мм (по умолчанию 10)")
#     ap.add_argument("--L2", type=float, default=8.0, help="Длина бокового канала, мм (по умолчанию 8)")
#     ap.add_argument("--L3", type=float, default=30.0, help="Длина правого плеча главного канала, мм (по умолчанию 30)")
#     ap.add_argument("--w", type=float, default=0.2, help="Ширина главного канала, мм (по умолчанию 0.2 = 200 мкм)")
#     ap.add_argument("--wd", type=float, default=0.1, help="Ширина бокового канала, мм (по умолчанию 0.1 = 100 мкм)")
#     ap.add_argument("--h", type=float, default=0.1, help="Высота (глубина) канала, мм (по умолчанию 0.1 = 100 мкм)")
#     ap.add_argument("--cap-thickness", type=float, default=0.3, help="Толщина крышек портов, мм (по умолчанию 0.3)")
#     ap.add_argument("--outdir", type=str, default="reactor_output", help="Папка для выходных файлов")
#     ap.add_argument("--stl-only", action="store_true", help="Сгенерировать только STL (пропустить STEP)")
#     ap.add_argument("--step-only", action="store_true", help="Сгенерировать только STEP (пропустить STL)")
#     return ap


def build_arg_parser() -> configargparse.ArgumentParser:
    ap = configargparse.ArgumentParser(
        description="Генератор геометрии Т-образного микрофлюидного реактора (STL + STEP)",
        default_config_files=[]  # можно указать файл по умолчанию, если хотите
    )
    # Добавляем аргумент для указания конфигурационного файла
    ap.add_argument('--config', is_config_file=True, help='Путь к файлу конфигурации (JSON/YAML/INI)')

    ap.add_argument("--L1", type=float, default=10.0, help="Длина левого плеча главного канала, мм (по умолчанию 10)")
    ap.add_argument("--L2", type=float, default=8.0, help="Длина бокового канала, мм (по умолчанию 8)")
    ap.add_argument("--L3", type=float, default=30.0, help="Длина правого плеча главного канала, мм (по умолчанию 30)")
    ap.add_argument("--w", type=float, default=0.2, help="Ширина главного канала, мм (по умолчанию 0.2 = 200 мкм)")
    ap.add_argument("--wd", type=float, default=0.1, help="Ширина бокового канала, мм (по умолчанию 0.1 = 100 мкм)")
    ap.add_argument("--h", type=float, default=0.1, help="Высота (глубина) канала, мм (по умолчанию 0.1 = 100 мкм)")
    ap.add_argument("--cap-thickness", type=float, default=0.3, help="Толщина крышек портов, мм (по умолчанию 0.3)")
    ap.add_argument("--outdir", type=str, default="reactor_output", help="Папка для выходных файлов")
    ap.add_argument("--stl-only", action="store_true", help="Сгенерировать только STL (пропустить STEP)")
    ap.add_argument("--step-only", action="store_true", help="Сгенерировать только STEP (пропустить STL)")

    return ap

def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    params = TReactorParams(
        L1=args.L1, L2=args.L2, L3=args.L3,
        w=args.w, wd=args.wd, h=args.h,
        cap_thickness=args.cap_thickness,
    )

    os.makedirs(args.outdir, exist_ok=True)

    # Сохраняем использованные параметры рядом с геометрией -- удобно
    # при варьировании параметров для последующего анализа результатов.
    with open(os.path.join(args.outdir, "params.json"), "w", encoding="utf-8") as f:
        json.dump(params.__dict__, f, ensure_ascii=False, indent=2)

    results = {}

    if not args.step_only:
        print("== Построение STL (VTK) ==")
        stl_paths = generate_all_stl(params, args.outdir)
        # диагностика замкнутости сетки основного тела
        body_pd = build_main_body_polydata(params)
        diag = check_manifold(body_pd)
        print(f"  Основное тело: {diag['n_points']} точек, {diag['n_cells']} треугольников, "
              f"открытых рёбер: {diag['n_open_edges']} "
              f"({'ЗАМКНУТО' if diag['watertight'] else 'ЕСТЬ ОТВЕРСТИЯ -- ожидаемо: 3 порта'})")
        for name, path in stl_paths.items():
            print(f"  {name}: {path}")
        results["stl"] = stl_paths

    # if not args.stl_only:
    #     print("== Построение STEP (CadQuery/OpenCASCADE) ==")
    #     step_paths = generate_all_step(params, args.outdir)
    #     for name, path in step_paths.items():
    #         print(f"  {name}: {path}")
    #     results["step"] = step_paths
    #
    # bbox = bounding_box(params)
    # print(f"Габариты сборки (тело+крышки), мм: "
    #       f"X[{bbox[0]:.3f},{bbox[1]:.3f}] Y[{bbox[2]:.3f},{bbox[3]:.3f}] Z[{bbox[4]:.3f},{bbox[5]:.3f}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
