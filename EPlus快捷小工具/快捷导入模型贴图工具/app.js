(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const defaultPack = 'resource_pack_EP_JXK_21';
  const defaults = {projectPath:'D:\\MCStudioDownload\\work\\m15962993069@163.com\\Cpp\\AddOn\\a745f7b0d91e4bf0b64b0cf0f37c9878',resourcePack:defaultPack,modelDir:`${defaultPack}/models/entity`,animationDir:`${defaultPack}/animations`,textureDir:`${defaultPack}/textures/entity`};
  const configKeys = Object.keys(defaults), pathKeys = ['modelDir','animationDir','textureDir'];
  let settings = {...defaults}, items = [], project = null, selected = null, files = [], busy = false, prepared = null, toastTimer;
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const size = n => n < 1024 ? `${n} B` : n < 1048576 ? `${(n/1024).toFixed(1)} KB` : `${(n/1048576).toFixed(1)} MB`;
  function toast(message) {
    $('toast').textContent = message; $('toast').hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(()=>$('toast').hidden=true,5500);
  }
  function message(text, type = 'warning') { $('validation').innerHTML = `<div class="notice ${type}" role="status">${esc(text)}</div>`; }
  function saveSettings() {
    for (const k of configKeys) settings[k] = $(k).value;
    try {localStorage.setItem('eplus-bb-settings-v1',JSON.stringify(settings));} catch (_) {}
  }
  function applySettings(data) {
    for (const key of configKeys) if (typeof data[key] === 'string') settings[key] = data[key];
    $('resourcePack').replaceChildren(new Option(settings.resourcePack || '项目根目录',settings.resourcePack));
    for (const key of configKeys) $(key).value = settings[key];
  }
  try {const saved=JSON.parse(localStorage.getItem('eplus-bb-settings-v1'));if(saved)settings={...settings,...saved};} catch (_) {}
  applySettings(settings);
  function busyState(value) {
    busy=value;
    document.querySelector('main').inert=value;
    $('confirmImport').disabled=value;
    $('cancelImport').disabled=value;
    $('importButton').disabled=value || !project || !files.length || items.some(i=>i.error);
  }
  function outputRows(list, confirmed = false) {
    const kind = {model:['G','geo','Bedrock 模型'],animation:['A','anim','骨骼动画'],texture:['T','tex','PNG 贴图']};
    return list.map(f=>{const [letter,cls,title]=kind[f.kind];return `<div class="output-row"><span class="file-icon ${cls}">${letter}</span><span class="output-path">${esc(f.path)}<small>${title}${confirmed ? (f.previous !== null ? ' · 将备份并替换' : ' · 新建') : ''}</small></span><span class="output-size">${size(f.data.length)}</span></div>`;}).join('');
  }
  function evaluate(item) {
    item.result=null;item.preview=null;item.error=item.parseError || '';
    if (!item.model) return;
    try {
      item.preview=BBConvert.convert(item.model,item.identifier.trim() || 'geometry.preview');
      BBConvert.identifier(item.identifier);
      item.result=item.preview;
    } catch(e) {item.error=e.message;}
  }
  function renderQueue() {
    $('queue').innerHTML=items.map(item=>{
      const m=item.model, p=item.preview, count=m?.elements?.filter(e=>e.type==='cube' || !e.type).length || 0;
      const thumb=p?.image.source;
      return `<article class="asset-card ${item.key===selected?'selected':''}" data-key="${item.key}"><div class="asset-head"><button class="thumb" data-select="${item.key}" title="预览 ${esc(item.filename)}">${thumb ? `<img src="${esc(thumb)}" alt="贴图缩略图" style="width:100%;height:100%;object-fit:contain">` : '◇'}</button><div class="asset-title"><strong>${esc(item.filename)}</strong><div class="asset-meta">${count} 个立方体 · ${m?.animations?.length || 0} 段动画 · ${size(item.size)}</div></div><button class="text-button" data-select="${item.key}">预览</button><button class="remove" data-remove="${item.key}" aria-label="移除 ${esc(item.filename)}">×</button></div><div class="id-row"><label for="id-${item.key}">模型标识符 <span style="color:var(--accent)">*</span></label><input id="id-${item.key}" data-id="${item.key}" spellcheck="false" value="${esc(item.identifier)}" placeholder="geometry.ep.lockpick" ${m?'':'disabled'} class="${item.error?'invalid':''}"></div><p id="error-${item.key}" class="asset-message ${item.error?'error':''}">${esc(item.error || '已就绪 · ' + item.result?.id)}</p></article>`;
    }).join('');
    $('queueCount').textContent=`${items.length} 个模型`;
    $('emptyState').hidden=items.length>0;
    $('clearQueue').disabled=items.length===0;
  }
  function refresh() {
    prepared=null;files=[];
    const errors=items.filter(i=>i.error), valid=items.filter(i=>i.result);
    let planError='';
    try {if(valid.length)files=BBProject.plan(valid.map(i=>i.result),Object.fromEntries(pathKeys.map(k=>[k,$(k).value])));} catch(e){planError=e.message;}
    $('outputList').innerHTML=files.length?outputRows(files):'<div class="output-placeholder">'+(items.length?'请先完成模型检查，再生成输出清单。':'添加模型后，这里会列出即将生成的文件。')+'</div>';
    const ready=items.length>0&&!errors.length&&!planError;
    $('importButton').disabled=!ready||!project||busy;
    $('downloadZip').disabled=!ready||busy;
    $('previewBadge').textContent=planError?'需要修改':errors.length?`${errors.length} 个待处理`:ready?'可导出':'等待素材';
    $('previewBadge').className='badge'+(ready?' ok':items.length?' warning':'');
    $('summary').textContent=ready?`${items.length} 个模型 · ${files.length} 个输出文件`:items.length?'先完成模型检查':'准备好你的模型';
    $('summaryHint').textContent=ready?(project?`目标：${project.name} · ${size(files.reduce((sum,f)=>sum+f.data.length,0))}`:'选择项目后可直接导入，也可以先导出 ZIP。'):items.length?'补全标识符或处理卡片中的提示。':'补全标识符后，即可预览输出。';
    if(planError)message(planError,'error');
    else if(errors.length)message(`${errors.length} 个模型尚未通过检查，请处理上方卡片中的提示。`);
    else if(ready){const warnings=[...new Set(valid.flatMap(i=>i.result.warnings))];$('validation').innerHTML=warnings.length?`<div class="notice">${warnings.map(esc).join('\n')}</div>`:'';}
    else $('validation').replaceChildren();
  }
  const viewer=new BBPreview($('previewCanvas'));
  async function showSelected() {
    const item=items.find(i=>i.key===selected);
    if($('modelPreview').hidden)return;
    if(!item?.preview){viewer.clear();$('texturePreview').textContent=item?.error || '选择一个模型以查看预览。';return;}
    const p=item.preview;
    $('texturePreview').innerHTML=`<img src="${esc(p.image.source)}" alt="模型原始贴图"><div><b>${esc(item.filename)}</b><br>${p.cubeCount} 个立方体 · ${p.boneCount} 根骨骼 · PNG ${p.image.width} × ${p.image.height}<br>UV ${p.geometry['minecraft:geometry'][0].description.texture_width} × ${p.geometry['minecraft:geometry'][0].description.texture_height}</div>`;
    await viewer.load(p);
  }
  async function addFiles(fileList) {
    if(busy)return;
    const accepted=Array.from(fileList).filter(f=>/\.bbmodel$/i.test(f.name));
    if(!accepted.length){toast('请选择或拖入 .bbmodel 文件。');return;}
    if(items.length+accepted.length>100){toast('一次最多处理 100 个模型，请分批导入。');return;}
    busyState(true);
    try {
      for(const file of accepted){
        if(items.some(i=>i.filename===file.name&&i.size===file.size&&i.lastModified===file.lastModified)){toast(`已跳过重复文件：${file.name}`);continue;}
        const item={key:crypto.randomUUID(),filename:file.name,size:file.size,lastModified:file.lastModified,identifier:''};
        try {
          if(file.size>64*1024*1024)throw new Error('单个模型超过 64 MB，请减小贴图尺寸后重试。');
          item.model=BBConvert.parse(await file.text());item.identifier=item.model.model_identifier || '';
        }catch(e){item.parseError=e.message;}
        evaluate(item);
        if(item.preview){
          try{const image=new Image();image.src=item.preview.image.source;await image.decode();}
          catch(_){item.parseError='内嵌 PNG 无法解码，请在 Blockbench 重新保存贴图。';item.error=item.parseError;item.preview=null;item.result=null;}
        }
        items.push(item);selected??=item.key;
      }
      renderQueue();
    }finally{busyState(false);refresh();await showSelected();$('fileInput').value='';}
  }
  $('dropZone').onclick=()=>$('fileInput').click();
  $('fileInput').onchange=e=>addFiles(e.target.files);
  for(const event of ['dragenter','dragover'])$('dropZone').addEventListener(event,e=>{e.preventDefault();if(!busy)$('dropZone').classList.add('dragover');});
  for(const event of ['dragleave','drop'])$('dropZone').addEventListener(event,e=>{e.preventDefault();$('dropZone').classList.remove('dragover');});
  $('dropZone').addEventListener('drop',e=>addFiles(e.dataTransfer.files));
  window.addEventListener('dragover',e=>e.preventDefault());
  window.addEventListener('drop',e=>e.preventDefault());
  $('queue').addEventListener('input',e=>{
    if(!e.target.dataset.id)return;
    const item=items.find(i=>i.key===e.target.dataset.id);item.identifier=e.target.value;evaluate(item);
    e.target.classList.toggle('invalid',Boolean(item.error));
    const error=$(`error-${item.key}`);error.textContent=item.error || `已就绪 · ${item.result.id}`;error.className=`asset-message ${item.error?'error':''}`;refresh();
  });
  $('queue').addEventListener('click',async e=>{
    const remove=e.target.closest('[data-remove]'), select=e.target.closest('[data-select]');
    if(remove){items=items.filter(i=>i.key!==remove.dataset.remove);if(selected===remove.dataset.remove)selected=items[0]?.key;renderQueue();refresh();await showSelected();}
    if(select){selected=select.dataset.select;$('modelPreview').hidden=false;$('togglePreview').textContent='收起模型';renderQueue();await showSelected();}
  });
  $('clearQueue').onclick=()=>{items=[];selected=null;renderQueue();refresh();viewer.clear();$('texturePreview').replaceChildren();};
  $('togglePreview').onclick=async()=>{$('modelPreview').hidden=!$('modelPreview').hidden;$('togglePreview').textContent=$('modelPreview').hidden?'查看模型':'收起模型';await showSelected();};
  $('resetView').onclick=()=>viewer.reset();
  function setPackPaths(pack) {
    const prefix=pack?`${pack}/`:'';
    $('modelDir').value=`${prefix}models/entity`;$('animationDir').value=`${prefix}animations`;$('textureDir').value=`${prefix}textures/entity`;saveSettings();refresh();
  }
  $('chooseProject').onclick=async()=>{
    if(!window.showDirectoryPicker){toast('此浏览器不能直接写入文件夹，请使用桌面版 Edge / Chrome，或导出 ZIP。');return;}
    try {
      const chosen=await showDirectoryPicker({id:'eplus-project',mode:'readwrite'});
      busyState(true);
      const packs=await BBProject.discover(chosen);
      project=chosen;
      const oldPack=$('resourcePack').value;
      $('resourcePack').replaceChildren(...(packs.length?packs.map(p=>new Option(p.name,p.path)):[new Option('未识别资源包 · 手动指定输出目录','')]));
      const match=packs.find(p=>p.path===oldPack);
      if(match)$('resourcePack').value=match.path;
      if(!match)setPackPaths($('resourcePack').value);
      $('projectBadge').textContent='已连接';$('projectBadge').className='badge ok';
      $('projectConnected').textContent=`已授权文件夹：${chosen.name}`;$('projectConnected').hidden=false;
      saveSettings();toast(packs.length?`已识别 ${packs.length} 个资源包。`:'未识别到资源包，请手动确认三个输出目录。');
    }catch(e){if(e.name!=='AbortError')toast(`项目选择失败：${e.message}`);}finally{busyState(false);refresh();}
  };
  $('copyPath').onclick=async()=>{try{await navigator.clipboard.writeText($('projectPath').value);toast('路径已复制，可粘贴到文件夹选择窗口的地址栏。');}catch(_){$('projectPath').focus();$('projectPath').select();toast('请按 Ctrl+C 复制选中的路径。');}};
  $('projectPath').addEventListener('change',()=>{
    project=null;$('projectBadge').textContent='未连接';$('projectBadge').className='badge';$('projectConnected').hidden=true;saveSettings();refresh();
  });
  $('resourcePack').onchange=()=>setPackPaths($('resourcePack').value);
  for(const k of pathKeys)$(k).addEventListener('input',()=>{saveSettings();refresh();});
  $('overwrite').onchange=refresh;
  for(const button of document.querySelectorAll('[data-browse]'))button.onclick=async()=>{
    if(!project){toast('请先选择项目文件夹。');return;}
    try {
      const dir=await showDirectoryPicker({id:'eplus-output',mode:'readwrite',startIn:project});
      const relative=await project.resolve(dir);
      if(!relative||!relative.length)throw new Error('请选择项目内部的输出子文件夹。');
      $(button.dataset.browse).value=relative.join('/');saveSettings();refresh();
    }catch(e){if(e.name!=='AbortError')toast(e.message);}
  };
  function download(blob,filename) {
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
  }
  $('saveConfig').onclick=()=>{saveSettings();download(new Blob([JSON.stringify({version:1,...settings},null,2)],{type:'application/json'}),'eplus-import-config.json');};
  $('loadConfig').onclick=()=>$('configInput').click();
  $('configInput').onchange=async e=>{
    const file=e.target.files[0];if(!file)return;
    try{const data=JSON.parse(await file.text());if(data.version!==1)throw new Error('不是有效的 v1 路径配置。');for(const k of pathKeys)BBProject.relativePath(data[k]);applySettings(data);project=null;$('projectBadge').textContent='未连接';$('projectBadge').className='badge';$('projectConnected').hidden=true;saveSettings();refresh();toast('已载入配置，请选择并授权对应的项目文件夹。');}catch(e){toast(e.message);}finally{$('configInput').value='';}
  };
  $('downloadZip').onclick=()=>{
    refresh();if(!files.length||items.some(i=>i.error))return;
    const report={createdAt:new Date().toISOString(),models:items.map(i=>({source:i.filename,identifier:i.result.id,animations:Object.keys(i.result.animations.animations),warnings:i.result.warnings})),files:files.map(f=>f.path)};
    const blob=BBProject.zip([...files,{path:'eplus-import-report.json',data:JSON.stringify(report,null,2)}]);
    download(blob,'eplus-bedrock-resources.zip');toast('ZIP 已导出，目录结构与预览一致。请解压到项目根目录。');
  };
  $('importButton').onclick=async()=>{
    refresh();if(!project||!files.length||items.some(i=>i.error))return;
    busyState(true);$('importButton').textContent='正在预检…';
    try {
      if(await project.requestPermission({mode:'readwrite'})!=='granted')throw new Error('没有文件夹写入权限，请重新选择项目并允许编辑。');
      const pack=$('resourcePack').value, prefix=pack?`${pack}/`:'';
      const scanDirs=[`${prefix}models`,`${prefix}animations`,$('modelDir').value.replace(/\\/g,'/'),$('animationDir').value.replace(/\\/g,'/')];
      prepared=await BBProject.preflight(project,files,{overwrite:$('overwrite').checked,scanDirs});
      $('confirmSummary').textContent=`将 ${files.length} 个文件写入“${project.name}”：${files.length-prepared.existingCount} 个新建，${prepared.existingCount} 个替换。`;
      $('confirmFiles').innerHTML=outputRows(prepared.files,true);
      $('backupNotice').textContent=prepared.existingCount?'原文件将备份至项目内 .bb-import-backups/时间戳/ 目录。写入失败时会尝试回滚，并报告结果。':'所有目标文件均为新建。请确认以下相对路径。';
      $('confirmDialog').showModal();
    }catch(e){message(e.message,'error');}finally{busyState(false);$('importButton').innerHTML='预检并导入 <span>→</span>';}
  };
  $('cancelImport').onclick=()=>{$('confirmDialog').close();prepared=null;};
  $('confirmDialog').addEventListener('cancel',e=>{if(busy)e.preventDefault();else prepared=null;});
  $('confirmImport').onclick=async()=>{
    if(!prepared||busy)return;
    const batch=prepared;busyState(true);
    try{
      const result=await BBProject.commit(project,batch,(n,total)=>$('confirmImport').textContent=`正在写入 ${n}/${total}`);
      $('confirmDialog').close();message(`导入完成：已写入并校验 ${result.count} 个文件。${result.backupDir?'\n原文件备份：'+result.backupDir:''}\n资源已放入项目；实体、物品和动画的使用绑定请在项目中配置。`,'success');toast(`导入成功 · ${result.count} 个文件`);
    }catch(e){$('confirmDialog').close();message(e.message,'error');}finally{prepared=null;busyState(false);$('confirmImport').textContent='写入项目';}
  };
  $('helpButton').onclick=()=>$('helpDialog').showModal();$('closeHelp').onclick=()=>$('helpDialog').close();
  window.addEventListener('beforeunload',e=>{if(busy){e.preventDefault();e.returnValue='';}});
  if(!window.showDirectoryPicker){$('compatibility').hidden=false;$('compatibility').textContent='当前浏览器不支持直接写入项目。请使用桌面版 Edge / Chrome 打开本工具；也可转换后导出 ZIP。';}
  refresh();
})();
