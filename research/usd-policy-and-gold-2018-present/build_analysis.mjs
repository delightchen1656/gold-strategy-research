import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.dirname(fileURLToPath(import.meta.url));
const raw = path.join(root, 'raw_data');
const out = path.join(root, 'outputs');

function parseCsv(text, sep=',') {
  const lines=text.trim().split(/\r?\n/); const headers=lines.shift().split(sep);
  return lines.map(line=>{ const vals=[]; let cur='',q=false; for(let i=0;i<line.length;i++){const c=line[i];if(c==='"')q=!q;else if(c===sep&&!q){vals.push(cur);cur='';}else cur+=c;} vals.push(cur); return Object.fromEntries(headers.map((h,i)=>[h,vals[i]]));});
}
const fed=parseCsv(await fs.readFile(`${raw}/fed_target_upper.csv`,'utf8'))
  .map(r=>({date:r.observation_date, rate:Number(r.DFEDTARU)})).filter(r=>Number.isFinite(r.rate));
const gold=parseCsv(await fs.readFile(`${raw}/xauusd_daily.csv`,'utf8'),';')
  .map(r=>({date:r.Date.slice(0,10).replaceAll('.','-'),open:+r.Open,high:+r.High,low:+r.Low,close:+r.Close,volume:+r.Volume}))
  .filter(r=>r.date>='2017-12-01'&&r.date<='2026-09-01'&&Number.isFinite(r.close)).sort((a,b)=>a.date.localeCompare(b.date));

const dates = [
'2018-01-31','2018-03-21','2018-05-02','2018-06-13','2018-08-01','2018-09-26','2018-11-08','2018-12-19',
'2019-01-30','2019-03-20','2019-05-01','2019-06-19','2019-07-31','2019-09-18','2019-10-30','2019-12-11',
'2020-01-29','2020-03-03','2020-03-15','2020-04-29','2020-06-10','2020-07-29','2020-09-16','2020-11-05','2020-12-16',
'2021-01-27','2021-03-17','2021-04-28','2021-06-16','2021-07-28','2021-09-22','2021-11-03','2021-12-15',
'2022-01-26','2022-03-16','2022-05-04','2022-06-15','2022-07-27','2022-09-21','2022-11-02','2022-12-14',
'2023-02-01','2023-03-22','2023-05-03','2023-06-14','2023-07-26','2023-09-20','2023-11-01','2023-12-13',
'2024-01-31','2024-03-20','2024-05-01','2024-06-12','2024-07-31','2024-09-18','2024-11-07','2024-12-18',
'2025-01-29','2025-03-19','2025-05-07','2025-06-18','2025-07-30','2025-09-17','2025-10-29','2025-12-10',
'2026-01-28','2026-03-18','2026-04-29','2026-06-17','2026-07-29'];
const emergency=new Set(['2020-03-03','2020-03-15']);
const fedMap=new Map(fed.map(x=>[x.date,x.rate]));
function dayAfter(s){const d=new Date(`${s}T00:00:00Z`);d.setUTCDate(d.getUTCDate()+1);return d.toISOString().slice(0,10)}
function baselineIdx(s){return gold.findIndex(x=>x.date>=s)}
const events=dates.map(d=>({date:d,meeting:emergency.has(d)?'紧急会议':'例会',oldRate:fedMap.get(d),newRate:fedMap.get(dayAfter(d)),idx:baselineIdx(d)}));

const wb=Workbook.create();
const dash=wb.worksheets.add('仪表盘'); const es=wb.worksheets.add('事件研究'); const gp=wb.worksheets.add('黄金价格'); const fr=wb.worksheets.add('政策利率'); const src=wb.worksheets.add('来源与说明'); const chk=wb.worksheets.add('检查');
for(const s of [dash,es,gp,fr,src,chk]) s.showGridLines=false;
const navy='#17365D', blue='#D9EAF7', goldc='#D9A441', green='#E2F0D9', red='#FCE4D6', gray='#F2F2F2', white='#FFFFFF';
function title(sheet,range,text){sheet.getRange(range).merge();sheet.getRange(range.split(':')[0]).values=[[text]];sheet.getRange(range).format={fill:navy,font:{bold:true,color:white,size:16},verticalAlignment:'center'};}
function header(r){r.format={fill:navy,font:{bold:true,color:white},horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,borders:{preset:'inside',style:'thin',color:'#A6A6A6'}};}
function section(r){r.format={fill:blue,font:{bold:true,color:'#17365D'},borders:{preset:'outside',style:'thin',color:'#9EADBA'}};}

