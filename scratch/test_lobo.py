"""LOBO/LODO 数值口径自检：不依赖数据库，直接跑服务层。

本机无 numpy，注入纯标准库等价桩（仅实现 pava.py 使用的接口），
PAVA 算法本体与生产代码同一份，仅底层数组运算被替换。
"""
import sys
import types

_np = types.ModuleType('numpy')
class _Arr(list):
 @property
 def ndim(self):
  return 1
 @property
 def shape(self):
  return (len(self),)
 def __mul__(self, other):
  if isinstance(other, _Arr):
   return _Arr(a * b for a, b in zip(self, other))
  return _Arr(v * other for v in self)
 def __pow__(self, p):
  return _Arr(v ** p for v in self)
 def __sub__(self, other):
  return _Arr(a - b for a, b in zip(self, other))
 def __getitem__(self, item):
  if isinstance(item, slice):
   return _Arr(list.__getitem__(self, item))
  return list.__getitem__(self, item)
 def __setitem__(self, item, value):
  if isinstance(item, slice):
   vals = list(self)[item]
   for i, _ in enumerate(vals):
    list.__setitem__(self, item.start + i, value)
  else:
   list.__setitem__(self, item, value)
 def tolist(self):
  return list(self)
 def all(self):
  return all(self)
 def any(self):
  return any(self)
 def __le__(self, other):
  return _Arr(v <= other for v in self)
 def __lt__(self, other):
  return _Arr(v < other for v in self)
def _asarray(values, dtype=None):
 return _Arr(values)
def _isfinite(values):
 import math
 return _Arr(math.isfinite(v) for v in values)
def _sum(values):
 return math.fsum(values)
_np.asarray = _asarray
_np.isfinite = _isfinite
_np.sum = _sum
_np.longdouble = float
_np.empty = lambda n, dtype=None: _Arr(0.0 for _ in range(n))
sys.modules['numpy'] = _np

sys.path.insert(0, '/workspace/backend')
import math  # noqa: E402

from src.services.analysis import analyze  # noqa: E402
from src.services.lobo import leave_one_batch_out  # noqa: E402

# 构造：4 个流速档，每档 4 片，3 个批次（每批在每档 1-2 片），批次跨档分布
levels = [{'id': 1, 'label': 'F1', 'flow': 10.0},
          {'id': 2, 'label': 'F2', 'flow': 20.0},
          {'id': 3, 'label': 'F3', 'flow': 30.0},
          {'id': 4, 'label': 'F4', 'flow': 40.0}]
# pressure 随 flow 非降；批次 B1/B2/B3
readings = []
ref = 0
base = {10: 2.0, 20: 4.0, 30: 6.0, 40: 8.0}
for lid, flow in [(1, 10.0), (2, 20.0), (3, 30.0), (4, 40.0)]:
    for j in range(4):
        ref += 1
        readings.append({'id': ref, 'study_id': 1, 'level_id': lid,
                         'specimen_ref': f'P{ref:02d}', 'pressure': base[flow] + 0.1 * j,
                         'measurement_note': '', 'production_batch': f'B{j % 3 + 1}'})

study = {'id': 1, 'name': 't', 'filename': 't.csv', 'description': '', 'direction': 'nondecreasing'}
config = {'target_pressure': 5.0, 'query_flows': [5.0, 25.0, 45.0], 'direction': 'nondecreasing'}

result = analyze(study, levels, readings, config)
lobo = result['lobo']
print('=== 正常 3 批次 LOBO ===')
print('available:', lobo['available'], 'batches:', lobo['batches'])
print('folds:', lobo['fit_count'], 'evaluable:', lobo['evaluable_fold_count'],
      'unevaluable:', lobo['unevaluable_fold_count'])
print('labeled/unlabeled:', lobo['labeled_reading_count'], lobo['unlabeled_reading_count'])
print('mse:', lobo['mse'], 'interior_mse:', lobo['interior_mse'])
print('clamped folds/readings:', lobo['clamped_folds'], lobo['clamped_reading_count'])
assert lobo['available'] and lobo['fit_count'] == 3
assert lobo['evaluable_reading_count'] == 16
# 汇总口径：总 SSE / 总片数，而非折 MSE 平均
manual_sse = sum(r['squared_error'] for f in lobo['folds'] for r in f['residuals'])
assert abs(manual_sse / 16 - lobo['mse']) < 1e-12
# 每折残差逐片且带夹持标记
for f in lobo['folds']:
    assert f['evaluable'] and len(f['residuals']) == f['omitted_count']
    assert all(r['production_batch'] == f['omitted_batch'] for r in f['residuals'])
