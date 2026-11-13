import {fmt} from '../utils/format';
export function FitDigest({result}:{result:any}){
 const lobo=result.lobo;
 const hasLobo=lobo&&lobo.available&&Number.isFinite(lobo.mse);
 return <dl className="fit-digest">
  <div><dt>独立滤片 / 独特流速</dt><dd>{result.reading_count}<span> / {result.unique_flows}</span></dd></div>
  <div><dt>PAVA合并块</dt><dd>{result.pava_blocks.length}</dd></div>
  <div><dt>训练原始读数 MSE</dt><dd>{fmt(result.training_raw_mse,5)}</dd></div>
  <div><dt>整档留一 LODO MSE</dt><dd>{fmt(result.lodo.mse,5)}</dd></div>
  <div><dt>整批留一 LOBO MSE</dt><dd>{hasLobo?fmt(lobo.mse,5):<span className="digest-na">未运行{lobo&&!lobo.available?' / 不可评估':''}</span>}</dd></div>
 </dl>;
}
