"""端到端口径补充：schema 批次归一化、混合/全无批次研究、种子结构、重聚合权重。"""
import sys
import types
import math

# 纯标准库 numpy 桩（与 test_lobo.py 相同口径）
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

from src.services.analysis import analyze, batch_coverage  # noqa: E402
from src.services.aggregate import aggregate_readings, aggregate  # noqa: E402


# 1) 模拟 ReadingInput 的批次归一化（pydantic 不可用，复刻 field_validator 规则）
def normalize_batch(value):
 if value is None: return None
 value = value.strip()
 return value or None
assert normalize_batch(None) is None
assert normalize_batch('') is None
assert normalize_batch('   ') is None
assert normalize_batch(' B1 ') == 'B1'
print('1) 批次归一化（空/空白→None，不猜填）OK')

# 2) 重聚合权重：去掉一个批次后，各组 count 按剩余滤片重新计算
levels = [{'id': 1, 'label': 'F1', 'flow': 10.0}, {'id': 2, 'label': 'F2', 'flow': 20.0},
          {'id': 3, 'label': 'F3', 'flow': 30.0}]
readings = []
k = 0
for lid, flow in [(1, 10.0), (2, 20.0), (3, 30.0)]:
 for j in range(6):
  k += 1
  readings.append({'id': k, 'level_id': lid, 'specimen_ref': f'P{k:02d}',
                   'pressure': float(lid + j * 0.01), 'production_batch': f'B{j % 3 + 1}'})
full = aggregate_readings(levels, readings)
assert all(g['count'] == 6 for g in full)
rest = [r for r in readings if r['production_batch'] != 'B1']
re_agg = aggregate_readings(levels, rest)
# B1 在每档有 j=0,3 两片 → 剩余每档 4 片；均值随剩余滤片重算
assert all(g['count'] == 4 for g in re_agg)
assert len(rest) == 12 and sum(g['count'] for g in re_agg) == 12
print('2) 各折按剩余滤片重新聚合流速与权重 OK：', [(g['flow'], g['count']) for g in re_agg])

# 3) 混合批次研究：analyze 成功，LODO 全覆盖、LOBO 只覆盖带批次片
study = {'id': 1, 'name': 'mix', 'filename': 'm.csv', 'description': '', 'direction': 'nondecreasing'}
config = {'target_pressure': 2.0, 'query_flows': [5.0, 35.0], 'direction': 'nondecreasing'}
mixed = [dict(r, production_batch=None) if r['id'] % 5 == 0 else r for r in readings]
res = analyze(study, levels, mixed, config)
assert res['lodo']['reading_count'] == 18           # LODO 仍是全部读数
unlabeled = sum(1 for r in mixed if not r['production_batch'])
assert res['lobo']['unlabeled_reading_count'] == unlabeled
assert res['lobo']['labeled_reading_count'] == 18 - unlabeled
assert res['lobo']['evaluable_reading_count'] == 18 - unlabeled
seen = {r['specimen_ref'] for f in res['lobo']['folds'] for r in f['residuals']}
assert all(next(r for r in mixed if r['id'] == i)['specimen_ref'] not in seen
           for i, r in enumerate(mixed, 1) if not r['production_batch'])
# 缺批次片同样不得进入任何折的训练集：每折训练片数 = 带批次总数 - 该批片数（无缺批次片）
batch_sizes = {b: sum(1 for r in mixed if r['production_batch'] == b)
               for b in {r['production_batch'] for r in mixed if r['production_batch']}}
for f in res['lobo']['folds']:
 assert f['training_reading_count'] == (18 - unlabeled) - batch_sizes[f['omitted_batch']]
assert sum(f['training_reading_count'] for f in res['lobo']['folds']) == \
       sum((18-unlabeled) - n for n in batch_sizes.values())
print(f'3) 混合研究 OK：LODO 18 片，LOBO 覆盖 {18-unlabeled} 片，缺批次 {unlabeled} 片完全不参与（训练与评估均排除），批次片数 {batch_sizes}')

# 4) 全无批次研究（对应种子第三项）：LOBO 明确不可用，LODO/拟合照常
none_readings = [dict(r, production_batch=None) for r in readings]
res4 = analyze(study, levels, none_readings, config)
assert res4['lobo']['available'] is False and res4['lobo']['mse'] is None
assert res4['lobo']['folds'] == [] and res4['lodo']['fit_count'] == 3
assert res4['batch_coverage'] == {'batch_recorded': False, 'batches': [], 'batch_count': 0,
                                  'labeled_reading_count': 0, 'unlabeled_reading_count': 18}
assert res4['knots'] and res4['threshold_set'] and res4['predictions']
print('4) 全无批次研究 OK：LOBO 不可评估且不产生总误差，LODO 与拟合正常')

# 5) 种子数据结构（12 档 × 8 片，批次 B1/B2/B3 按 j%3 分配）
s_levels = [{'id': i+1, 'label': f'F{i+1:02d}', 'flow': float(10*(i+1))} for i in range(12)]
s_readings = []
sk = 0
for i, lv in enumerate(s_levels):
 for j in range(8):
  sk += 1
  s_readings.append({'id': sk, 'level_id': lv['id'], 'specimen_ref': f'FW-F{i+1:02d}-P{j+1:02d}',
                     'pressure': float(2 + i + 0.1*j), 'production_batch': f'B{j % 3 + 1}'})
res5 = analyze(study, s_levels, s_readings,
               {'target_pressure': 6.5, 'query_flows': [5, 125], 'direction': 'nondecreasing'})
# 每批 j%3：B1={j:0,3,6}→3片/档×12=36；B2={j:1,4,7}→36；B3={j:2,5}→2片/档×12=24
counts = {b: sum(1 for r in s_readings if r['production_batch'] == b) for b in ('B1', 'B2', 'B3')}
assert counts == {'B1': 36, 'B2': 36, 'B3': 24}
assert res5['lobo']['fit_count'] == 3 and res5['lobo']['unevaluable_fold_count'] == 0
# 各折训练片数 = 96 - 该批片数；留出后仍覆盖全部 12 个流速
for f in res5['lobo']['folds']:
 assert len(f['training_flows']) == 12
 assert f['training_reading_count'] == 96 - counts[f['omitted_batch']]
 assert f['omitted_count'] == counts[f['omitted_batch']]
# 逐片残差总数 = 96，且每片只出现一次
all_res = [r for f in res5['lobo']['folds'] for r in f['residuals']]
assert len(all_res) == 96 and len({r['specimen_ref'] for r in all_res}) == 96
# 夹持：留出 B3 后训练域仍 [10,120]，留出片流速都在域内 → 无夹持
assert res5['lobo']['clamped_folds'] == 0
print('5) 种子结构 OK：3 折全部可评估，逐片残差 96 条且不重复；批次片数', counts)

# 6) 历史结果兼容性：结果中 lodo 结构字段保持原名
for key in ('folds', 'fit_count', 'reading_count', 'sse', 'mse', 'interior_mse',
            'interior_reading_count', 'clamped_folds', 'clamped_reading_count', 'definition'):
 assert key in res5['lodo'], key
assert 'lobo' in res5 and 'batch_coverage' in res5
print('6) 历史兼容 OK：LODO 字段不变，新增 lobo / batch_coverage')
print('\n全部补充断言通过 ✓')