# 留出 B1 后训练读数 = 16 - B1 的片数（B1: j=0,3 -> 每档2片 × 4档 = 8? j%3: j=0→B1,3→B1 → 每档2片）
b1 = next(f for f in lobo['folds'] if f['omitted_batch'] == 'B1')
assert b1['training_reading_count'] == 16 - 8 and len(b1['training_flows']) == 4
# 训练折重新聚合：4 档仍在，每档剩 2 片
print('B1 fold training flows:', b1['training_flows'], 'training n:', b1['training_reading_count'])

# --- 场景 2：缺批次读数不猜填，仍可做 LOBO，未标注片被排除 ---
readings_mix = [dict(r) for r in readings]
readings_mix[0]['production_batch'] = None  # 一片无批次
lobo2 = leave_one_batch_out(levels, readings_mix)
print('\n=== 含 1 片缺批次 ===')
print('labeled/unlabeled:', lobo2['labeled_reading_count'], lobo2['unlabeled_reading_count'])
assert lobo2['unlabeled_reading_count'] == 1 and lobo2['labeled_reading_count'] == 15
assert lobo2['evaluable_reading_count'] == 15
# 无批次片不出现在任何留出折残差里
seen = {r['specimen_ref'] for f in lobo2['folds'] for r in f['residuals']}
assert 'P01' not in seen

# --- 场景 3：全部缺批次 → 不可用，不产生总误差 ---
readings_none = [dict(r, production_batch=None) for r in readings]
lobo3 = leave_one_batch_out(levels, readings_none)
print('\n=== 全部缺批次 ===')
print('available:', lobo3['available'], 'reason:', lobo3['reason'], 'mse:', lobo3['mse'])
assert lobo3['available'] is False and lobo3['mse'] is None and lobo3['folds'] == []

# --- 场景 4：单批次 → 不可用 ---
readings_one = [dict(r, production_batch='BX') for r in readings]
lobo4 = leave_one_batch_out(levels, readings_one)
assert lobo4['available'] is False and lobo4['batch_count'] == 1
print('\n=== 单批次 ===  reason:', lobo4['reason'])

# --- 场景 5：某批次留出后只剩一个流速 → 该折不可评估，不混入总误差 ---
# B2 只占据最高流速 40 档；留出 B2 后 B1 仍覆盖 4 档（可评估），
# 留出 B1 后只剩 40 一个流速（不可评估）。
readings5 = []
k = 0
for lid, flow in [(1, 10.0), (2, 20.0), (3, 30.0), (4, 40.0)]:
    for j in range(3):  # B1 覆盖全部四档
        k += 1
        readings5.append({'id': k, 'study_id': 1, 'level_id': lid, 'specimen_ref': f'Q{k:02d}',
                          'pressure': base[flow], 'measurement_note': '',
                          'production_batch': 'B1'})
for j in range(2):  # B2 仅最高档
    k += 1
    readings5.append({'id': k, 'study_id': 1, 'level_id': 4, 'specimen_ref': f'Q{k:02d}',
                      'pressure': 8.0, 'measurement_note': '', 'production_batch': 'B2'})
lobo5 = leave_one_batch_out(levels, readings5)
print('\n=== 单档批次留出后剩余一流速：该折不可评估 ===')
for f in lobo5['folds']:
    print(f['omitted_batch'], 'evaluable:', f['evaluable'], '| train flows:',
          f['training_flows'], '|', f['reason'])
assert lobo5['available'] is True
assert lobo5['unevaluable_fold_count'] == 1 and lobo5['evaluable_fold_count'] == 1
# 总误差只含可评估的 B2 折；B1 折的片不进总误差
b1f5 = next(f for f in lobo5['folds'] if f['omitted_batch'] == 'B1')
b2f5 = next(f for f in lobo5['folds'] if f['omitted_batch'] == 'B2')
assert not b1f5['evaluable'] and b1f5['residuals'] == []
assert b2f5['evaluable']
assert lobo5['evaluable_reading_count'] == b2f5['omitted_count'] == 2
assert abs(lobo5['mse'] - b2f5['mse']) < 1e-12

