from fastapi import HTTPException
from src.models import ValidationNote
from src.utils.csv_export import csv_response
from src.services.audit import record

def export_note(db, id, actor):
 note = db.get(ValidationNote, id)
 if not note:
  raise HTTPException(404, '说明不存在')
 if note.status != 'approved':
  raise HTTPException(409, '仅批准说明可导出')
 result = note.result_snapshot
 target = result['threshold_set']
 lobo = result.get('lobo') or {}
 lobo_mse = lobo.get('mse')
 rows = [[note.name, result['source_study']['name'], result['fingerprint'], k['flow'], k['count'],
          k['mean_pressure'], k['fitted_pressure'], result['lodo']['mse'],
          '' if lobo_mse is None else lobo_mse, lobo.get('evaluable_fold_count', ''),
          lobo.get('unevaluable_fold_count', ''), lobo.get('clamped_reading_count', ''),
          target['target_pressure'], target['kind'], target['lower_flow'], target['upper_flow'],
          note.proposed_flow, note.interpretation, note.next_step, note.review_note]
         for k in result['knots']]
 record(db, actor, 'note.exported', {'note_id': id})
 return csv_response(f'flow-validation-{id}.csv', rows,
                     ['复验说明', '研究', '输入指纹', '流速mL/min', '独立滤片数', '均压差kPa', '拟合压差kPa',
                      '整档留一LODO_MSE', '整批留一LOBO_MSE', 'LOBO可评估折数', 'LOBO不可评估折数',
                      'LOBO夹持滤片数', '目标压差', '逆集合类型', '逆集合下限', '逆集合上限',
                      '计划新流速', '人工解释', '下一步', '审核意见'])
