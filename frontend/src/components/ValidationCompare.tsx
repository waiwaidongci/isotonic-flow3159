import {fmt} from '../utils/format';

function Cell({label, children, tone}:{label:string;children:React.ReactNode;tone?:'muted'|'brass'}){
 return <div className={`compare-cell${tone==='muted'?' is-muted':tone==='brass'?' is-brass':''}`}>
  <dt>{label}</dt><dd>{children}</dd>
 </div>;
}

export function ValidationCompare({result}:{result:any}){
 const lodo=result.lodo;
 const lobo=result.lobo;
 const coverage=result.batch_coverage;
 const legacy=!lobo;
 return <section className="ledger-section validation-compare">
  <div className="section-head">
   <h2>两种留出验证并排核对</h2>
   <span>覆盖范围不同，误差不可互相替代</span>
  </div>
  <p>整档留一（LODO）按流速留出，同制片批次的滤片仍会留在训练集，误差偏乐观；
  整批留一（LOBO）按制片批次留出，更接近新批次的泛化误差。两者总MSE都按原始独立滤片汇总，不按折简单平均。</p>
  <dl className="compare-grid">
   <div className="compare-column">
    <h3>整档留一 LODO（按流速）</h3>
    <Cell label="重拟合折数 / 覆盖滤片">{lodo.fit_count} 折 / {lodo.reading_count} 片（全部读数）</Cell>
    <Cell label="总 MSE（kPa²）" tone="brass">{fmt(lodo.mse,6)}</Cell>
    <Cell label="域内 MSE / 滤片数">{fmt(lodo.interior_mse,6)} / {lodo.interior_reading_count} 片</Cell>
    <Cell label="端点夹持">{lodo.clamped_folds} 折 / {lodo.clamped_reading_count} 片（计入并标记）</Cell>
    <Cell label="已知局限" tone="muted">同批滤片跨档时仍参与训练，预测误差偏乐观</Cell>
   </div>
   <div className="compare-column">
    <h3>整批留一 LOBO（按制片批次）</h3>
    {legacy?<>
      <Cell label="状态" tone="muted">历史结果：未记录批次，未运行</Cell>
      <Cell label="总 MSE（kPa²）" tone="muted">—</Cell>
      <Cell label="覆盖" tone="muted">重新运行含批次数据后生成；缺批次不猜填</Cell>
     </>:!lobo.available?<>
      <Cell label="状态" tone="muted">不可评估</Cell>
      <Cell label="总 MSE（kPa²）" tone="muted">—（不混入总误差）</Cell>
      <Cell label="原因" tone="muted">{lobo.reason}</Cell>
      <Cell label="覆盖" tone="muted">{coverage.batch_count} 批次 / {coverage.labeled_reading_count} 带批次片 / {coverage.unlabeled_reading_count} 缺批次片</Cell>
     </>:<>
      <Cell label="重拟合折数 / 覆盖滤片">{lobo.evaluable_fold_count} 可评估折（{lobo.unevaluable_fold_count} 折不可评估）/ {lobo.evaluable_reading_count} 片</Cell>
      <Cell label="总 MSE（kPa²）" tone="brass">{fmt(lobo.mse,6)}</Cell>
      <Cell label="域内 MSE / 滤片数">{fmt(lobo.interior_mse,6)} / {lobo.interior_reading_count} 片</Cell>
      <Cell label="端点夹持">{lobo.clamped_folds} 折 / {lobo.clamped_reading_count} 片（计入并标记）</Cell>
      <Cell label="批次覆盖" tone="muted">{lobo.batches.join(' / ')}；缺批次 {lobo.unlabeled_reading_count} 片完全不参与（训练与评估均排除）</Cell>
     </>}
   </div>
  </dl>
  {!legacy&&lobo.available&&Number.isFinite(lobo.mse)&&
   <p className="compare-verdict">
    LOBO 总MSE {fmt(lobo.mse,6)} 对比 LODO 总MSE {fmt(lodo.mse,6)}；
    LOBO 只覆盖 {lobo.evaluable_reading_count}/{lodo.reading_count} 片且按批次留出，两者口径与覆盖不同，应并排阅读而非直接相减下结论。
   </p>}
 </section>;
}
