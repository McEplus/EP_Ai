(function (root) {
  'use strict';
  const encoder = new TextEncoder();
  const bytes = data => typeof data === 'string' ? encoder.encode(data) : new Uint8Array(data);
  function relativePath(path) {
    if (typeof path !== 'string' || !path.trim()) throw new Error('输出目录不能为空。');
    const p = path.trim().replace(/\\/g,'/');
    const parts = p.split('/');
    if (parts.some(s => !s || s === '.' || s === '..' || /[<>:"|?*\x00-\x1f]/.test(s) || /[. ]$/.test(s) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(s))) throw new Error(`无效的相对路径：${path}。请使用项目内目录，不含盘符或 ..。`);
    if (parts.some(s => ['.git','.codex','.agents','.bb-import-backups'].includes(s.toLowerCase()))) throw new Error('不能写入工具备份目录或项目管理目录。');
    return parts.join('/');
  }
  function plan(results, paths) {
    const folders = {model:relativePath(paths.modelDir),animation:relativePath(paths.animationDir),texture:relativePath(paths.textureDir)};
    const files = [], ids = new Set(), animationIds = new Set(), destinations = new Set();
    for (const result of results) {
      if (ids.has(result.id)) throw new Error(`模型标识符重复：${result.id}`);
      ids.add(result.id);
      for (const id of Object.keys(result.animations.animations)) {
        if (animationIds.has(id)) throw new Error(`动画标识符重复：${id}`);
        animationIds.add(id);
      }
      for (const file of result.files) {
        const path = `${folders[file.kind]}/${file.name}`;
        if (destinations.has(path.toLowerCase())) throw new Error(`多个文件将写入同一位置：${path}`);
        destinations.add(path.toLowerCase());
        files.push({...file,path,data:bytes(file.data),owner:result.id});
      }
    }
    return files;
  }
  async function getFile(root, path, create = false, createdDirs) {
    const parts = path.split('/'), filename = parts.pop();
    let dir = root, prefix = '';
    for (const part of parts) {
      prefix += (prefix ? '/' : '') + part;
      try { dir = await dir.getDirectoryHandle(part); }
      catch (error) {
        if (error.name !== 'NotFoundError' || !create) throw error;
        const parent = dir;
        dir = await parent.getDirectoryHandle(part,{create:true});
        createdDirs?.push({parent,name:part,path:prefix});
      }
    }
    return {dir,name:filename,handle:await dir.getFileHandle(filename,{create})};
  }
  async function read(root, path) {
    try { return new Uint8Array(await (await (await getFile(root,path)).handle.getFile()).arrayBuffer()); }
    catch (e) { if (e.name === 'NotFoundError') return null; throw e; }
  }
  const equal = (a,b) => a === null || b === null ? a === b : a.length === b.length && a.every((v,i) => v === b[i]);
  async function writeHandle(handle, data) {
    const stream = await handle.createWritable();
    try { await stream.write(data); await stream.close(); }
    catch (e) { try { await stream.abort(); } catch (_) {} throw e; }
  }
  async function discover(root) {
    const found = [];
    async function isPack(dir) {
      try {
        const manifest = JSON.parse(await (await (await dir.getFileHandle('manifest.json')).getFile()).text());
        return manifest.modules?.some(m => m.type === 'resources');
      } catch (e) { if (e.name === 'NotAllowedError') throw e; return false; }
    }
    if (await isPack(root)) found.push({path:'',name:`${root.name}（当前文件夹）`});
    for await (const [name, handle] of root.entries()) {
      if (handle.kind === 'directory' && !name.startsWith('.') && await isPack(handle)) found.push({path:name,name});
    }
    return found;
  }
  async function existingIds(root, starts) {
    const found = [], visited = new Set();
    let count = 0;
    async function walk(dir, prefix, depth) {
      if (depth > 30) throw new Error('项目资源目录层级过深，无法完成标识符预检。');
      for await (const [name,handle] of dir.entries()) {
        const path = prefix ? `${prefix}/${name}` : name;
        const key = path.toLowerCase();
        if (visited.has(key)) continue;
        visited.add(key);
        if (++count > 30000) throw new Error('资源预检超过 30,000 个目录项，请选择更具体的资源包。');
        if (handle.kind === 'directory' && !name.startsWith('.')) await walk(handle,path,depth+1);
        else if (handle.kind === 'file' && name.toLowerCase().endsWith('.json')) {
          let json;
          try {
            const file = await handle.getFile();
            if (file.size > 64 * 1024 * 1024) throw new Error(`资源文件过大，无法预检：${path}`);
            json = JSON.parse((await file.text()).replace(/^\uFEFF/,''));
          } catch (e) { if (e instanceof SyntaxError) continue; throw e; }
          if (!json || typeof json !== 'object' || Array.isArray(json)) continue;
          for (const geo of Array.isArray(json['minecraft:geometry']) ? json['minecraft:geometry'] : []) if (geo?.description?.identifier) found.push({id:geo.description.identifier,path,kind:'model'});
          for (const id of Object.keys(json)) if (id.startsWith('geometry.')) found.push({id,path,kind:'model'});
          for (const id of Object.keys(json.animations || {})) found.push({id,path,kind:'animation'});
        }
      }
    }
    for (const start of new Set(starts)) {
      let dir = root;
      try { for (const part of start.split('/').filter(Boolean)) dir = await dir.getDirectoryHandle(part); }
      catch (e) { if (e.name === 'NotFoundError') continue; throw e; }
      await walk(dir,start,0);
    }
    return found;
  }
  async function preflight(root, files, options = {}) {
    const snapshots = [];
    for (const file of files) {
      relativePath(file.path);
      snapshots.push({...file,previous:await read(root,file.path)});
    }
    const conflicting = snapshots.filter(f => f.previous !== null);
    if (conflicting.length && !options.overwrite) throw new Error(`有 ${conflicting.length} 个同名文件已存在。需要替换时请勾选“允许替换同名文件”。\n${conflicting.map(f => f.path).join('\n')}`);
    const targets = new Map();
    for (const file of files) {
      if (file.kind === 'texture') continue;
      const json = JSON.parse(new TextDecoder().decode(file.data));
      const ids = file.kind === 'model' ? json['minecraft:geometry'].map(g => g.description.identifier) : Object.keys(json.animations);
      for (const id of ids) targets.set(`${file.kind}:${id}`,file.path.toLowerCase());
      const previous = snapshots.find(f => f.path === file.path).previous;
      if (previous) {
        try {
          const old = JSON.parse(new TextDecoder().decode(previous));
          const oldIds = file.kind === 'model' ? [...(old['minecraft:geometry'] || []).map(g=>g.description.identifier),...Object.keys(old).filter(k=>k.startsWith('geometry.'))] : Object.keys(old.animations || {});
          if (oldIds.some(id => !ids.includes(id))) throw new Error(`同名文件包含其他资源标识符，为避免丢失，请更换输出目录或标识符：${file.path}`);
        } catch (e) { if (!(e instanceof SyntaxError)) throw e; }
      }
    }
    const existing = await existingIds(root, options.scanDirs || []);
    for (const record of existing) {
      const target = targets.get(`${record.kind}:${record.id}`);
      if (target && target !== record.path.toLowerCase()) throw new Error(`项目中已有相同标识符“${record.id}”，位于 ${record.path}。请使用新的标识符或改为更新该文件。`);
    }
    return {files:snapshots,overwrite:Boolean(options.overwrite),existingCount:conflicting.length};
  }
  async function commit(root, prepared, onProgress = () => {}) {
    // Check again after the confirmation dialog; do not overwrite edits made meanwhile.
    for (const file of prepared.files) if (!equal(file.previous,await read(root,file.path))) throw new Error(`预检后文件发生变化，请重新预检：${file.path}`);
    const stamp = `${new Date().toISOString().replace(/[:.]/g,'-')}-${Math.random().toString(36).slice(2,8)}`;
    const backupDir = `.bb-import-backups/${stamp}`, written = [], createdDirs = [];
    // Finish ALL backups before opening any target for writing.
    for (const file of prepared.files.filter(f=>f.previous !== null)) {
      const backup = await getFile(root,`${backupDir}/${file.path}`,true);
      await writeHandle(backup.handle,file.previous);
    }
    if (prepared.existingCount) {
      const manifest = await getFile(root,`${backupDir}/backup-info.json`,true);
      await writeHandle(manifest.handle,JSON.stringify({createdAt:new Date().toISOString(),files:prepared.files.map(f=>({path:f.path,hadOriginal:f.previous !== null}))},null,2));
    }
    try {
      for (let i=0;i<prepared.files.length;i++) {
        const file = prepared.files[i];
        // Recheck each target before opening it, including targets that were absent.
        if (!equal(file.previous,await read(root,file.path))) throw new Error(`写入期间文件发生变化：${file.path}`);
        const target = await getFile(root,file.path,true,createdDirs);
        written.push({file,...target});
        await writeHandle(target.handle,file.data);
        if (!equal(file.data,await read(root,file.path))) throw new Error(`写入后校验失败：${file.path}`);
        onProgress(i+1,prepared.files.length);
      }
    } catch (error) {
      const rollbackErrors = [];
      for (const item of written.reverse()) {
        try {
          if (item.file.previous !== null) await writeHandle(item.handle,item.file.previous);
          else await item.dir.removeEntry(item.name);
        } catch (_) { rollbackErrors.push(item.file.path); }
      }
      for (const item of createdDirs.reverse()) { try { await item.parent.removeEntry(item.name); } catch (_) {} }
      if (rollbackErrors.length) throw new Error(`写入失败：${error.message}\n部分回滚失败，请检查：${rollbackErrors.join('、')}。原文件备份：${prepared.existingCount ? backupDir : '本次均为新文件，无旧文件备份'}`);
      throw new Error(`写入失败，已回滚本次文件改动：${error.message}`);
    }
    return {count:prepared.files.length,backupDir:prepared.existingCount ? backupDir : null};
  }
  // ZIP STORE: no runtime packages, no CDN, UTF-8 filenames, standard CRC-32.
  const crcTable = Uint32Array.from({length:256},(_,i) => {
    let c = i; for (let j=0;j<8;j++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0;
  });
  function crc32(data) { let c=0xffffffff; for (const b of data) c=crcTable[(c^b)&255]^(c>>>8); return (c^0xffffffff)>>>0; }
  function zip(files) {
    const chunks = [], central = []; let offset=0, directorySize=0;
    if (files.length > 65535) throw new Error('ZIP 文件数超出限制。');
    const date = new Date(), dosTime=(date.getHours()<<11)|(date.getMinutes()<<5)|(date.getSeconds()>>1), dosDate=((Math.max(1980,date.getFullYear())-1980)<<9)|((date.getMonth()+1)<<5)|date.getDate();
    for (const file of files) {
      const filename=encoder.encode(relativePath(file.path)), data=bytes(file.data), crc=crc32(data);
      const local=new Uint8Array(30+filename.length), v=new DataView(local.buffer);
      v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint16(10,dosTime,true);v.setUint16(12,dosDate,true);v.setUint32(14,crc,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,filename.length,true);local.set(filename,30);
      chunks.push(local,data);
      const record=new Uint8Array(46+filename.length), d=new DataView(record.buffer);
      d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint16(8,0x800,true);d.setUint16(12,dosTime,true);d.setUint16(14,dosDate,true);d.setUint32(16,crc,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);d.setUint16(28,filename.length,true);d.setUint32(42,offset,true);record.set(filename,46);
      central.push(record);directorySize+=record.length;offset+=local.length+data.length;
      if (offset+directorySize > 0xffffffff) throw new Error('ZIP 超过 4 GB 限制。');
    }
    const end=new Uint8Array(22), e=new DataView(end.buffer);
    e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,directorySize,true);e.setUint32(16,offset,true);
    return new Blob([...chunks,...central,end],{type:'application/zip'});
  }
  root.BBProject = {relativePath,plan,discover,preflight,commit,zip,crc32};
})(globalThis);
