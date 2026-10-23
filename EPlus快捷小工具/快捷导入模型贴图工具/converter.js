/* Independent, dependency-free bbmodel → Bedrock conversion. See README for scope. */
(function (root) {
  'use strict';
  const dict = () => Object.create(null);
  const directions = ['north', 'east', 'south', 'west', 'up', 'down'];
  const round = n => Math.round(n * 1e8) / 1e8;
  function fail(message) { throw new Error(message); }
  function finite(value, label) {
    if (typeof value !== 'number' || !Number.isFinite(value)) fail(`${label}必须是有限数值。`);
    return value;
  }
  function vector(value, label, fallback = [0, 0, 0], length = 3) {
    const v = value ?? fallback;
    if (!Array.isArray(v) || v.length !== length) fail(`${label}需要 ${length} 个数值。`);
    return v.map(n => finite(n, label));
  }
  function name(value, label) {
    if (typeof value !== 'string' || !value.trim() || ['__proto__', 'constructor', 'prototype'].includes(value)) fail(`${label}为空或无效。`);
    return value;
  }
  function identifier(value) {
    if (typeof value !== 'string' || !value.trim()) fail('缺少模型标识符，请先填写，例如 geometry.ep.lockpick。');
    let id = value.trim();
    if (!id.startsWith('geometry.')) id = `geometry.${id}`;
    if (!/^geometry\.[a-z0-9_]+(?:[.\-][a-z0-9_]+)*$/.test(id) || id.length > 140) fail('标识符需使用小写字母、数字、下划线、点或连字符，例如 geometry.ep.lockpick。');
    return id;
  }
  function safeFilename(id) {
    let value = id.replace(/^geometry\./, '');
    if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(value)) value = `model_${value}`;
    return value;
  }
  function parse(text) {
    let model;
    try { model = JSON.parse(text.replace(/^\uFEFF/, '')); } catch (_) { fail('无法解析 JSON，请确认文件是未压缩的 .bbmodel。'); }
    if (!model || typeof model !== 'object' || !model.meta || !Array.isArray(model.elements)) fail('不是有效的 Blockbench 项目：缺少 meta 或 elements。');
    const major = Number(String(model.meta.format_version).split('.')[0]);
    if (!Number.isFinite(major) || major < 3 || major > 5) fail(`暂不支持 bbmodel ${model.meta.format_version}，请使用 Blockbench 3–5 格式保存。`);
    if (model.elements.length > 30000) fail('模型超过 30,000 个元素，请拆分后导入。');
    return model;
  }
  function png(source) {
    if (typeof source !== 'string' || !/^data:image\/png;base64,/i.test(source)) fail('贴图没有内嵌 PNG。请在 Blockbench 中加载贴图并保存项目，再重新拖入。');
    let bytes;
    try { bytes = Uint8Array.from(atob(source.slice(source.indexOf(',') + 1)), c => c.charCodeAt(0)); }
    catch (_) { fail('内嵌 PNG 的 Base64 数据损坏。'); }
    if (bytes.length < 33 || ![137,80,78,71,13,10,26,10].every((n,i) => bytes[i] === n) || String.fromCharCode(...bytes.slice(12,16)) !== 'IHDR') fail('内嵌贴图不是有效 PNG。');
    const view = new DataView(bytes.buffer);
    const width = view.getUint32(16), height = view.getUint32(20);
    if (!width || !height || width > 16384 || height > 16384 || width * height > 67108864) fail('PNG 尺寸无效或超过 64M 像素限制。');
    let offset = 8, hasData = false, hasEnd = false;
    while (offset + 12 <= bytes.length) {
      const length = view.getUint32(offset);
      if (offset + 12 + length > bytes.length) fail('内嵌 PNG 数据被截断，请重新保存贴图。');
      const type = String.fromCharCode(...bytes.slice(offset+4,offset+8));
      if (type === 'IDAT') hasData = true;
      if (type === 'IEND') {hasEnd = true; break;}
      offset += length + 12;
    }
    if (!hasData || !hasEnd) fail('内嵌 PNG 数据不完整，请重新保存贴图。');
    return {bytes, width, height, source};
  }
  function hierarchy(model) {
    const elements = new Map(), groups = new Map(), used = new Set(), nodes = [], byId = new Map(), names = new Set();
    for (const e of model.elements) {
      if (!e.uuid || elements.has(e.uuid)) fail('元素 UUID 缺失或重复。');
      elements.set(e.uuid, e);
    }
    for (const g of model.groups || []) {
      if (!g.uuid || groups.has(g.uuid)) fail('骨骼 UUID 缺失或重复。');
      groups.set(g.uuid, g);
    }
    let loose;
    const addGroup = (g, parent) => {
      const n = name(g.name, '骨骼名称');
      if (names.has(n)) fail(`骨骼名称“${n}”重复，请先在 Blockbench 中重命名。`);
      names.add(n);
      const node = {group:g, parent, elements:[]};
      nodes.push(node);
      if (g.uuid) {
        if (byId.has(g.uuid)) fail(`骨骼“${n}”在层级中重复。`);
        byId.set(g.uuid, node);
      }
      return node;
    };
    const visit = (items, parent, depth = 0) => {
      if (depth > 100) fail('骨骼层级超过 100 层。');
      for (const item of items) {
        if (typeof item === 'string') {
          const e = elements.get(item);
          if (!e) fail(`层级引用了不存在的元素：${item}`);
          if (used.has(item)) fail(`元素“${e.name}”被重复引用。`);
          used.add(item);
          if (!parent) {
            if (!loose) {
              let n = 'bb_main';
              while (names.has(n) || [...groups.values()].some(g => g.name === n)) n += '_';
              loose = addGroup({name:n, origin:[0,0,0]}, null);
            }
            loose.elements.push(e);
          } else parent.elements.push(e);
        } else if (item && typeof item === 'object') {
          const g = {...groups.get(item.uuid), ...item};
          const node = addGroup(g, parent);
          visit(item.children || [], node, depth + 1);
        } else fail('模型层级中存在无效条目。');
      }
    };
    const outline = model.outliner;
    if (outline != null && !Array.isArray(outline)) fail('outliner 不是数组。');
    visit(outline?.length ? outline : model.elements.map(e => e.uuid), null);
    for (const e of model.elements) if (e.export !== false && !used.has(e.uuid)) fail(`元素“${e.name}”没有出现在层级中，无法确定其父骨骼。`);
    return {nodes, byId, names};
  }
  const mirrorPosition = v => [round(-v[0]), round(v[1]), round(v[2])];
  const mirrorRotation = v => [round(-v[0]), round(-v[1]), round(v[2])];
  function convert(model, suppliedId) {
    const id = identifier(suppliedId ?? model.model_identifier), base = safeFilename(id);
    const warnings = [];
    const width = finite(model.resolution?.width ?? 16, 'UV 宽度'), height = finite(model.resolution?.height ?? 16, 'UV 高度');
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) fail('UV 分辨率必须为正整数。');
    const tree = hierarchy(model), textures = model.textures || [], usedTextures = new Set();
    const textureIndex = ref => {
      let i = typeof ref === 'number' ? ref : textures.findIndex(t => t.uuid === ref);
      if (i < 0 && /^\d+$/.test(String(ref))) i = Number(ref);
      if (!Number.isInteger(i) || !textures[i]) fail(`模型引用的贴图“${ref}”不存在。`);
      usedTextures.add(i);
      return i;
    };
    let cubeCount = 0;
    for (const node of tree.nodes) for (const e of node.elements) {
      if (e.export === false) continue;
      if (e.type && !['cube','locator'].includes(e.type)) fail(`暂不支持 ${e.type} 元素“${e.name}”。请先在 Blockbench 转为 Bedrock 立方体模型。`);
      if (e.type === 'locator') continue;
      cubeCount++;
      const box = e.box_uv ?? model.meta.box_uv;
      for (const face of Object.values(e.faces || {})) {
        if (face.texture != null) textureIndex(face.texture);
        if (!box && face.rotation) fail('检测到旋转 UV：Bedrock 1.12.0 无法直接保留，请先在 Blockbench 展平 UV 旋转。');
        if (face.material_name) fail('检测到自定义面材质实例，本版仅导出普通实体贴图。');
      }
      if (box && !Object.values(e.faces || {}).some(f => f.texture != null)) textureIndex(0);
    }
    if (!cubeCount) fail('没有可导出的立方体。');
    if (usedTextures.size > 1) fail('同一模型使用了多张贴图。请先在 Blockbench 合并为一张贴图，再导入，避免面贴图丢失。');
    if (!textures.length) fail('模型没有贴图。请先在 Blockbench 添加 PNG 贴图并保存。');
    const selectedIndex = [...usedTextures][0] ?? 0, texture = textures[selectedIndex];
    if (texture.layers_enabled) fail('贴图启用了图层，请先在 Blockbench 合并图层并保存。');
    const image = png(texture.source);
    const uvWidth = finite(texture.uv_width ?? width, '贴图 UV 宽度'), uvHeight = finite(texture.uv_height ?? height, '贴图 UV 高度');
    if (uvWidth <= 0 || uvHeight <= 0) fail('贴图 UV 分辨率无效。');
    const uvScale = [width / uvWidth, height / uvHeight];
    if (textures.length > 1) warnings.push(`仅导出模型实际使用的贴图“${texture.name}”；其余 ${textures.length - 1} 张未使用贴图未输出。`);
    const bones = [], previewCubes = [];
    let radius = 1;
    for (const node of tree.nodes) {
      const g = node.group, origin = vector(g.origin, '骨骼原点'), rotation = vector(g.rotation, '骨骼旋转');
      if (g.scale && vector(g.scale, '骨骼缩放').some(v => v !== 1)) fail(`骨骼“${g.name}”含静态缩放，请先应用缩放。`);
      if (g.bedrock_binding) fail(`骨骼“${g.name}”使用 binding，需要高于 1.12.0 的模型格式。`);
      const bone = {name:g.name, pivot:mirrorPosition(origin)};
      if (node.parent) bone.parent = node.parent.group.name;
      if (rotation.some(Boolean)) bone.rotation = mirrorRotation(rotation);
      if (g.reset) bone.reset = true;
      if (g.mirror_uv && model.meta.box_uv) bone.mirror = true;
      const cubes = [], locators = dict();
      for (const e of node.elements) {
        if (e.export === false) continue;
        if (e.type === 'locator') {
          const locatorName = name(e.name, '定位器名称');
          if (Object.hasOwn(locators, locatorName)) fail(`骨骼“${g.name}”上的定位器名称重复。`);
          const offset = mirrorPosition(vector(e.position ?? e.from, '定位器坐标'));
          const r = mirrorRotation(vector(e.rotation, '定位器旋转'));
          if (e.ignore_inherited_scale) fail('定位器 ignore_inherited_scale 需要更新的模型格式，当前不支持。');
          locators[locatorName] = r.some(Boolean) ? {offset, rotation:r} : offset;
          continue;
        }
        const from = vector(e.from, '立方体起点'), to = vector(e.to, '立方体终点');
        const size = to.map((v,i) => round(v - from[i]));
        if (size.some(v => v < 0)) fail(`立方体“${e.name}”存在负尺寸，请先在 Blockbench 修正。`);
        const cube = {origin:[round(-to[0]),from[1],from[2]], size};
        const r = vector(e.rotation, '立方体旋转'), pivot = vector(e.origin, '立方体原点');
        if (r.some(Boolean)) {cube.pivot = mirrorPosition(pivot); cube.rotation = mirrorRotation(r);}
        const inflate = finite(e.inflate ?? 0, '膨胀值');
        if (inflate) cube.inflate = inflate;
        if (e.box_uv ?? model.meta.box_uv) {
          if (uvScale.some(v => v !== 1)) fail('Box UV 的贴图 UV 尺寸与项目不一致，请在 Blockbench 中统一 UV 分辨率。');
          cube.uv = vector(e.uv_offset, 'Box UV 偏移', [0,0], 2);
          if (Boolean(e.mirror_uv) !== Boolean(bone.mirror)) cube.mirror = Boolean(e.mirror_uv);
        } else {
          cube.uv = dict();
          for (const key of directions) {
            const f = e.faces?.[key];
            if (!f || f.texture === null) continue;
            if (f.texture === undefined) fail(`立方体“${e.name}”的 ${key} 面未分配贴图，请先补全。`);
            const uv = vector(f.uv, '面 UV', [0,0,0,0], 4);
            const top = key === 'up' || key === 'down';
            cube.uv[key] = {
              uv:[round(uv[top ? 2 : 0] * uvScale[0]),round(uv[top ? 3 : 1] * uvScale[1])],
              uv_size:[round((top ? uv[0]-uv[2] : uv[2]-uv[0]) * uvScale[0]), round((top ? uv[1]-uv[3] : uv[3]-uv[1]) * uvScale[1])]
            };
          }
        }
        cubes.push(cube);
        previewCubes.push({cube, node});
        // A rotation-independent sphere bound includes any rest-pose bone rotations.
        let extent = Math.hypot(...from.map((v,i) => Math.max(Math.abs(v-pivot[i]),Math.abs(to[i]-pivot[i])))) + Math.abs(inflate)*2;
        let last = pivot;
        for (let n = node; n; n = n.parent) {
          const p = vector(n.group.origin, '骨骼原点');
          extent += Math.hypot(...p.map((v,i) => v-last[i])); last = p;
        }
        radius = Math.max(radius, extent + Math.hypot(...last));
      }
      if (cubes.length) bone.cubes = cubes;
      if (Object.keys(locators).length) bone.locators = locators;
      bones.push(bone);
    }
    const bound = Math.ceil(radius / 8 + 1);
    const geometry = {format_version:'1.12.0', 'minecraft:geometry':[{description:{identifier:id,texture_width:width,texture_height:height,visible_bounds_width:bound,visible_bounds_height:bound,visible_bounds_offset:[0,0,0]},bones}]};
    const animations = convertAnimations(model, tree, base, warnings);
    if (model.animation_controllers?.length) fail('文件含动画控制器，本版不转换控制器。请在 Blockbench 单独导出控制器后再处理此模型。');
    if (model.display && Object.keys(model.display).length) warnings.push('物品展示视角设置未导出；本版只导出模型、贴图和骨骼动画。');
    const files = [{kind:'model',name:`${base}.geo.json`,data:JSON.stringify(geometry,null,2)+'\n'}];
    if (Object.keys(animations.animations).length) files.push({kind:'animation',name:`${base}.animation.json`,data:JSON.stringify(animations,null,2)+'\n'});
    else warnings.push('源文件没有动画，仅输出模型和贴图。');
    files.push({kind:'texture',name:`${base}.png`,data:image.bytes});
    return {id,base,geometry,animations,files,warnings,image,textureName:texture.name,cubeCount,boneCount:bones.length,animationCount:Object.keys(animations.animations).length};
  }
  function molang(value, fallback = 0) {
    if (value == null || value === '') return fallback;
    if (typeof value === 'number') return finite(value, '动画关键帧');
    if (typeof value !== 'string') fail('动画关键帧不是数值或 Molang 表达式。');
    const s = value.trim();
    if (s && Number.isFinite(Number(s))) return Number(s);
    if (!s) return fallback;
    return s;
  }
  function negate(v) {
    if (typeof v === 'number') return round(-v);
    // Simple expressions can be negated without changing evaluation order.
    // A multi-statement Molang expression needs its return value rewritten.
    if (/;|\breturn\b/.test(v)) fail('动画 X/Y 轴含多语句 Molang，暂不能可靠转换符号；请先改为单个表达式。');
    return `-(${v})`;
  }
  function keyVector(point, channel) {
    const fallback = channel === 'scale' ? 1 : 0;
    const v = ['x','y','z'].map(axis => molang(point?.[axis], fallback));
    if (channel === 'position' || channel === 'rotation') v[0] = negate(v[0]);
    if (channel === 'rotation') v[1] = negate(v[1]);
    return v;
  }
  function timecode(time) {
    const t = finite(time ?? 0, '关键帧时间');
    if (t < 0) fail('动画存在负时间关键帧。');
    const s = String(round(t)); return s.includes('.') ? s : `${s}.0`;
  }
  function compileChannel(frames, channel) {
    const sorted = frames.slice().sort((a,b) => a.time-b.time), output = dict();
    for (let i=0; i<sorted.length; i++) {
      const k = sorted[i], t = timecode(k.time), previous = sorted[i-1];
      const interpolation = k.interpolation || 'linear';
      if (!['linear','catmullrom','step'].includes(interpolation)) fail(`动画含 ${interpolation} 插值，暂不支持，请在 Blockbench 烘焙为线性关键帧后导入。`);
      if (Object.hasOwn(output,t)) fail(`动画 ${channel} 通道在 ${t} 秒有重复关键帧。`);
      const points = k.data_points || [{x:k.x,y:k.y,z:k.z}];
      if (!points.length || points.length > 2) fail('变换关键帧需要 1–2 个数据点。');
      const pre = keyVector(points[0],channel), post = keyVector(points[1] || points[0],channel);
      if (interpolation === 'catmullrom') {
        const includePre = (!previous && k.time > 0) || (previous && previous.interpolation !== 'catmullrom');
        output[t] = includePre ? {pre,post,lerp_mode:'catmullrom'} : {post:pre,lerp_mode:'catmullrom'};
      } else if (points.length > 1) output[t] = {pre,post};
      else if (previous?.interpolation === 'step') {
        const pp = previous.data_points || [previous];
        output[t] = {pre:keyVector(pp[pp.length-1],channel),post};
      } else output[t] = pre;
    }
    return output;
  }
  function convertAnimations(model, tree, base, warnings) {
    const animations = dict();
    if (model.animations != null && !Array.isArray(model.animations)) fail('animations 字段不是数组。');
    for (const a of model.animations || []) {
      let n = name(a.name, '动画名称');
      if (!n.startsWith('animation.')) n = `animation.${base}.${n}`;
      if (!/^animation\.[a-z0-9_]+(?:[.\-][a-z0-9_]+)*$/.test(n)) fail(`动画名称“${a.name}”无效，请使用小写字母、数字、下划线和点。`);
      if (Object.hasOwn(animations,n)) fail(`动画名称“${n}”重复。`);
      const out = {bones:dict()};
      if (a.loop === 'loop') out.loop = true;
      else if (a.loop === 'hold') out.loop = 'hold_on_last_frame';
      else if (a.loop && a.loop !== 'once') fail(`未知动画循环模式：${a.loop}`);
      const length = finite(a.length ?? 0, '动画长度');
      if (length < 0) fail('动画长度不能为负。');
      if (length) out.animation_length = length;
      const maxKeyTime = Object.values(a.animators || {}).reduce((max,animator) => (animator.keyframes || []).reduce((latest,k) => Math.max(latest,k.time ?? 0),max),0);
      if (!length && !maxKeyTime && a.loop !== 'hold') out.loop = true;
      if (a.override) out.override_previous_animation = true;
      for (const property of ['anim_time_update','blend_weight','start_delay','loop_delay']) if (a[property] !== '' && a[property] != null) out[property] = molang(a[property]);
      for (const [uuid, animator] of Object.entries(a.animators || {})) {
        if (!Array.isArray(animator.keyframes ?? [])) fail('动画 keyframes 字段不是数组。');
        const frames = animator.keyframes || [];
        if (frames.some(k => length > 0 && k.time > length)) warnings.push(`动画“${a.name}”有关键帧超出动画长度，已保留原时间。`);
        if (uuid === 'effects' || animator.type === 'effect') {
          for (const k of frames) {
            const fields = {sound:'sound_effects',particle:'particle_effects',timeline:'timeline'};
            const field = fields[k.channel];
            if (!field) fail(`不支持动画效果通道 ${k.channel}。`);
            const t = timecode(k.time), data = k.data_points || [];
            out[field] ||= dict();
            const points = [];
            for (const p of data) {
              if (k.channel === 'timeline') {
                if (p.script?.trim()) points.push(p.script.trim().replace(/;?$/, ';'));
              } else if (p.effect) {
                const effect = {effect:p.effect};
                if (p.locator) effect.locator = p.locator;
                if (k.channel === 'particle') {
                  if (p.script) effect.pre_effect_script = p.script;
                  if (p.bind_to_actor === false) effect.bind_to_actor = false;
                }
                points.push(effect);
              }
            }
            if (points.length) {
              const existing = out[field][t];
              const merged = existing == null ? points : [...(Array.isArray(existing) ? existing : [existing]),...points];
              out[field][t] = merged.length === 1 ? merged[0] : merged;
            }
          }
          warnings.push(`动画“${a.name}”包含效果事件；需要项目已有对应的粒子 / 声音短名称绑定。`);
          continue;
        }
        if (!frames.length && !animator.rotation_global) continue;
        if (animator.type && animator.type !== 'bone') fail(`暂不支持 ${animator.type} 动画通道。`);
        const node = tree.byId.get(uuid) || tree.nodes.find(g => g.group.name === uuid || g.group.name === animator.name);
        if (!node) fail(`动画“${a.name}”引用了不存在的骨骼“${animator.name || uuid}”。`);
        if (Object.hasOwn(out.bones,node.group.name)) fail(`动画“${a.name}”含重复骨骼通道。`);
        const channels = dict();
        for (const k of frames) {
          if (!['position','rotation','scale'].includes(k.channel)) fail(`不支持骨骼动画通道 ${k.channel}。`);
          if (k.quaternion_interpolation) fail('暂不支持四元数插值，请在 Blockbench 烘焙动画后导入。');
          (channels[k.channel] ||= []).push(k);
        }
        const bone = dict();
        for (const [channel, keys] of Object.entries(channels)) bone[channel] = compileChannel(keys,channel);
        if (animator.rotation_global) {
          bone.relative_to = {rotation:'entity'};
          if (!bone.rotation) bone.rotation = [0,0,0.01];
          else for (const value of Object.values(bone.rotation)) if (Array.isArray(value) && value.every(v=>v===0)) value[2] = 0.01;
        }
        out.bones[node.group.name] = bone;
      }
      animations[n] = out;
    }
    return {format_version:'1.8.0', animations};
  }
  root.BBConvert = {parse,convert,identifier,hierarchy,compileChannel,png};
})(globalThis);
