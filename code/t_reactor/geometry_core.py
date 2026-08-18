
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Прямоугольный параллелепипед, заданный диапазонами координат (мм)
BoxSpec = Tuple[float, float, float, float, float, float]  # xmin,xmax,ymin,ymax,zmin,zmax


@dataclass
class TReactorParams:
    """Параметры Т-образного реактора (все размеры в мм).

    Соответствие обозначениям на чертеже (в скобках — значение
    на чертеже в мкм/мм, для справки):
    """
    L1: float = 10.0     # длина левого плеча главного канала, мм
    L2: float = 8.0      # длина бокового (дозирующего) канала, мм
    L3: float = 30.0     # длина правого плеча главного канала, мм
    w: float = 0.2        # ширина главного канала, мм (200 мкм)
    wd: float = 0.1       # ширина бокового канала, мм (100 мкм)
    h: float = 0.1        # высота (глубина) канала, мм (100 мкм)

    # Технологический параметр инструмента (не с чертежа): доля
    # перекрытия бокового канала с главным; не влияет на итоговую
    # длину L2, т.к. отсчитывается уже ВНУТРИ главного канала.
    junction_overlap: float = 0.0

    def __post_init__(self):
        for name in ("L1", "L2", "L3", "w", "wd", "h"):
            if getattr(self, name) <= 0:
                raise ValueError(f"Параметр {name} должен быть положительным")
        if self.wd > self.w:
            raise ValueError("Ширина бокового канала wd не может превышать ширину главного канала w")

    # -- производные величины -------------------------------------------------
    @property
    def total_length(self) -> float:
        """Полная длина главного канала L1+L3, мм."""
        return self.L1 + self.L3

    @property
    def junction_x(self) -> float:
        """Координата X центра Т-образного стыка (= L1)."""
        return self.L1


def t_shape_outline(p: TReactorParams) -> List[Tuple[float, float]]:
    """Контур (2D, плоскость XY) Т-образной полости канала.

    Так как высота h одинакова и для главного, и для бокового
    канала (см. сечение А-А на чертеже), всё тело реактора -- это
    просто призма: плоский Т-образный контур, "выдавленный" по Z на
    величину h. Такой подход даёт ГАРАНТИРОВАННО замкнутое
    (watertight) тело без необходимости в трёхмерной булевой
    операции над объёмными боксами, которая для тонких
    высоко-аспектных боксов с совпадающими гранями по Z численно
    неустойчива (см. vtk_backend.py).

    Контур обходится против часовой стрелки, начиная с левого
    верхнего угла главного канала.
    """
    x0, x1 = 0.0, p.total_length
    y_top, y_bot = p.w / 2.0, -p.w / 2.0
    xL = p.junction_x - p.wd / 2.0
    xR = p.junction_x + p.wd / 2.0
    y_branch = -(p.w / 2.0 + p.L2)

    return [
        (x0, y_top),
        (x1, y_top),
        (x1, y_bot),
        (xR, y_bot),
        (xR, y_branch),
        (xL, y_branch),
        (xL, y_bot),
        (x0, y_bot),
    ]


def main_body_wall_rects(p: TReactorParams) -> List[List[Tuple[float, float, float]]]:
    """Прямоугольные стенки основного тела (боковые "вертикальные"
    грани призмы), КРОМЕ трёх портовых торцов -- те остаются
    открытыми (сквозными отверстиями), чтобы их отдельно закрывали
    "крышки" (см. cap_rects). Крышки + эти стенки + верх/низ вместе
    образуют полностью замкнутый объём.

    Каждая стенка возвращается как список из 4 вершин (x,y,z) в
    порядке обхода (не обязательно "наружу" -- ориентация
    выставляется бэкендом при построении полигона).
    """
    outline = t_shape_outline(p)
    n = len(outline)
    # Индексы рёбер контура (см. t_shape_outline): 1,4,7 -- открытые
    # порты (outlet, inlet_2, inlet_1 соответственно), остальные --
    # обычные стенки.
    open_edge_indices = {1, 4, 7}
    walls = []
    for i in range(n):
        if i in open_edge_indices:
            continue
        x1, y1 = outline[i]
        x2, y2 = outline[(i + 1) % n]
        walls.append([
            (x1, y1, 0.0),
            (x2, y2, 0.0),
            (x2, y2, p.h),
            (x1, y1, p.h),
        ])
    return walls


