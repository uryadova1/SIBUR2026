from dataclasses import dataclass
import argparse
import vtk


@dataclass
class TReactorParams:
    """
    Геометрические параметры T-реактора.
    Все размеры в миллиметрах.
    """

    L1: float = 10.0      # длина левого участка
    L2: float = 8.0       # длина вертикального участка
    L3: float = 30.0      # длина правого участка

    w: float = 200.0      # ширина основного канала
    wd: float = 100.0     # ширина вертикального канала

    h: float = 100.0      # высота канала


def create_t_reactor(params: TReactorParams) -> vtk.vtkPolyData:
    """
    Создаёт 3D-объём T-образного канала.

    Система координат:
        X — горизонтальное направление
        Y — направление вертикального ответвления
        Z — высота канала

    Геометрия соответствует чертежу:
        L1 — от левого торца до левой стенки ответвления
        L3 — от правой стенки ответвления до правого торца
        L2 — длина ответвления вниз от основного канала
        w  — ширина основного канала
        wd — ширина ответвления
        h  — высота канала
    """

    L1 = params.L1
    L2 = params.L2
    L3 = params.L3
    w = params.w
    wd = params.wd
    h = params.h

    # -----------------------------
    # Проверка параметров
    # -----------------------------

    if L1 < 0 or L2 < 0 or L3 < 0:
        raise ValueError("L1, L2 и L3 должны быть >= 0")

    if w <= 0 or wd <= 0 or h <= 0:
        raise ValueError("w, wd и h должны быть > 0")

    if wd > w:
        raise ValueError("wd не может быть больше w")

    # -----------------------------
    # Геометрия T в плоскости XY
    # -----------------------------

    # Вертикальный канал расположен по центру.
    #
    # Общая длина горизонтального канала:
    #
    #      L1       wd       L3
    # |----------|--------|----------|
    #
    #            |
    #            |
    #            | L2
    #            |
    #

    x_left = -(L1 + wd / 2.0)
    x_right = +(L3 + wd / 2.0)

    y_top = +w / 2.0
    y_bottom = -w / 2.0

    x_branch_left = -wd / 2.0
    x_branch_right = +wd / 2.0

    y_branch_bottom = y_bottom - L2

    # Контур T-образного канала.
    #
    #                 x_right
    #        ┌────────────────────┐
    #        │                    │
    #        │                    │
    #        └───────┐    ┌───────┘
    #                │    │
    #                │    │
    #                │    │
    #                └────┘
    #
    #        x_left       x=0
    #
    points_2d = [
        (x_left,          y_top),
        (x_right,         y_top),
        (x_right,         y_bottom),
        (x_branch_right,  y_bottom),
        (x_branch_right,  y_branch_bottom),
        (x_branch_left,   y_branch_bottom),
        (x_branch_left,   y_bottom),
        (x_left,           y_bottom),
    ]

    # -----------------------------
    # Создание 2D-полигона
    # -----------------------------

    points = vtk.vtkPoints()

    for x, y in points_2d:
        points.InsertNextPoint(x, y, 0.0)

    polygon = vtk.vtkPolygon()
    polygon.GetPointIds().SetNumberOfIds(len(points_2d))

    for i in range(len(points_2d)):
        polygon.GetPointIds().SetId(i, i)

    cells = vtk.vtkCellArray()
    cells.InsertNextCell(polygon)

    surface_2d = vtk.vtkPolyData()
    surface_2d.SetPoints(points)
    surface_2d.SetPolys(cells)

    # -----------------------------
    # Выдавливание по высоте h
    # -----------------------------

    extrusion = vtk.vtkLinearExtrusionFilter()

    extrusion.SetInputData(surface_2d)

    extrusion.SetExtrusionTypeToVectorExtrusion()
    extrusion.SetVector(0.0, 0.0, h)

    # Создать верхнюю и нижнюю крышки
    extrusion.CappingOn()

    extrusion.Update()

    # -----------------------------
    # Триангуляция
    # -----------------------------

    triangle_filter = vtk.vtkTriangleFilter()
    triangle_filter.SetInputConnection(
        extrusion.GetOutputPort()
    )
    triangle_filter.Update()

    # -----------------------------
    # Удаление дублирующихся точек
    # -----------------------------

    clean = vtk.vtkCleanPolyData()
    clean.SetInputConnection(
        triangle_filter.GetOutputPort()
    )
    clean.Update()

    # -----------------------------
    # Результат
    # -----------------------------

    result = vtk.vtkPolyData()
    result.DeepCopy(clean.GetOutput())

    return result


