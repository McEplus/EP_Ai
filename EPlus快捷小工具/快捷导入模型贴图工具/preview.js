/* Small orthographic Canvas renderer; does not affect exported assets. */
(function(root){
  'use strict';
  const add=(a,b)=>a.map((n,i)=>n+b[i]), sub=(a,b)=>a.map((n,i)=>n-b[i]);
  function rotate(p,angles){
    let [x,y,z]=p;
    // Bedrock rest pose: X, then Y, then Z.
    for(let axis=0;axis<3;axis++){
      const angle=(angles?.[axis]||0)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);
      if(axis===0)[y,z]=[y*c-z*s,y*s+z*c];
      if(axis===1)[x,z]=[x*c+z*s,-x*s+z*c];
      if(axis===2)[x,y]=[x*c-y*s,x*s+y*c];
    }
    return [x,y,z];
  }
  function around(p,pivot,angles){return add(rotate(sub(p,pivot),angles),pivot);}
  class BBPreview{
    constructor(canvas){
      this.canvas=canvas;this.ctx=canvas.getContext('2d');this.faces=[];this.yaw=-35;this.pitch=-18;this.zoom=1;this.serial=0;
      let pointer;
      canvas.addEventListener('pointerdown',e=>{pointer=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
      canvas.addEventListener('pointermove',e=>{if(!pointer)return;this.yaw+=(e.clientX-pointer[0])*.5;this.pitch=Math.max(-85,Math.min(85,this.pitch+(e.clientY-pointer[1])*.5));pointer=[e.clientX,e.clientY];this.draw();});
      canvas.addEventListener('pointerup',()=>pointer=null);canvas.addEventListener('pointercancel',()=>pointer=null);
      canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom=Math.max(.25,Math.min(6,this.zoom*Math.exp(-e.deltaY*.001)));this.draw();},{passive:false});
      new ResizeObserver(()=>this.draw()).observe(canvas);
    }
    reset(){this.yaw=-35;this.pitch=-18;this.zoom=1;this.draw();}
    clear(){this.serial++;this.faces=[];this.draw();}
    async load(result){
      const serial=++this.serial, image=new Image();image.src=result.image.source;
      try{await image.decode();}catch(_){this.clear();return;}
      if(serial!==this.serial)return;
      this.image=image;this.description=result.geometry['minecraft:geometry'][0].description;
      const bones=result.geometry['minecraft:geometry'][0].bones, byName=new Map(bones.map(b=>[b.name,b]));this.faces=[];
      const all=[];
      for(const bone of bones)for(const cube of bone.cubes||[]){
        const inflate=cube.inflate||0, [x,y,z]=cube.origin.map(n=>n-inflate),[w,h,d]=cube.size.map(n=>n+inflate*2);
        const verts=[[x,y,z],[x+w,y,z],[x+w,y+h,z],[x,y+h,z],[x,y,z+d],[x+w,y,z+d],[x+w,y+h,z+d],[x,y+h,z+d]].map(v=>{
          if(cube.rotation)v=around(v,cube.pivot||[0,0,0],cube.rotation);
          for(let b=bone;b;b=byName.get(b.parent))if(b.rotation)v=around(v,b.pivot||[0,0,0],b.rotation);
          all.push(v);return v;
        });
        const indices={north:[3,2,1,0],south:[6,7,4,5],west:[7,3,0,4],east:[2,6,5,1],up:[7,6,2,3],down:[0,1,5,4]};
        let uv=cube.uv;
        if(Array.isArray(uv)){
          const [u,v]=uv,[sx,sy,sz]=cube.size;
          uv={west:{uv:[u,v+sz],uv_size:[sz,sy]},north:{uv:[u+sz,v+sz],uv_size:[sx,sy]},east:{uv:[u+sz+sx,v+sz],uv_size:[sz,sy]},south:{uv:[u+2*sz+sx,v+sz],uv_size:[sx,sy]},up:{uv:[u+sz+sx,v+sz],uv_size:[-sx,-sz]},down:{uv:[u+sz+2*sx,v],uv_size:[-sx,sz]}};
          if(cube.mirror??bone.mirror){[uv.east,uv.west]=[uv.west,uv.east];for(const face of Object.values(uv)){face.uv[0]+=face.uv_size[0];face.uv_size[0]*=-1;}}
        }
        for(const [name,index] of Object.entries(indices))if(uv[name])this.faces.push({points:index.map(i=>verts[i]),uv:uv[name],shade:{north:.11,south:.08,west:.22,east:.14,up:0,down:.3}[name]});
      }
      const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
      for(const v of all)for(let i=0;i<3;i++){min[i]=Math.min(min[i],v[i]);max[i]=Math.max(max[i],v[i]);}
      this.center=min.map((v,i)=>(v+max[i])/2);this.extent=Math.max(...max.map((v,i)=>v-min[i]),1);this.reset();
    }
    draw(){
      const rect=this.canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
      const ratio=Math.min(devicePixelRatio||1,2),w=rect.width,h=rect.height;
      this.canvas.width=Math.round(w*ratio);this.canvas.height=Math.round(h*ratio);
      const ctx=this.ctx;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,w,h);
      ctx.strokeStyle='#8ea3b012';ctx.lineWidth=1;
      for(let i=0;i<w;i+=32){ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i,h);ctx.stroke();}
      for(let i=0;i<h;i+=32){ctx.beginPath();ctx.moveTo(0,i);ctx.lineTo(w,i);ctx.stroke();}
      if(!this.faces.length){ctx.fillStyle='#7e929e';ctx.font='12px Segoe UI';ctx.textAlign='center';ctx.fillText('添加并选择模型后显示预览',w/2,h/2);return;}
      const scale=Math.min(w*.7,h*.7)/this.extent*this.zoom;
      const project=p=>{let q=sub(p,this.center);q=rotate(q,[0,this.yaw,0]);q=rotate(q,[this.pitch,0,0]);return [w/2+q[0]*scale,h/2-q[1]*scale,q[2]];};
      const faces=this.faces.map(f=>({...f,points:f.points.map(project)})).sort((a,b)=>a.points.reduce((s,p)=>s+p[2],0)-b.points.reduce((s,p)=>s+p[2],0));
      ctx.imageSmoothingEnabled=false;
      for(const face of faces){
        const p=face.points;
        const [u,v]=face.uv.uv,[su,sv]=face.uv.uv_size;
        const tw=this.description.texture_width,th=this.description.texture_height;
        const coords=[[u,v],[u+su,v],[u+su,v+sv],[u,v+sv]].map(uv=>[uv[0]/tw*this.image.width,uv[1]/th*this.image.height]);
        this.triangle([p[0],p[1],p[2]],[coords[0],coords[1],coords[2]]);
        this.triangle([p[0],p[2],p[3]],[coords[0],coords[2],coords[3]]);
        // Keep alpha holes transparent: shading is omitted rather than painting the whole face.
      }
    }
    triangle(points,uv){
      const [a,b,c]=uv,[p,q,r]=points;
      const denominator=(b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]);if(Math.abs(denominator)<1e-9)return;
      const sx=((q[0]-p[0])*(c[1]-a[1])-(r[0]-p[0])*(b[1]-a[1]))/denominator;
      const sy=((q[1]-p[1])*(c[1]-a[1])-(r[1]-p[1])*(b[1]-a[1]))/denominator;
      const tx=((r[0]-p[0])*(b[0]-a[0])-(q[0]-p[0])*(c[0]-a[0]))/denominator;
      const ty=((r[1]-p[1])*(b[0]-a[0])-(q[1]-p[1])*(c[0]-a[0]))/denominator;
      const ctx=this.ctx;ctx.save();ctx.beginPath();ctx.moveTo(...p.slice(0,2));ctx.lineTo(...q.slice(0,2));ctx.lineTo(...r.slice(0,2));ctx.closePath();ctx.clip();
      ctx.transform(sx,sy,tx,ty,p[0]-sx*a[0]-tx*a[1],p[1]-sy*a[0]-ty*a[1]);ctx.drawImage(this.image,0,0);ctx.restore();
    }
  }
  root.BBPreview=BBPreview;
})(globalThis);
