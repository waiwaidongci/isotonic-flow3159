from .aggregate import aggregate_readings
from .pava import weighted_pava
from .interpolate import predict

def leave_one_batch_out(levels, readings):
 """整批留一（LOBO）：每次留出同一制片批次的全部滤片，按剩余带批次滤片重新聚合流速与权重后重拟合。

 批次只来自读数显式记录的 production_batch；缺批次的读数不猜填、不分配任何批次，
 既不进入任何训练折也不进入留出评估，完全排除在本验证之外（覆盖数会明确标明）。
 剩余读数无法再聚合成至少两个不同流速的折标记为不可评估，不混入任何总误差。
 端点夹持照常计入可评估折并单独标记，不称外推。
 """
 labeled = [r for r in readings if r.get('production_batch')]
 batches = sorted({r['production_batch'] for r in labeled})
 if len(batches) < 2:
  return {'available': False, 'reason': '可识别制片批次不足两个，整批留一无法进行；缺批次读数不猜填',
          'batch_count': len(batches), 'batches': batches,
          'labeled_reading_count': len(labeled), 'unlabeled_reading_count': len(readings) - len(labeled),
          'folds': [], 'fit_count': 0, 'evaluable_fold_count': 0, 'unevaluable_fold_count': 0,
          'evaluable_reading_count': 0, 'sse': None, 'mse': None, 'interior_mse': None,
          'interior_reading_count': 0, 'clamped_folds': 0, 'clamped_reading_count': 0,
          'definition': 'Hold out every filter from one recorded production batch, re-aggregate flows and weights from the remaining labeled filters, and refit PAVA independently. Filters without a recorded batch are excluded from the whole validation (never assigned a batch, never used in training or scoring). Unevaluable folds (fewer than two distinct remaining flows) are excluded from every aggregate error.'}
 folds = []
 total_sse = 0.
 total_n = 0
 inside_sse = 0.
 inside_n = 0
 clamped_folds = 0
 clamped_readings = 0
 for batch in batches:
  held = [r for r in labeled if r['production_batch'] == batch]
  rest = [r for r in labeled if r['production_batch'] != batch]
  train_groups = aggregate_readings(levels, rest)
  if len(train_groups) < 2:
   folds.append({'omitted_batch': batch, 'evaluable': False,
                 'reason': '剩余滤片仅覆盖一个流速（或无剩余），无法重拟合非降曲线；本折不参与总误差',
                 'omitted_count': len(held), 'training_flows': [g['flow'] for g in train_groups],
                 'training_reading_count': len(rest), 'residuals': []})
   continue
  fit = weighted_pava([g['mean_pressure'] for g in train_groups], [g['count'] for g in train_groups])
  x = [g['flow'] for g in train_groups]
  held_groups = aggregate_readings(levels, held)
  residuals = []
  sse = 0.
  fold_clamped = None
  within_all = True
  for g in held_groups:
   pred = predict(x, fit['fitted'], g['flow'])
   if pred['clamped'] is not None:
    fold_clamped = pred['clamped']
    within_all = False
   for r in g['readings']:
    residual = r['pressure'] - pred['prediction']
    squared = residual ** 2
    residuals.append({'specimen_ref': r['specimen_ref'], 'flow': g['flow'],
                      'production_batch': batch, 'observed_pressure': r['pressure'],
                      'prediction': pred['prediction'], 'residual': residual,
                      'squared_error': squared, 'clamped': pred['clamped'],
                      'within_observed_domain': pred['within_observed_domain']})
    sse += squared
  n = len(residuals)
  total_sse += sse
  total_n += n
  if within_all:
   inside_sse += sse
   inside_n += n
  if fold_clamped is not None:
   clamped_folds += 1
   clamped_readings += n
  folds.append({'omitted_batch': batch, 'evaluable': True, 'reason': None,
                'omitted_count': n, 'omitted_flows': [g['flow'] for g in held_groups],
                'omitted_labels': sorted({label for g in held_groups for label in g['labels']}),
                'training_flows': x, 'training_reading_count': len(rest),
                'training_fitted': fit['fitted'], 'training_blocks': fit['blocks'],
                'clamped': fold_clamped, 'sse': sse, 'mse': sse / n, 'residuals': residuals})
 evaluable = [f for f in folds if f['evaluable']]
 return {'available': True,
         'reason': None if evaluable else '每个批次留出后剩余滤片都不足两个流速，全部折不可评估；不产生总误差',
         'batch_count': len(batches), 'batches': batches,
         'labeled_reading_count': len(labeled),
         'unlabeled_reading_count': len(readings) - len(labeled),
         'folds': folds, 'fit_count': len(evaluable),
         'evaluable_fold_count': len(evaluable),
         'unevaluable_fold_count': len(folds) - len(evaluable),
         'evaluable_reading_count': total_n,
         'sse': total_sse if evaluable else None,
         'mse': total_sse / total_n if evaluable else None,
         'interior_mse': inside_sse / inside_n if inside_n else None,
         'interior_reading_count': inside_n,
         'clamped_folds': clamped_folds, 'clamped_reading_count': clamped_readings,
         'definition': 'Hold out every filter from one recorded production batch, re-aggregate flows and weights from the remaining labeled filters, and refit PAVA independently. Filters without a recorded batch are excluded from the whole validation (never assigned a batch, never used in training or scoring). Per-filter errors are pooled over original independent filters (not averaged per fold). Endpoint clamps are included and marked; folds that cannot rebuild at least two distinct flows are reported unevaluable and excluded from every aggregate error. No extrapolation or confidence interval.'}