def save_stl(polydata: vtk.vtkPolyData, filename: str):
    """
    Сохраняет геометрию в STL.
    """

    writer = vtk.vtkSTLWriter()

    writer.SetFileName(filename)
    writer.SetInputData(polydata)

    writer.SetFileTypeToBinary()

    if not writer.Write():
        raise RuntimeError(
            f"Не удалось записать STL: {filename}"
        )

    print(f"STL сохранён: {filename}")


def create_actor(polydata: vtk.vtkPolyData):
    """
    Создаёт VTK actor для визуализации.
    """

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    # Отображение граней
    actor.GetProperty().SetEdgeVisibility(True)
    actor.GetProperty().SetLineWidth(1.0)

    # Немного прозрачности
    actor.GetProperty().SetOpacity(0.8)

    return actor


def show_model(polydata: vtk.vtkPolyData):
    """
    Открывает окно с 3D-моделью.
    """

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(
        0.12, 0.12, 0.15
    )

    actor = create_actor(polydata)
    renderer.AddActor(actor)

    # Координатные оси
    axes = vtk.vtkAxesActor()
    axes.SetTotalLength(
        50.0,
        50.0,
        50.0
    )

    axes.SetShaftTypeToLine()
    axes.SetAxisLabels(True)

    renderer.AddActor(axes)

    # Окно
    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)

    render_window.SetSize(
        1000,
        700
    )

    render_window.SetWindowName(
        "T-shaped microfluidic reactor"
    )

    # Интерактор
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(
        render_window
    )

    # Камера
    renderer.ResetCamera()

    camera = renderer.GetActiveCamera()

    camera.Elevation(25)
    camera.Azimuth(-35)

    renderer.ResetCameraClippingRange()

    # Запуск
    render_window.Render()
    interactor.Start()


def parse_arguments():
    """
    Чтение параметров из командной строки.
    """

    parser = argparse.ArgumentParser(
        description="Генерация T-образного микрофлюидного реактора"
    )

    parser.add_argument(
        "--L1",
        type=float,
        default=10.0,
        help="Длина левого участка, мм"
    )

    parser.add_argument(
        "--L2",
        type=float,
        default=8.0,
        help="Длина вертикального участка, мм"
    )

    parser.add_argument(
        "--L3",
        type=float,
        default=30.0,
        help="Длина правого участка, мм"
    )

    parser.add_argument(
        "--w",
        type=float,
        default=200.0,
        help="Ширина основного канала, мм"
    )

    parser.add_argument(
        "--wd",
        type=float,
        default=100.0,
        help="Ширина вертикального канала, мм"
    )

    parser.add_argument(
        "--h",
        type=float,
        default=100.0,
        help="Высота канала, мм"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="t_reactor.stl",
        help="Имя STL-файла"
    )

    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Не открывать окно визуализации"
    )

    return parser.parse_args()


def main():

    args = parse_arguments()

    # -----------------------------
    # Параметры
    # -----------------------------

    params = TReactorParams(
        L1=args.L1,
        L2=args.L2,
        L3=args.L3,
        w=args.w,
        wd=args.wd,
        h=args.h,
    )

    print("Параметры реактора:")
    print(f"  L1 = {params.L1} мм")
    print(f"  L2 = {params.L2} мм")
    print(f"  L3 = {params.L3} мм")
    print(f"  w  = {params.w} мм")
    print(f"  wd = {params.wd} мм")
    print(f"  h  = {params.h} мм")

    total_length = (
        params.L1
        + params.wd
        + params.L3
    )

    print(
        f"  Общая длина = {total_length} мм"
    )

    # -----------------------------
    # Создание геометрии
    # -----------------------------

    reactor = create_t_reactor(params)

    print(
        f"Создано точек: {reactor.GetNumberOfPoints()}"
    )

    print(
        f"Создано полигонов: {reactor.GetNumberOfPolys()}"
    )

    # -----------------------------
    # STL
    # -----------------------------

    save_stl(
        reactor,
        args.output
    )

    # -----------------------------
    # Визуализация
    # -----------------------------

    if not args.no_gui:
        show_model(reactor)


if __name__ == "__main__":
    main()