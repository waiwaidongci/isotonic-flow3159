import {Table} from './common/Table';
import {fmt} from '../utils/format';

export function LoboTable({result}:{result:any}){
 const lobo=result.lobo;
 const coverage=result.batch_coverage;
 if(!lobo||!lobo.available){
  return <section className="ledger-section">
   <div className="section-head"><h2>整批留一 LOBO：当前不可评估</h2><span>缺批次不猜填</span></div>
   <p>{lobo?.reason||'历史结果未包含整批留一验证。'}</p>
   <p className="coverage-line">已记录批次 {coverage?.batch_count??0} 个 / 带批次滤片 {coverage?.labeled_reading_count??0} 片 / 缺批次滤片 {coverage?.unlabeled_reading_count??0} 片。
   缺批次滤片只参与整档留一（LODO）与全量拟合，不分配任何批次，也不进入 LOBO 的训练折或留出误差。</p>
  </section>;
 }
 return <section className="ledger-section">
  <div className="section-head">
   <h2>整批留一，再重新聚合重拟合。</h2>
   <span>{lobo.evaluable_fold_count} 次真实重拟合 / {lobo.batch_count} 个制片批次 / {lobo.evaluable_reading_count} 片带批次滤片</span>
  </div>
  <p>同一制片批次的全部滤片一起留出（批次跨流速档分布），各折只用剩余滤片重新聚合流速均值与独立滤片权重后再跑 PAVA。
  总MSE = 可评估折全部原始滤片平方误差之和 / 可评估滤片总数；不可评估折与缺批次滤片一律不混入。</p>
  <p className="coverage-line">覆盖：批次 {lobo.batches.join(' / ')}；带批次 {lobo.labeled_reading_count} 片，缺批次 {lobo.unlabeled_reading_count} 片（缺批次不猜填、不参与本验证）。</p>
  <Table headers={['留出制片批次','留出片数 / 训练片数','本批原始MSE','训练流速数','预测边界','可评估性']}>
   {lobo.folds.map((f:any)=>
    <tr key={f.omitted_batch} className={f.evaluable?'':'unevaluable-row'}>
     <td>{f.omitted_batch}{f.evaluable&&f.omitted_labels&&f.omitted_labels.length>0&&<small>{f.omitted_labels.join(' / ')}</small>}</td>
     <td>{f.omitted_count} / {f.training_reading_count}</td>
     <td>{f.evaluable?fmt(f.mse,6):'—'}</td>
     <td>{f.training_flows.length}</td>
     <td className={f.clamped?'brass':''}>{!f.evaluable?'—':f.clamped==='left'?'左端点夹持':f.clamped==='right'?'右端点夹持':'训练域内插值'}</td>
     <td>{f.evaluable?'可评估':<span className="error-text">不可评估<small>{f.reason}</small></span>}</td>
    </tr>)}
  </Table>
  <p>可评估 {lobo.evaluable_fold_count} 折 / 不可评估 {lobo.unevaluable_fold_count} 折；夹持 {lobo.clamped_folds} 折 / {lobo.clamped_reading_count} 片；
  域内滤片 MSE {fmt(lobo.interior_mse,6)}（{lobo.interior_reading_count} 片）。端点夹持计入可评估折总MSE并单独标记，不构成外推验证。</p>
  <details>
   <summary>查看逐滤片残差与各折训练节点（仅可评估折）</summary>
   {lobo.folds.filter((f:any)=>f.evaluable).map((f:any)=>
    <div className="fold-detail" key={f.omitted_batch}>
     <strong>留出批次 {f.omitted_batch} / 训练流速 {f.training_flows.map(v=>fmt(v)).join(', ')}</strong>
     <p>{f.residuals.map((r:any)=>`${r.specimen_ref}@${fmt(r.flow)}: ${fmt(r.residual,5)}${r.clamped?`（${r.clamped==='left'?'左夹持':'右夹持'}）`:''}`).join('　/　')}</p>
    </div>)}
  </details>
 </section>;
}
