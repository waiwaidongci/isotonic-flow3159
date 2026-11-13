import {useState} from 'react';
import {PageHeading} from '../components/common/PageHeading';
import {Table} from '../components/common/Table';
import {Notice} from '../components/common/Notice';
import {useTask} from '../hooks/useTask';
import {sourceApi} from '../api/source';
import {fmt} from '../utils/format';

const example={name:'独立滤片三档手算输入',filename:'fw-independent-3doses.json',description:'同x按原始独立滤片数合并；方向预先声明；production_batch记录制片批次',direction:'nondecreasing',levels:[
 {label:'低档',flow:1,readings:[{specimen_ref:'P01',pressure:3,production_batch:'B1'}]},
 {label:'中档',flow:2,readings:[
  {specimen_ref:'P02',pressure:1,production_batch:'B1'},{specimen_ref:'P03',pressure:1,production_batch:'B2'},{specimen_ref:'P04',pressure:1,production_batch:null}]},
 {label:'高档',flow:3,readings:[{specimen_ref:'P05',pressure:2,production_batch:'B2'}]}]};

export function SourcePage({studies,levels,readings,user,reloadSource}:any){
 const [id,S]=useState(0),[raw,R]=useState(JSON.stringify(example,null,2)),task=useTask(),
  study=studies.find((s:any)=>s.id===(id||studies[0]?.id)),
  ls=levels.filter((l:any)=>l.study_id===study?.id),
  rs=readings.filter((r:any)=>r.study_id===study?.id);
 const batches=[...new Set(rs.map((r:any)=>r.production_batch).filter(Boolean))].sort();
 const unlabeled=rs.filter((r:any)=>!r.production_batch).length;
 return <>
  <PageHeading index="02" title="每一片独立滤片，都有来路。" description="流速可重合，滤片编号不能重复；同一滤片重复读数不作独立重复。production_batch 记录制片批次，留空即缺批次、不猜填。"/>
  <label>来源研究<select value={study?.id||''} onChange={e=>S(+e.target.value)}>
   {studies.map((s:any)=><option key={s.id} value={s.id}>{s.name}</option>)}
  </select></label>
  {study&&<p>{study.filename} / {study.description} / 预先声明 {study.direction}</p>}
  {study&&<p className="coverage-line">制片批次 {batches.length} 个{batches.length?`（${batches.join(' / ')}）`:''}；带批次滤片 {rs.length-unlabeled} 片，缺批次 {unlabeled} 片（缺批次不猜填，仅不参与整批留一）。</p>}
  <div className="source-layout">
   <section>
    <h2>档位与独立重复数</h2>
    <Table headers={['档位','流速 mL/min','独立数 / 均压差','修订']}>
     {ls.map((l:any)=>{const items=rs.filter((r:any)=>r.level_id===l.id);
      return <tr key={l.id}><td>{l.label}</td><td>{fmt(l.flow)}</td>
       <td>{items.length} / {fmt(items.reduce((a:number,r:any)=>a+r.pressure,0)/items.length)}</td>
       <td>{user.role!=='viewer'&&<button onClick={()=>{const value=prompt('修订流速（同x会合并）',String(l.flow));if(value!==null)task.act(async()=>{await sourceApi.editLevel(l.id,{label:l.label,flow:+value});await reloadSource()},'档位已修订，已有运行保留原结果')}}>修订流速</button>}</td></tr>;})}
    </Table>
    <h2 className="spaced">原始滤片 / 前24条</h2>
    <Table headers={['滤片编号','制片批次','压差 kPa','测量说明','修订']}>
     {rs.slice(0,24).map((r:any)=>
      <tr key={r.id}><td>{r.specimen_ref}</td>
       <td>{r.production_batch||<span className="digest-na">缺批次</span>}</td>
       <td>{fmt(r.pressure,6)}</td><td>{r.measurement_note}</td>
       <td>{user.role!=='viewer'&&<button onClick={()=>{const value=prompt('修订原始压差',String(r.pressure));if(value!==null)task.act(async()=>{await sourceApi.editReading(r.id,{pressure:+value,measurement_note:r.measurement_note});await reloadSource()},'原始读数已修订')}}>修订读数</button>}</td></tr>)}
    </Table>
   </section>
   <section className="input-panel">
    <small>NEW INDEPENDENT STUDY</small>
    <h2>导入档位与滤片</h2>
    <p>JSON内每档 readings 代表不同滤片。2–30档、总计≤600读数；同流速档合并而不是任意赋权。
    可在每条读数附 production_batch（字符串）记录制片批次；省略或为 null 即缺批次，系统不猜填。缺批次滤片完全不参与整批留一（既不进训练折也不进留出评估），覆盖数会单独标明；LODO 与全量拟合仍使用全部读数。</p>
    {user.role!=='viewer'?
     <form onSubmit={e=>{e.preventDefault();task.act(async()=>{const s=await sourceApi.create(JSON.parse(raw));await reloadSource();S(s.id)},'独立研究已保存，可前往拟合配置')}}>
      <label>研究 JSON<textarea rows={19} value={raw} onChange={e=>R(e.target.value)}/></label>
      <button className="primary" disabled={task.busy}>保存独立研究 →</button>
     </form>:<p>观察员可读取底稿；新研究由试验员提交。</p>}
    <Notice {...task}/>
   </section>
  </div>
 </>;
}
