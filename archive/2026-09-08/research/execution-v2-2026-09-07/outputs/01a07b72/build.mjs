import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const dir=path.dirname(fileURLToPath(import.meta.url));
const input=JSON.parse(await fs.readFile(path.join(dir,'../../workbook_data.json'),'utf8'));
const wb=Workbook.create();
const sh=wb.worksheets.add('收益与比较');
const tr=wb.worksheets.add('交易记录');
for(const s of [sh,tr]) {s.showGridLines=false;s.getRange('A1:J110').format.font={name:'Arial',size:11,color:'#1F2937'};s.getRange('A1:J110').format.rowHeight=24;}
sh.tabColor='#705429';
sh.getRange('A2').values=[['黄金策略研究：阶段收益']];
sh.getRange('A2').format.font={name:'Arial',size:16,bold:true};
sh.getRange('A3').values=[['趋势＋波动率控仓＋回撤退出；2021-01-04至2026-09-04；每个产品初始5万元']];
const widths={A:19,B:25,C:17,D:17,E:14,F:14,G:14,H:14,I:13,J:18};
for(const [c,w] of Object.entries(widths)) sh.getRange(`${c}1:${c}110`).format.columnWidth=w;
const headers=['产品','阶段','期初资产（元）','期末资产（元）','累计收益','年化收益','最大回撤','平均仓位','买卖次数','费用（元）'];
function header(s,range,values){s.getRange(range).values=[values];s.getRange(range).format={fill:'#705429',font:{name:'Arial',size:11,color:'#FFFFFF',bold:true},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:30};}
header(sh,'A5:J5',headers);
function writeMetrics(row,m){
  sh.getRange(`A${row}:J${row}`).values=[[m.product,m.period,m.initial,m.final_cny,null,m.cagr_pct/100,-m.max_drawdown_pct/100,m.average_weight_pct/100,m.trade_days,m.fees_cny]];
  sh.getRange(`E${row}`).formulas=[[`=D${row}/C${row}-1`]];
}
input.rows.slice(0,6).forEach((m,i)=>writeMetrics(6+i,m));
input.rows.slice(6,8).forEach((m,i)=>writeMetrics(13+i,m));
sh.getRange('A13:J14').format.fill='#F4EFE6';
header(sh,'A17:J17',headers);
input.rows.slice(8).forEach((m,i)=>writeMetrics(18+i,m));
sh.getRange('C6:D29').setNumberFormat('#,##0.00;(#,##0.00);"—"');
sh.getRange('E6:H29').setNumberFormat('0.00%;(0.00%);"—"');
sh.getRange('I6:I29').setNumberFormat('0');
sh.getRange('J6:J29').setNumberFormat('#,##0.00;(#,##0.00);"—"');
sh.getRange('C6:J29').format.horizontalAlignment='right';
sh.getRange('A32').values=[['同口径比较（前期固定参数，后期检查约束）']];
sh.getRange('A32').format.font={name:'Arial',size:14,bold:true};
// A wider comparison label occupies existing A:B; leave B empty, without merging.
header(sh,'A34:F34',['方法','','积存金年化','建信A年化','最差全期回撤','六阶段合格']);
input.comparisons.forEach((r,i)=>sh.getRange(`A${35+i}:F${35+i}`).values=[[r[0],null,...r.slice(1)]]);
sh.getRange('C35:E45').setNumberFormat('0.00%;(0.00%);"—"');
sh.getRange('F35:F45').format.horizontalAlignment='center';
const notes=[
  '费用口径：建信A标准申购1.5%；支付宝具体优惠未核实。0.15%情景年化为11.28%。',
  '赎回按FIFO持有天数收费：不足7日1.5%，7至不足30日0.5%，满30日0%；到账按T+7保守测算。',
  '积存金为伦敦金×汇率的价格代理，买卖各2.5元/克；缺少历史客户报价及完整历史下单规则。',
  '平均仓位按阶段每日净值时点计算。阶段收益含首日变化与费用；期末按净值/中间价估值，未清仓。',
  '本表是固定输入的回测快照；Excel只重算资产收益比率，更改策略需重新运行回测。',
  '已检查资金与份额对账、赎回到账占用及未来数据截断；历史约束不保证未来回撤。',
  '产品费率来源：https://www.ccbfund.cn/u/cms/jx/brief/009033.pdf',
  '伦敦金来源：https://www.westmetall.com/en/markdaten.php?action=table&field=USD_ozt_London&year=2026',
  '完整执行假设、点差报道与验证记录见随附研究结论。'
];
notes.forEach((t,i)=>sh.getRange(`A${48+i}`).values=[[t]]);
sh.freezePanes.freezeRows(5);

tr.getRange('A2').values=[['主候选交易记录']];
tr.getRange('A2').format.font={name:'Arial',size:16,bold:true};
tr.getRange('A3').values=[['买入金额含申购费或点差；卖出金额已扣赎回费或点差。信号信息均早于成交日期。']];
header(tr,'A5:H5',['产品','成交日期','买卖','份额／克数','净值／中间价','现金金额（元）','费用（元）','目标仓位']);
const transactions=input.trades.map(r=>[r[0],new Date(r[1]+'T00:00:00Z'),...r.slice(2)]);
tr.getRange(`A6:H${5+transactions.length}`).values=transactions;
for(const [c,w] of Object.entries({A:19,B:17,C:12,D:19,E:21,F:22,G:19,H:16}))tr.getRange(`${c}1:${c}100`).format.columnWidth=w;
tr.getRange(`B6:B${5+transactions.length}`).setNumberFormat('yyyy-mm-dd');
tr.getRange(`B6:C${5+transactions.length}`).format.horizontalAlignment='center';
tr.getRange(`D6:E${5+transactions.length}`).setNumberFormat('#,##0.0000');
tr.getRange(`F6:G${5+transactions.length}`).setNumberFormat('#,##0.00;(#,##0.00);"—"');
tr.getRange(`H6:H${5+transactions.length}`).setNumberFormat('0%');
tr.freezePanes.freezeRows(5);
const originalInitial=sh.getRange('C6').values[0][0];
sh.getRange('C6').values=[[originalInitial*1.1]];
const recalculated=sh.getRange('E6').values[0][0];
if(Math.abs(recalculated-(input.rows[0].final_cny/(originalInitial*1.1)-1))>1e-10)throw new Error('Return formula did not recalculate');
sh.getRange('C6').values=[[originalInitial]];
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'收益与比较!C6:H14',include:'values,formulas',tableMaxRows:9,tableMaxCols:6,maxChars:1800})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
for(const [name,range,file] of [['收益与比较','A1:J15','summary'],['收益与比较','A17:J29','years'],['收益与比较','A32:J57','comparison'],['交易记录','A1:H16','trades']]){
  const image=await wb.render({sheetName:name,range,scale:1.4,format:'png'});
  await fs.writeFile(path.join(dir,file+'.png'),new Uint8Array(await image.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(dir,'黄金策略阶段收益.xlsx'));
console.log('Exported',transactions.length,'trades');
