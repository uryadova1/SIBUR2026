import pyvista as pv

# Open and load the VTK file
path = '\code\\analysis\VTK_case1\VTK_case1'
mesh = pv.read('D:\мага\технохак 2026\sibur\code\\analysis\VTK_case1\VTK_case1\OF8_droplet_flowfocusing_x20_0.vtk')

# Print basic properties (points, cells, active scalars)
print(mesh)

# Extract a specific data array by name
data_array = mesh.point_data['alpha.dispersed']
print(data_array)

# Instantly visualize the data in an interactive 3D window
mesh.plot()

import pyvista as pv
import numpy as np
from scipy import ndimage
from skimage.measure import regionprops

# Загрузка VTK (предположим, это структурированная сетка)
mesh = pv.read("result.vtk")
alpha = mesh.point_data["alpha"]  # 1D массив значений

# Если сетка неструктурированная, получим координаты и интерполируем
# Но проще, если у вас есть регулярная сетка, тогда:
# допустим, mesh.dimensions = (nx, ny, 1)
grid = mesh.cast_to_unstructured_grid()  # или оставить как есть
# Преобразуем в 2D массив (если сетка регулярная):
nx, ny = mesh.dimensions[:2]  # если у вас 2D срез
alpha_2d = alpha.reshape((ny, nx), order='F')  # порядок зависит от формата

# Бинаризация
thresh = 0.5
mask = alpha_2d > thresh

# Сегментация
labeled, num_features = ndimage.label(mask)

# Анализ каждой капли
props = regionprops(labeled, intensity_image=alpha_2d)
# площадь пикселя (предположим, что сетка равномерная с шагом dx, dy)
dx = ...  # получите из геометрии
dy = ...
pixel_area = dx * dy

diameters = []
for prop in props:
    area = prop.area * pixel_area
    diam = np.sqrt(4 * area / np.pi)
    diameters.append(diam)

print(f"Средний диаметр: {np.mean(diameters):.3f}")


from pathlib import Path
import sys



if __name__ == "__main__":
    parent_dir = Path(__file__).resolve().parents[3]
    dir_name = "\CO2_fine_mesh_correct_vel"
    path = str(parent_dir) + dir_name
    print(path)