# --- 场景 6：部分折不可评估，可评估折仍汇总 ---
# B1 全档分布（4档各2片），B2 只在 10/20；留出 B1 后剩 10/20 两档可拟合；留出 B2 后剩 4 档
readings6 = []
k = 0
for lid, flow in [(1, 10.0), (2, 20.0), (3, 30.0), (4, 40.0)]:
    for j in range(2):  # B1 每档
        k += 1
        readings6.append({'id': k, 'study_id': 1, 'level_id': lid, 'specimen_ref': f'R{k:02d}',
                          'pressure': base[flow], 'measurement_note': '', 'production_batch': 'B1'})
for lid, flow in [(1, 10.0), (2, 20.0)]:
    for j in range(2):  # B2 仅低两档
        k += 1
        readings6.append({'id': k, 'study_id': 1, 'level_id': lid, 'specimen_ref': f'R{k:02d}',
                          'pressure': base[flow], 'measurement_note': '', 'production_batch': 'B2'})
lobo6 = leave_one_batch_out(levels, readings6)
print('\n=== 部分不可评估 ===')
for f in lobo6['folds']:
    print(f['omitted_batch'], 'evaluable:', f['evaluable'], 'train flows:', f['training_flows'])
assert lobo6['evaluable_fold_count'] == 2 and lobo6['unevaluable_fold_count'] == 0
# 留出 B2：剩余 B1 覆盖 4 档；留出 B1：剩余 B2 覆盖 2 档 → 仍可拟合
b1f = next(f for f in lobo6['folds'] if f['omitted_batch'] == 'B1')
assert b1f['evaluable'] and b1f['training_flows'] == [10.0, 20.0]
assert lobo6['mse'] is not None

# --- 场景 7：端点夹持标记 ---
# B1 覆盖 10/20/30（不覆盖 40），B3 独占最高流速 40 档：
# 留出 B3 后训练域为 [10,30]，预测 40 触发右端点夹持。
readings7 = []
k = 0
for lid, flow in [(1, 10.0), (2, 20.0), (3, 30.0)]:
    for j in range(2):
        k += 1
        readings7.append({'id': k, 'study_id': 1, 'level_id': lid, 'specimen_ref': f'S{k:02d}',
                          'pressure': base[flow], 'measurement_note': '', 'production_batch': 'B1'})
for j in range(2):  # B3 仅最高档
    k += 1
    readings7.append({'id': k, 'study_id': 1, 'level_id': 4, 'specimen_ref': f'S{k:02d}',
                      'pressure': 8.0, 'measurement_note': '', 'production_batch': 'B3'})
lobo7 = leave_one_batch_out(levels, readings7)
b3 = next(f for f in lobo7['folds'] if f['omitted_batch'] == 'B3')
print('\n=== 端点夹持 ===  B3 clamp:', b3['clamped'],
      'within domain flags:', {r['within_observed_domain'] for r in b3['residuals']})
assert b3['clamped'] == 'right'
assert all(r['clamped'] == 'right' for r in b3['residuals'])
assert lobo7['clamped_folds'] >= 1 and lobo7['clamped_reading_count'] >= 2
# 留出 B1 后仅剩 40 一个流速 → 不可评估，且夹持统计不被污染
b1f7 = next(f for f in lobo7['folds'] if f['omitted_batch'] == 'B1')
assert not b1f7['evaluable']
assert lobo7['evaluable_reading_count'] == 2

# --- 场景 8：历史结果兼容 —— LODO 仍在且结构不变 ---
print('\n=== LODO 兼容 ===')
print('lodo mse:', result['lodo']['mse'], 'folds:', result['lodo']['fit_count'])
assert result['lodo']['fit_count'] == 4 and 'interior_mse' in result['lodo']
print('batch_coverage:', result['batch_coverage'])
assert result['batch_coverage'] == {'batch_recorded': True, 'batches': ['B1', 'B2', 'B3'],
                                    'batch_count': 3, 'labeled_reading_count': 16,
                                    'unlabeled_reading_count': 0}
print('\n全部断言通过 ✓')
