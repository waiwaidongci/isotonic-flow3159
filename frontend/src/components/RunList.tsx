import {Table} from './common/Table';
import {Status} from './common/Status';
import type {Run} from '../types/domain';

export function RunList({runs,open}:{runs:Run[];open:(run:Run)=>void}){
 return <Table headers={['研究运行','状态','目标压差','LODO MSE','LOBO MSE','打开']}>
  {runs.map(r=>{
   const lobo=r.result?.lobo;
   const loboText=!lobo?'历史结果未运行':!lobo.available?'不可评估':Number.isFinite(lobo.mse)?Number(lobo.mse).toFixed(5):'—';
   return <tr key={r.id}>
    <td><strong>{r.name}</strong><small>#{r.id} / 研究{r.study_id}</small></td>
    <td><Status value={r.status}/>{r.error&&<small className="error-text">{r.error}</small>}</td>
    <td>{r.config.target_pressure} kPa</td>
    <td>{r.result?Number(r.result.lodo.mse).toFixed(5):'—'}</td>
    <td>{r.result?loboText:'—'}</td>
    <td><button onClick={()=>open(r)}>展开响应 ↗</button></td>
   </tr>;})}
 </Table>;
}
