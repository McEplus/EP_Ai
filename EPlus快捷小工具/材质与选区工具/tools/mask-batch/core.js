/* Offline detail-v1 math. PNG decode uses bundled UPNG; encoding preserves hidden RGB. */
function createMaskCore() {
  const directions = [[1,0,0],[0,1,0],[0,0,1],[1,1,0],[1,0,1]];
  const text = new TextEncoder();
  function region(r,g,b) {
    const length = Math.hypot(r,g,b);
    if (!length) return -1;
    for (let i=0;i<5;i++) {
      const d=directions[i];
      if ((r*d[0]+g*d[1]+b*d[2])/(length*Math.sqrt(d[0]+d[1]+d[2])) >= .9999) return i;
    }
    return -1;
  }
  function crc(bytes) {
    let c=0xffffffff;
    for (const b of bytes) {
      c^=b;
      for(let i=0;i<8;i++) c=(c>>>1)^((c&1)?0xedb88320:0);
    }
    return (c^0xffffffff)>>>0;
  }
  function join(parts) {
    const out=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));
    let at=0; for(const p of parts) {out.set(p,at);at+=p.length;} return out;
  }
  function chunk(name,data) {
    const out=new Uint8Array(data.length+12), view=new DataView(out.buffer);
    view.setUint32(0,data.length);out.set(text.encode(name),4);out.set(data,8);
    view.setUint32(out.length-4,crc(out.subarray(4,out.length-4)));return out;
  }
  function info(buffer) {
    const a=new Uint8Array(buffer), v=new DataView(buffer);
    if(a.length<33 || ![137,80,78,71,13,10,26,10].every((b,i)=>a[i]===b)) throw Error('不是有效 PNG');
    const width=v.getUint32(16),height=v.getUint32(20);
    if(!width || !height || width*height>4194304) throw Error('单图超过 4,194,304 像素上限');
    if(a[24]===16) throw Error('请先将 16 位 PNG 转为 8 位');
    let compiled=false;
    for(let p=8;p+12<=a.length;) {
      const len=v.getUint32(p);
      if(p+12+len>a.length) throw Error('PNG 数据不完整');
      const type=String.fromCharCode(...a.subarray(p+4,p+8));
      if(crc(a.subarray(p+4,p+8+len))!==v.getUint32(p+8+len)) throw Error('PNG 校验失败');
      if(type==='acTL') throw Error('暂不处理动画 PNG');
      if(type==='tEXt' && new TextDecoder().decode(a.subarray(p+8,p+8+len))==='EplusMaskVersion\0detail-v1') compiled=true;
      p+=len+12;
    }
    return {width,height,compiled};
  }
  function decode(buffer) {
    const meta=info(buffer), decoded=UPNG.decode(buffer);
    return {...meta,rgba:new Uint8Array(UPNG.toRGBA8(decoded)[0])};
  }
  function encode(width,height,rgba) {
    const ihdr=new Uint8Array(13),v=new DataView(ihdr.buffer);
    v.setUint32(0,width);v.setUint32(4,height);ihdr[8]=8;ihdr[9]=6;
    const raw=new Uint8Array(height*(width*4+1));
    for(let y=0;y<height;y++) raw.set(rgba.subarray(y*width*4,(y+1)*width*4),y*(width*4+1)+1);
    return join([new Uint8Array([137,80,78,71,13,10,26,10]),chunk('IHDR',ihdr),
      chunk('tEXt',text.encode('EplusMaskVersion\0detail-v1')),chunk('IDAT',pako.deflate(raw,{level:9})),chunk('IEND',new Uint8Array())]);
  }
  function roundEven(x) {const f=Math.floor(x);return x-f===.5?f+(f%2):Math.round(x);}
  function build(source,mask,progress=()=>{}) {
    const w=mask.width,h=mask.height,n=w*h, m=mask.rgba;
    const src=new Uint8Array(n*4),ids=new Int8Array(n),logs=new Float64Array(n),labels=new Int32Array(n),groups=[[],[],[],[],[]];
    labels.fill(-1);
    for(let y=0;y<h;y++) for(let x=0;x<w;x++) {
      const p=y*w+x,q=(Math.min(source.height-1,Math.floor((y+.5)*source.height/h))*source.width+Math.min(source.width-1,Math.floor((x+.5)*source.width/w)))*4;
      src.set(source.rgba.subarray(q,q+4),p*4);
      ids[p]=region(m[p*4],m[p*4+1],m[p*4+2]);
      logs[p]=Math.log(Math.max((src[p*4]*.299+src[p*4+1]*.587+src[p*4+2]*.114)/255,1/255));
      if(ids[p]>=0&&src[p*4+3]) groups[ids[p]].push(logs[p]);
    }
    const medians=groups.map(a=>{a.sort((a,b)=>a-b);return a.length?(a[(a.length-1)>>1]+a[a.length>>1])/2:null;});
    const stack=new Int32Array(n);let component=0,selected=0;
    for(let start=0;start<n;start++) {
      if(ids[start]<0||!src[start*4+3]||labels[start]>=0) continue;
      labels[start]=component;let top=1;stack[0]=start;
      while(top) {
        const p=stack[--top],x=p%w,y=Math.floor(p/w);
        for(const q of [x?p-1:-1,x<w-1?p+1:-1,y?p-w:-1,y<h-1?p+w:-1]) {
          if(q>=0&&labels[q]<0&&ids[q]===ids[p]&&src[q*4+3]) {labels[q]=component;stack[top++]=q;}
        }
      }
      component++;
    }
    const kernel=[];
    for(let dy=-6;dy<=6;dy++) for(let dx=-6;dx<=6;dx++) kernel.push([dx,dy,Math.exp(-(dx*dx+dy*dy)/8)]);
    const result=new Uint8Array(m);
    for(let y=0;y<h;y++) {
      for(let x=0;x<w;x++) {
        const p=y*w+x,r=ids[p];if(r<0) continue;
        selected++;let total=0,weight=0;
        if(labels[p]>=0) for(const [dx,dy,v] of kernel) {
          const nx=x+dx,ny=y+dy;
          if(nx>=0&&nx<w&&ny>=0&&ny<h) {const q=ny*w+nx;if(labels[q]===labels[p]) {total+=logs[q]*v;weight+=v;}}
        }
        const local=weight?total/weight:logs[p],median=medians[r]===null?local:medians[r];
        const ratio=Math.exp(logs[p]-(.8*local+.2*median));
        const detail=ratio<=1?.9*ratio:.9+.09*(1-Math.exp(-3*(ratio-1)));
        const level=Math.max(8,Math.min(252,roundEven(detail*255)));
        for(let c=0;c<3;c++) result[p*4+c]=level*directions[r][c];
      }
      if(y%16===0) progress(y/h);
    }
    return {rgba:result,width:w,height:h,selected,resampled:source.width!==w||source.height!==h};
  }
  return {decode,encode,build,info,region};
}
