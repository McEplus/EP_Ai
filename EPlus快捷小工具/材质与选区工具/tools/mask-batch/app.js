const core=createMaskCore();
const $=id=>document.getElementById(id);
let files=[],rows=[],selected=null,mode='white',busy=false,worker=null,activeReject=null,previewSerial=0;
const statuses={ready:'待处理',working:'处理中',done:'已生成',already:'已处理 · 保留',missing:'缺基础图',duplicate:'同名冲突',error:'处理失败'};
function safePath(path){const parts=path.replaceAll('\\','/').split('/').filter(Boolean);if(parts.some(p=>p==='..'||p==='.'||p.includes('\0')))throw Error('文件路径无效');return parts.join('/');}
function status(message){$('message').textContent=message;}
function refresh(){
  const ready=rows.filter(r=>r.status==='ready').length,done=rows.filter(r=>r.output).length;
  $('total').textContent=rows.length;$('ready').textContent=ready;$('completed').textContent=done;
  $('abnormal').textContent=rows.filter(r=>['missing','duplicate','error'].includes(r.status)).length;
  $('run').disabled=busy||!ready;$('cancel').disabled=!busy;$('export').disabled=busy||!done;
  $('clear').disabled=busy;$('addFiles').disabled=busy;$('addFolder').disabled=busy;
  $('report').disabled=!rows.length;$('download').disabled=!selected?.output;
  $('empty').classList.toggle('hidden',!!rows.length);
  const query=$('filter').value.toLowerCase(),fragment=document.createDocumentFragment();
  for(const row of rows){
    if(!row.path.toLowerCase().includes(query))continue;
    const tr=document.createElement('tr');tr.className='row'+(row===selected?' active':'');tr.tabIndex=0;tr.setAttribute('aria-selected',String(row===selected));
    const name=document.createElement('td'),main=document.createElement('span'),sub=document.createElement('span');
    main.textContent=row.path.split('/').pop();sub.className='path';sub.textContent=row.path.includes('/')?row.path.slice(0,row.path.lastIndexOf('/')):'本地文件';name.append(main,sub);
    const dimensions=document.createElement('td');dimensions.textContent=row.width?row.width+' × '+row.height:'—';
    const state=document.createElement('td');state.className='status '+(row.output?'done':['error','missing','duplicate'].includes(row.status)?'error':'');state.textContent=statuses[row.status];
    tr.append(name,dimensions,state);tr.onclick=()=>select(row);tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(row);}};fragment.append(tr);
  }
  $('rows').replaceChildren(fragment);
}
async function addEntries(entries){
  if(busy)return;
  let ignored=0;
  for(const entry of entries){
    if(!/\.png$/i.test(entry.path)){ignored++;continue;}
    const path=safePath(entry.path);
    let duplicate=false;
    for(const existing of files.filter(x=>x.path===path&&x.file.size===entry.file.size)){
      const a=new Uint8Array(await existing.file.arrayBuffer()),b=new Uint8Array(await entry.file.arrayBuffer());
      if(a.every((v,i)=>v===b[i])){duplicate=true;break;}
    }
    if(duplicate)continue;
    files.push({...entry,path});
  }
  const groups=new Map();for(const entry of files){const key=entry.path.toLowerCase();if(!groups.has(key))groups.set(key,[]);groups.get(key).push(entry);}
  const previous=new Map(rows.map(row=>[row.path,row]));rows=[];
  for(const [key,masks] of groups){
    if(!key.endsWith('_color_mask.png'))continue;
    const path=masks[0].path,bases=groups.get(key.slice(0,-15)+'.png')||[],old=previous.get(path);
    const row={path,mask:masks[0].file,base:bases[0]?.file,basePath:bases[0]?.path,
      status:masks.length>1||bases.length>1?'duplicate':!bases.length?'missing':'ready'};
    if(old&&old.mask===row.mask&&old.base===row.base&&old.output)Object.assign(row,old);
    if(row.status==='ready')try{Object.assign(row,core.info(await row.mask.arrayBuffer()));}catch(e){row.status='error';row.error=e.message;}
    rows.push(row);
  }
  rows.sort((a,b)=>a.path.localeCompare(b.path));selected=rows.find(r=>r.path===selected?.path)||rows[0]||null;
  refresh();if(selected)await select(selected);
  status(`${files.length} 个 PNG · ${rows.length} 组选区${ignored?' · 忽略 '+ignored+' 个非 PNG':''}`);
}
async function walk(entry,prefix=''){
  if(entry.isFile)return [{path:prefix+entry.name,file:await new Promise((resolve,reject)=>entry.file(resolve,reject))}];
  if(!entry.isDirectory)return [];
  const reader=entry.createReader();let entries=[],batch;
  do{batch=await new Promise((resolve,reject)=>reader.readEntries(resolve,reject));entries.push(...batch);}while(batch.length);
  const result=[];for(const child of entries)result.push(...await walk(child,prefix+entry.name+'/'));return result;
}
async function select(row){
  selected=row;const serial=++previewSerial;refresh();
  $('selectedName').textContent=row.path.split('/').pop();$('basePath').textContent=row.basePath||'—';$('maskPath').textContent=row.path;$('outputPath').textContent=row.output?row.path:'—';
  $('detailStatus').textContent=statuses[row.status];$('notice').textContent=row.error||(row.resampled?'基础图已按归一化 UV 对齐；选区图尺寸保持不变。':'');
  try{
    const mask=core.decode(await row.mask.arrayBuffer()),source=row.base?core.decode(await row.base.arrayBuffer()):null;
    const output=row.output?core.decode(row.output.slice().buffer):null;
    if(serial!==previewSerial)return;
    const useMask=mode==='mask';
    const opaqueMask=image=>{if(!image)return null;const rgba=new Uint8Array(image.rgba);for(let p=3;p<rgba.length;p+=4)rgba[p]=255;return {...image,rgba};};
    paint($('sourceCanvas'),useMask?opaqueMask(mask):source);
    if(useMask)paint($('resultCanvas'),opaqueMask(output));
    else if(output&&source){
      const result={width:output.width,height:output.height,rgba:new Uint8Array(output.width*output.height*4)};
      const targets={white:[1,1,1],gray:[141/255,141/255,141/255],red:[1,0,0]},target=targets[mode],chosen=Number($('region').value);
      for(let y=0;y<result.height;y++)for(let x=0;x<result.width;x++){
        const p=(y*result.width+x)*4,q=(Math.min(source.height-1,Math.floor((y+.5)*source.height/result.height))*source.width+Math.min(source.width-1,Math.floor((x+.5)*source.width/result.width)))*4;
        const r=core.region(...output.rgba.subarray(p,p+3)),t=Math.max(...output.rgba.subarray(p,p+3));
        for(let c=0;c<3;c++)result.rgba[p+c]=r>=0&&(chosen<0||chosen===r)?Math.round(target[c]*t):source.rgba[q+c];
        result.rgba[p+3]=source.rgba[q+3];
      }
      paint($('resultCanvas'),result);
    }else paint($('resultCanvas'),null);
    $('sourceSize').textContent=(useMask?mask:source)?.width?`${(useMask?mask:source).width} × ${(useMask?mask:source).height}`:'';
    $('outputSize').textContent=output?`${output.width} × ${output.height}`:'';
  }catch(e){if(serial===previewSerial)$('notice').textContent=e.message;}
}
function paint(canvas,image){
  canvas.width=image?.width||1;canvas.height=image?.height||1;
  if(image){const data=new ImageData(new Uint8ClampedArray(image.rgba),image.width,image.height);canvas.getContext('2d').putImageData(data,0,0);}
  const zoom=Number($('zoom').value);canvas.parentElement.classList.toggle('full',!!zoom);
  canvas.style.width=zoom?canvas.width*zoom+'px':'100%';canvas.style.height=zoom?canvas.height*zoom+'px':'auto';
}
function makeWorker(){
  const sources='self.window=self;\n'+['pako-lib','upng-lib'].map(id=>$(id).textContent).join('\n');
  const source=sources+'\nconst core=('+createMaskCore.toString()+')();\nonmessage=function(event){try{const base=core.decode(event.data.base),mask=core.decode(event.data.mask);if(mask.compiled){postMessage({kind:"done",output:event.data.mask,width:mask.width,height:mask.height,already:true},[event.data.mask]);return;}const result=core.build(base,mask,p=>postMessage({kind:"progress",progress:p}));const output=core.encode(result.width,result.height,result.rgba);postMessage({kind:"done",output:output.buffer,width:result.width,height:result.height,resampled:result.resampled,selected:result.selected},[output.buffer]);}catch(e){postMessage({kind:"error",message:e.message});}};';
  const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'})),w=new Worker(url);URL.revokeObjectURL(url);return w;
}
async function run(){
  if(busy)return;busy=true;refresh();worker=makeWorker();const pending=rows.filter(r=>r.status==='ready');let completed=0;
  try{
    for(const row of pending){
      if(!busy)break;row.status='working';refresh();status('处理中：'+row.path);
      try{
        const base=await row.base.arrayBuffer(),mask=await row.mask.arrayBuffer();
        if(!busy){row.status='ready';break;}
        const response=await new Promise((resolve,reject)=>{
          activeReject=reject;worker.onerror=e=>reject(Error(e.message||'处理线程失败'));
          worker.onmessage=e=>{const data=e.data;if(data.kind==='progress'){$('progress').style.width=((completed+data.progress)/pending.length*100)+'%';return;}activeReject=null;data.kind==='error'?reject(Error(data.message)):resolve(data);};
          worker.postMessage({base,mask},[base,mask]);
        });
        Object.assign(row,{output:new Uint8Array(response.output),status:response.already?'already':'done',width:response.width,height:response.height,resampled:response.resampled,selectedPixels:response.selected});
      }catch(e){if(!busy){row.status='ready';break;}row.status='error';row.error=e.message;}
      completed++;refresh();if(row===selected)await select(row);
    }
    status(busy?'处理完成':'已停止；已完成文件保留');
  }catch(e){status('处理失败：'+e.message);}finally{busy=false;worker?.terminate();worker=null;activeReject=null;$('progress').style.width=completed===pending.length?'100%':'0';refresh();}
}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
function report(){return {algorithm:'detail-v1',created:new Date().toISOString(),files:rows.map(r=>({mask:r.path,base:r.basePath||null,status:r.status,error:r.error||null,width:r.width,height:r.height,uvResampled:!!r.resampled,outputBytes:r.output?.length||0}))};}
async function exportZip(){
  $('export').disabled=true;
  try{
    const zip=new JSZip(),names=new Set();
    for(const row of rows.filter(r=>r.output)){const name=$('keepPaths').checked?row.path:row.path.split('/').pop();if(names.has(name.toLowerCase()))throw Error('同名文件冲突，请保留目录后导出');names.add(name.toLowerCase());zip.file(name,row.output);}
    zip.file('_eplus_mask_report.json',JSON.stringify(report(),null,2));status('正在打包');
    download(await zip.generateAsync({type:'blob',compression:'STORE'}),'eplus_detail_masks.zip');status('ZIP 已导出');
  }catch(e){status(e.message);}finally{refresh();}
}
$('addFiles').onclick=()=>$('fileInput').click();$('addFolder').onclick=()=>$('folderInput').click();
for(const id of ['fileInput','folderInput'])$(id).onchange=async e=>{try{await addEntries([...e.target.files].map(file=>({file,path:file.webkitRelativePath||file.name})));}catch(error){status(error.message);}e.target.value='';};
$('run').onclick=run;$('cancel').onclick=()=>{busy=false;worker?.terminate();activeReject?.(Error('停止'));};
$('clear').onclick=()=>{files=[];rows=[];selected=null;++previewSerial;refresh();for(const id of ['sourceCanvas','resultCanvas'])paint($(id),null);for(const id of ['sourceSize','outputSize','notice'])$(id).textContent='';for(const id of ['basePath','maskPath','outputPath','detailStatus'])$(id).textContent='—';$('selectedName').textContent='未选择文件';$('progress').style.width='0';status('已清空');};
$('export').onclick=exportZip;$('report').onclick=()=>download(new Blob([JSON.stringify(report(),null,2)],{type:'application/json'}),'eplus_mask_report.json');
$('download').onclick=()=>{if(selected?.output)download(new Blob([selected.output],{type:'image/png'}),selected.path.split('/').pop());};
$('filter').oninput=refresh;
for(const button of $('modes').querySelectorAll('button'))button.onclick=()=>{mode=button.dataset.mode;for(const b of $('modes').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b===button));if(selected)select(selected);};
for(const id of ['region','zoom'])$(id).onchange=()=>{if(selected)select(selected);};
let dragDepth=0;window.addEventListener('dragenter',e=>{e.preventDefault();if(busy)return;dragDepth++;document.body.classList.add('dragging');});
window.addEventListener('dragover',e=>e.preventDefault());window.addEventListener('dragleave',e=>{e.preventDefault();if(--dragDepth<=0){dragDepth=0;document.body.classList.remove('dragging');}});
window.addEventListener('drop',async e=>{e.preventDefault();dragDepth=0;document.body.classList.remove('dragging');if(busy)return;try{const items=[...e.dataTransfer.items].filter(i=>i.kind==='file'),entries=items.map(i=>i.webkitGetAsEntry?.()),loose=[...e.dataTransfer.files];status('读取文件');let list=[];if(entries.length&&entries.every(Boolean)){for(const entry of entries)list.push(...await walk(entry));}else list=loose.map(file=>({path:file.name,file}));await addEntries(list);}catch(error){status(error.message);}});
lucide.createIcons();refresh();
