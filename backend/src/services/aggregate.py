from collections import defaultdict
from math import fsum
from .validation import validate_source

def aggregate_readings(levels, readings):
 """按流速把给定读数聚合成组：同流速的命名档合并，权重为独立滤片数。"""
 lookup = {l['id']: l for l in levels}
 grouped = defaultdict(list)
 for r in sorted(readings, key=lambda x: x['specimen_ref']):
  grouped[lookup[r['level_id']]['flow']].append(r)
 groups = []
 for flow, items in sorted(grouped.items()):
  ids = {r['level_id'] for r in items}
  groups.append({'flow': float(flow), 'mean_pressure': fsum(r['pressure'] for r in items) / len(items),
                 'count': len(items), 'level_ids': sorted(ids),
                 'labels': sorted(lookup[i]['label'] for i in ids), 'readings': items})
 return groups

def aggregate(levels, readings):
 validate_source(levels, readings)
 return aggregate_readings(levels, readings)
