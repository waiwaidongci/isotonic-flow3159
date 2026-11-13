"""确定性回归：不依赖 numpy RNG。
1) aggregate() 重构后与原内联分组逻辑逐字段等价；
2) analyze 产出的 LODO 与独立内联实现完全一致（保护重构未改变历史口径）；
3) 同一份带批次数据同时产出结构正确的 LOBO。
"""
import sys, types, math
from collections import defaultdict
from math import fsum

_np = types.ModuleType('numpy')
class _Arr(list):
 ndim = property(lambda self: 1)
 shape = property(lambda self: (len(self),))
 def __mul__(self, o): return _Arr(a*b for a, b in zip(self, o)) if isinstance(o, _Arr) else _Arr(v*o for v in self)
 def __sub__(self, o): return _Arr(a-b for a, b in zip(self, o))
 def __pow__(self, p): return _Arr(v**p for v in self)
 def __getitem__(self, i): return _Arr(list.__getitem__(self, i)) if isinstance(i, slice) else list.__getitem__(self, i)
 def __setitem__(self, i, v):
  if isinstance(i, slice):
   for k, _ in enumerate(list(self)[i]): list.__setitem__(self, i.start+k, v)
  else: list.__setitem__(self, i, v)
 def tolist(self): return list(self)
 def all(self): return all(self)
 def any(self): return any(self)
 def __le__(self, o): return _Arr(v <= o for v in self)
_np.asarray = lambda values, dtype=None: _Arr(values)
_np.isfinite = lambda v: _Arr(math.isfinite(x) for x in v)
_np.sum = lambda v: math.fsum(v)
_np.longdouble = float
_np.empty = lambda n, dtype=None: _Arr(0.0 for _ in range(n))
sys.modules['numpy'] = _np
sys.path.insert(0, '/workspace/backend')

from src.services.analysis import analyze  # noqa: E402
from src.services.aggregate import aggregate, aggregate_readings  # noqa: E402
from src.services.pava import weighted_pava  # noqa: E402
from src.services.interpolate import predict  # noqa: E402

# 确定性数据：4 档，含同流速合并（两个命名档同为 20），每档 3 片，批次跨档
levels = [{'id': 1, 'label': 'F1', 'flow': 10.0}, {'id': 2, 'label': 'F2a', 'flow': 20.0},
          {'id': 3, 'label': 'F2b', 'flow': 20.0}, {'id': 4, 'label': 'F3', 'flow': 30.0}]
raw = [(1, 10.0, 2.0, 'B1'), (1, 10.0, 2.4, 'B2'), (1, 10.0, 1.8, 'B3'),
       (2, 20.0, 4.1, 'B1'), (2, 20.0, 3.9, 'B2'), (2, 20.0, 4.0, 'B3'),
       (3, 20.0, 4.2, 'B1'), (3, 20.0, 3.8, 'B2'),
       (4, 30.0, 6.0, 'B1'), (4, 30.0, 5.8, 'B2'), (4, 30.0, 6.2, 'B3')]
readings = [{'id': i+1, 'level_id': lid, 'specimen_ref': f'P{i+1:02d}', 'pressure': p,
             'production_batch': b} for i, (lid, _, p, b) in enumerate(raw)]
study = {'id': 1, 'name': 'reg', 'filename': 'r.csv', 'description': '', 'direction': 'nondecreasing'}
config = {'target_pressure': 4.0, 'query_flows': [5.0, 25.0, 35.0], 'direction': 'nondecreasing'}

# 1) 与重构前内联聚合逐字段对照（直接复刻旧 aggregate 函数体）
lookup = {l['id']: l for l in levels}
grouped = defaultdict(list)
for r in sorted(readings, key=lambda z: z['specimen_ref']):
 grouped[lookup[r['level_id']]['flow']].append(r)
old_groups = []
for flow, items in sorted(grouped.items()):
 ids = {r['level_id'] for r in items}
 old_groups.append({'flow': float(flow), 'mean_pressure': fsum(r['pressure'] for r in items)/len(items),
                    'count': len(items), 'level_ids': sorted(ids),
                    'labels': sorted(lookup[i]['label'] for i in ids), 'readings': items})
new_groups = aggregate(levels, readings)
assert len(old_groups) == len(new_groups) == 3  # 20 的两档合并
for a, b in zip(old_groups, new_groups):
 assert a['flow'] == b['flow'] and a['count'] == b['count']
 assert abs(a['mean_pressure'] - b['mean_pressure']) < 1e-15
 assert a['level_ids'] == b['level_ids'] and a['labels'] == b['labels']
 assert [r['specimen_ref'] for r in a['readings']] == [r['specimen_ref'] for r in b['readings']]
print('1) 聚合重构等价 OK（同流速 20 的 F2a/F2b 合并为 1 组，权重 5）')

# 2) 独立内联 LODO，与 analyze().lodo 逐折对照
def inline_lodo(groups):
 folds = []
 total_sse = 0.0; total_n = 0
 for omitted, g in enumerate(groups):
  train = [r for i, r in enumerate(groups) if i != omitted]
  fit = weighted_pava([r['mean_pressure'] for r in train], [r['count'] for r in train])
  xx = [r['flow'] for r in train]
  pred = predict(xx, fit['fitted'], g['flow'])
  sse = fsum((r['pressure'] - pred['prediction'])**2 for r in g['readings'])
  n = len(g['readings']); total_sse += sse; total_n += n
  folds.append({'flow': g['flow'], 'sse': sse, 'n': n, 'clamped': pred['clamped']})
 return total_sse / total_n, folds

res = analyze(study, levels, readings, config)
exp_mse, exp_folds = inline_lodo(new_groups)
assert abs(res['lodo']['mse'] - exp_mse) < 1e-15
assert res['lodo']['fit_count'] == len(exp_folds) == 3
for f, e in zip(res['lodo']['folds'], exp_folds):
 assert f['omitted_flow'] == e['flow'] and abs(f['sse'] - e['sse']) < 1e-15
 assert f['omitted_count'] == e['n'] and f['clamped'] == e['clamped']
# 端点折：留出 10 档 → 左夹持；留出 30 档 → 右夹持
assert res['lodo']['folds'][0]['clamped'] == 'left'
assert res['lodo']['folds'][-1]['clamped'] == 'right'
assert res['lodo']['clamped_folds'] == 2
print('2) LODO 与独立实现逐折一致 OK：总MSE =', round(res['lodo']['mse'], 9),
      '| 夹持折', res['lodo']['clamped_folds'])

# 3) 同数据 LOBO：3 批，F2b 无 B3 → 留出 B3 后 20 档仍有 F2a 两片，三流速齐全
lobo = res['lobo']
assert lobo['available'] and lobo['fit_count'] == 3 and lobo['unevaluable_fold_count'] == 0
# 手工核对 B3 折：B3 为 P3/P6/P11 共 3 片（F2b 本就无 B3），训练 11-3=8 片
b3 = next(f for f in lobo['folds'] if f['omitted_batch'] == 'B3')
assert b3['training_reading_count'] == 8 and b3['omitted_count'] == 3
assert len(b3['training_flows']) == 3  # 20 档靠 F2a 的 B1/B2 两片仍在
# 逐片残差覆盖全部 11 片且不重复（B1=4、B2=4、B3=3）
all_refs = [r['specimen_ref'] for f in lobo['folds'] for r in f['residuals']]
assert sorted(all_refs) == sorted(r['specimen_ref'] for r in readings)
print('3) LOBO 结构 OK：3 折全可评估，B3 折训练 8 片仍覆盖 3 流速；11 片逐片残差无重复')
print('\n确定性回归全部通过 ✓')