// Raw gold
title(gp,'A1:F1','黄金现货日线（XAU/USD）');
gp.getRange('A2:F2').values=[['日期','开盘','最高','最低','收盘','成交量']];header(gp.getRange('A2:F2'));
gp.getRange(`A3:F${gold.length+2}`).values=gold.map(x=>[new Date(`${x.date}T00:00:00Z`),x.open,x.high,x.low,x.close,x.volume]);
gp.getRange(`A3:A${gold.length+2}`).format.numberFormat='yyyy-mm-dd';gp.getRange(`B3:E${gold.length+2}`).format.numberFormat='$#,##0.00';gp.getRange(`F3:F${gold.length+2}`).format.numberFormat='#,##0';gp.freezePanes.freezeRows(2);
gp.getRange('A:F').format.columnWidth=14; gp.getRange('F:F').format.columnWidth=16;

// Raw fed
title(fr,'A1:B1','联邦基金目标区间上限（日度）');fr.getRange('A2:B2').values=[['日期','上限']];header(fr.getRange('A2:B2'));
fr.getRange(`A3:B${fed.length+2}`).values=fed.map(x=>[new Date(`${x.date}T00:00:00Z`),x.rate/100]);fr.getRange(`A3:A${fed.length+2}`).format.numberFormat='yyyy-mm-dd';fr.getRange(`B3:B${fed.length+2}`).format.numberFormat='0.00%';fr.freezePanes.freezeRows(2);fr.getRange('A:B').format.columnWidth=18;

// Event study
title(es,'A1:Z1','FOMC 政策事件与黄金后续表现');
es.getRange('A2:Z2').merge();es.getRange('A2').values=[['窗口为交易日；基准价取决议日或其后首个黄金交易日收盘。收益分类阈值：>+1% 上涨，<-1% 下跌，其余震荡。']];es.getRange('A2').format={fill:gray,font:{italic:true,color:'#555555'},wrapText:true};
const eh=['序号','决议日','会议类型','原上限','新上限','变动(bp)','政策分类','黄金行号','基准交易日','基准收盘','1日价','1日收益','3日价','3日收益','5日价','5日收益','10日价','10日收益','20日价','20日收益','60日价','60日收益','短期分类','中期分类','综合走势','数据状态'];
es.getRange('A4:Z4').values=[eh];header(es.getRange('A4:Z4'));
const erows=events.length, estart=5, eend=estart+erows-1;
es.getRange(`A${estart}:E${eend}`).values=events.map((x,i)=>[i+1,new Date(`${x.date}T00:00:00Z`),x.meeting,x.oldRate/100,x.newRate/100]);
es.getRange(`H${estart}:H${eend}`).values=events.map(x=>[x.idx>=0?x.idx+3:null]);
for(let r=estart;r<=eend;r++){
  es.getRange(`F${r}`).formulas=[[`=(E${r}-D${r})*10000`]];
  es.getRange(`G${r}`).formulas=[[`=IF(F${r}>0,"加息",IF(F${r}<0,"降息","暂停"))`]];
  es.getRange(`I${r}`).formulas=[[`=IF(H${r}="","",INDEX('黄金价格'!$A$3:$A$${gold.length+2},H${r}-2))`]];
  es.getRange(`J${r}`).formulas=[[`=IF(H${r}="","",INDEX('黄金价格'!$E$3:$E$${gold.length+2},H${r}-2))`]];
  const wins=[[1,'K','L'],[3,'M','N'],[5,'O','P'],[10,'Q','R'],[20,'S','T'],[60,'U','V']];
  for(const [w,pc,rc] of wins){es.getRange(`${pc}${r}`).formulas=[[`=IF(OR(H${r}="",H${r}-2+${w}>${gold.length}),"",INDEX('黄金价格'!$E$3:$E$${gold.length+2},H${r}-2+${w}))`]];es.getRange(`${rc}${r}`).formulas=[[`=IF(${pc}${r}="","",${pc}${r}/J${r}-1)`]];}
  es.getRange(`W${r}`).formulas=[[`=IF(P${r}="","数据不足",IF(P${r}>1%,"上涨",IF(P${r}<-1%,"下跌","震荡")))`]];
  es.getRange(`X${r}`).formulas=[[`=IF(T${r}="","数据不足",IF(T${r}>1%,"上涨",IF(T${r}<-1%,"下跌","震荡")))`]];
  es.getRange(`Y${r}`).formulas=[[`=IF(OR(W${r}="数据不足",X${r}="数据不足"),"数据不足",IF(W${r}=X${r},W${r},IF(AND(P${r}>0,T${r}>0),"先弱后强",IF(AND(P${r}<0,T${r}<0),"先强后弱","方向反转"))))`]];
  es.getRange(`Z${r}`).formulas=[[`=IF(H${r}="","无黄金数据",IF(V${r}="","窗口未满","完整"))`]];
}
es.getRange(`B${estart}:B${eend}`).format.numberFormat='yyyy-mm-dd';es.getRange(`D${estart}:E${eend}`).format.numberFormat='0.00%';es.getRange(`F${estart}:F${eend}`).format.numberFormat='0';es.getRange(`I${estart}:I${eend}`).format.numberFormat='yyyy-mm-dd';es.getRange(`J${estart}:K${eend}`).format.numberFormat='$#,##0.00';es.getRange(`M${estart}:M${eend}`).format.numberFormat='$#,##0.00';es.getRange(`O${estart}:O${eend}`).format.numberFormat='$#,##0.00';es.getRange(`Q${estart}:Q${eend}`).format.numberFormat='$#,##0.00';es.getRange(`S${estart}:S${eend}`).format.numberFormat='$#,##0.00';es.getRange(`U${estart}:U${eend}`).format.numberFormat='$#,##0.00';for(const c of ['L','N','P','R','T','V'])es.getRange(`${c}${estart}:${c}${eend}`).format.numberFormat='0.00%;[Red](0.00%);-';
es.freezePanes.freezeRows(4);es.freezePanes.freezeColumns(3);es.getRange('A:Z').format.columnWidth=12;es.getRange('C:C').format.columnWidth=13;es.getRange('G:G').format.columnWidth=11;es.getRange('W:Z').format.columnWidth=14;