def port_specs(p: TReactorParams) -> Dict[str, dict]:
    """Геометрия трёх портов (входов/выходов) реактора.

    Для каждого порта возвращает словарь с:
      - 'axis'   : 0/1/2 -> ось X/Y/Z, вдоль которой смотрит порт
      - 'sign'   : -1 или +1, направление нормали (наружу из тела)
      - 'coord'  : координата торцевой плоскости порта вдоль axis
      - 'u_range', 'v_range' : диапазоны двух других координат
        (то есть форма поперечного сечения порта)
    """
    return {
        "inlet_1": dict(
            axis=0, sign=-1, coord=0.0,
            u_range=(-p.w / 2.0, p.w / 2.0),  # Y
            v_range=(0.0, p.h),                # Z
        ),
        "outlet": dict(
            axis=0, sign=+1, coord=p.total_length,
            u_range=(-p.w / 2.0, p.w / 2.0),  # Y
            v_range=(0.0, p.h),                # Z
        ),
        "inlet_2": dict(
            axis=1, sign=-1, coord=-(p.w / 2.0 + p.L2),
            u_range=(p.junction_x - p.wd / 2.0, p.junction_x + p.wd / 2.0),  # X
            v_range=(0.0, p.h),                                              # Z
        ),
    }


def cap_rects(p: TReactorParams) -> Dict[str, List[Tuple[float, float, float]]]:
    """Плоские (нулевой толщины) прямоугольники трёх "крышек" портов.

    Каждая крышка -- это ПЛОСКАЯ грань, лежащая ровно в плоскости
    соответствующего торца канала (не отдельная пластина со
    смещением/толщиной) и в точности повторяющая его поперечное
    сечение (w x h для главного канала, wd x h для бокового).

    Возвращает для каждого порта список из 4 вершин (x,y,z) в порядке
    обхода (без учёта ориентации/нормали -- она выставляется в
    бэкенде отдельно, по нормали порта).
    """
    ports = port_specs(p)
    rects: Dict[str, List[Tuple[float, float, float]]] = {}
    for name, spec in ports.items():
        axis = spec["axis"]
        coord = spec["coord"]
        u0, u1 = spec["u_range"]
        v0, v1 = spec["v_range"]

        if axis == 0:      # нормаль по X -> плоскость грани в Y,Z при X=coord
            rects[name] = [
                (coord, u0, v0),
                (coord, u1, v0),
                (coord, u1, v1),
                (coord, u0, v1),
            ]
        elif axis == 1:    # нормаль по Y -> плоскость грани в X,Z при Y=coord
            rects[name] = [
                (u0, coord, v0),
                (u1, coord, v0),
                (u1, coord, v1),
                (u0, coord, v1),
            ]
        else:               # нормаль по Z (не используется в этой модели)
            rects[name] = [
                (u0, v0, coord),
                (u1, v0, coord),
                (u1, v1, coord),
                (u0, v1, coord),
            ]
    return rects


def bounding_box(p: TReactorParams) -> BoxSpec:
    """Габаритный параллелепипед всей сборки (тело + крышки), мм.

    Крышки теперь плоские (нулевой толщины) и лежат ровно в плоскости
    портов основного тела, поэтому габариты сборки совпадают с
    габаритами самого тела.
    """
    outline = t_shape_outline(p)
    xs = [x for x, _ in outline]
    ys = [y for _, y in outline]
    return (min(xs), max(xs), min(ys), max(ys), 0.0, p.h)