// Dashboard
title(dash,'A1:L1','美元政策变化对黄金的事件研究（2018 至今）');dash.getRange('A2:L2').merge();dash.getRange('A2').values=[['样本截至：政策 2026-08-31；黄金 2025-06-06。结论仅描述历史事件后的相关表现，不代表单一因果关系或投资建议。']];dash.getRange('A2').format={fill:gray,font:{color:'#555555'},wrapText:true};
dash.getRange('A4:D4').values=[['政策分类','事件数','5日平均','20日平均']];header(dash.getRange('A4:D4'));dash.getRange('A5:A7').values=[['加息'],['降息'],['暂停']];
for(let r=5;r<=7;r++){dash.getRange(`B${r}`).formulas=[[`=COUNTIF('事件研究'!$G$${estart}:$G$${eend},A${r})`]];dash.getRange(`C${r}`).formulas=[[`=AVERAGEIF('事件研究'!$G$${estart}:$G$${eend},A${r},'事件研究'!$P$${estart}:$P$${eend})`]];dash.getRange(`D${r}`).formulas=[[`=AVERAGEIF('事件研究'!$G$${estart}:$G$${eend},A${r},'事件研究'!$T$${estart}:$T$${eend})`]];}
dash.getRange('C5:D7').format.numberFormat='0.00%;[Red](0.00%);-';dash.getRange('A4:D7').format.borders={preset:'outside',style:'thin',color:'#9EADBA'};
dash.getRange('F4:I4').values=[['政策分类','上涨','震荡','下跌']];header(dash.getRange('F4:I4'));dash.getRange('F5:F7').values=[['加息'],['降息'],['暂停']];for(let r=5;r<=7;r++){for(const [c,label] of [['G','上涨'],['H','震荡'],['I','下跌']])dash.getRange(`${c}${r}`).formulas=[[`=COUNTIFS('事件研究'!$G$${estart}:$G$${eend},F${r},'事件研究'!$X$${estart}:$X$${eend},"${label}")`]];}
dash.getRange('A10:L10').merge();dash.getRange('A10').values=[['阅读要点']];section(dash.getRange('A10:L10'));
dash.getRange('A11:L15').merge();dash.getRange('A11').formulas=[[`="样本内加息事件 20 日平均收益为 "&TEXT(D5,"0.00%")&"，降息为 "&TEXT(D6,"0.00%")&"，暂停为 "&TEXT(D7,"0.00%")&"。请结合通胀、美元指数、实际利率与风险事件解释；利率方向本身不是黄金走势的充分条件。"`]];dash.getRange('A11').format={wrapText:true,verticalAlignment:'top',fill:'#FFF8E7',font:{size:12,color:'#5B4636'}};
dash.getRange('A:D').format.columnWidth=16;dash.getRange('F:I').format.columnWidth=16;dash.getRange('A11:L15').format.rowHeight=24;

// Sources and methodology
title(src,'A1:D1','来源、口径与限制');src.getRange('A3:D3').values=[['项目','口径/值','来源','备注']];header(src.getRange('A3:D3'));
src.getRange('A4:D11').values=[
['政策事件','FOMC 例会及 2020-03-03/15 紧急会议','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm','事件日为声明日'],
['政策利率','Federal Funds Target Range - Upper Limit (DFEDTARU)','https://fred.stlouisfed.org/series/DFEDTARU','变动幅度按决议日与次日上限差计算'],
['黄金价格','XAU/USD 日线收盘','https://github.com/FeziweMelvin/XAUUSD-Gold-Price','MetaTrader 4 来源；当前文件截止 2025-06-06'],
['窗口','1/3/5/10/20/60 个交易日','本工作簿计算','决议日无交易则取其后首个交易日'],
['分类阈值','>+1% 上涨；<-1% 下跌；其余震荡','本工作簿假设','可按研究偏好调整'],
['完整性','政策至 2026-08-31；黄金至 2025-06-06','原始文件检查','后段政策保留但不参与未满窗口统计'],
['因果限制','事件后收益是条件统计，不是严格因果识别','研究说明','未控制市场预期、通胀、美元和风险溢价'],
['用途','历史归纳与情景参考','研究说明','不构成投资建议']];
src.getRange('A:D').format.columnWidth=26;src.getRange('B:B').format.columnWidth=42;src.getRange('C:C').format.columnWidth=58;src.getRange('D:D').format.columnWidth=42;src.getRange('A4:D11').format.wrapText=true;src.getRange('A4:D11').format.rowHeight=34;

// Checks
title(chk,'A1:F1','数据与模型检查');chk.getRange('A3:F3').values=[['检查项','实际','预期','差异','状态','说明']];header(chk.getRange('A3:F3'));
chk.getRange('A4:A8').values=[['政策事件数量'],['黄金最早日期'],['黄金最晚日期'],['黄金重复日期'],['总体状态']];
chk.getRange('B4').formulas=[[`=COUNTA('事件研究'!$B$${estart}:$B$${eend})`]];chk.getRange('C4').values=[[events.length]];chk.getRange('D4').formulas=[['=B4-C4']];chk.getRange('E4').formulas=[['=IF(D4=0,"OK","检查")']];
chk.getRange('B5').formulas=[[`=MIN('黄金价格'!$A$3:$A$${gold.length+2})`]];chk.getRange('C5').values=[[new Date(`${gold[0].date}T00:00:00Z`)]];chk.getRange('D5').formulas=[['=B5-C5']];chk.getRange('E5').formulas=[['=IF(D5=0,"OK","检查")']];
chk.getRange('B6').formulas=[[`=MAX('黄金价格'!$A$3:$A$${gold.length+2})`]];chk.getRange('C6').values=[[new Date(`${gold.at(-1).date}T00:00:00Z`)]];chk.getRange('D6').formulas=[['=B6-C6']];chk.getRange('E6').formulas=[['=IF(D6=0,"OK","检查")']];
chk.getRange('B7').values=[[new Set(gold.map(x=>x.date)).size]];chk.getRange('C7').values=[[gold.length]];chk.getRange('D7').formulas=[['=C7-B7']];chk.getRange('E7').formulas=[['=IF(D7=0,"OK","检查")']];
chk.getRange('B8').formulas=[['=COUNTIF(E4:E7,"检查")']];chk.getRange('C8').values=[[0]];chk.getRange('D8').formulas=[['=B8-C8']];chk.getRange('E8').formulas=[['=IF(D8=0,"OK","检查")']];
chk.getRange('F4:F8').values=[['事件表覆盖'],['原始价格覆盖'],['原始价格覆盖'],['唯一日期检查'],['全部基础检查汇总']];chk.getRange('B5:C6').format.numberFormat='yyyy-mm-dd';chk.getRange('A:F').format.columnWidth=20;chk.getRange('F:F').format.columnWidth=32;

await fs.mkdir(out,{recursive:true});
const file=`${out}/美元政策与黄金事件研究_2018至今.xlsx`;
const x=await SpreadsheetFile.exportXlsx(wb);await x.save(file);
const inspections=[];
inspections.push((await wb.inspect({kind:'table',range:'仪表盘!A1:L15',include:'values,formulas',tableMaxRows:15,tableMaxCols:12})).ndjson);
inspections.push((await wb.inspect({kind:'table',range:`事件研究!A4:Z12`,include:'values,formulas',tableMaxRows:9,tableMaxCols:26})).ndjson);
inspections.push((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:100},summary:'formula error scan'})).ndjson);
await fs.writeFile(`${out}/verification.txt`,inspections.join('\n'));
for(const [sheet,range,name] of [['仪表盘','A1:L15','preview_dashboard.png'],['事件研究','A1:Z16','preview_events.png'],['来源与说明','A1:D11','preview_sources.png'],['检查','A1:F8','preview_checks.png']]){const b=await wb.render({sheetName:sheet,range,scale:1.2,format:'png'});await fs.writeFile(`${out}/${name}`,new Uint8Array(await b.arrayBuffer()));}
console.log(JSON.stringify({file,goldRows:gold.length,fedRows:fed.length,events:events.length,goldStart:gold[0].date,goldEnd:gold.at(-1).date}));
