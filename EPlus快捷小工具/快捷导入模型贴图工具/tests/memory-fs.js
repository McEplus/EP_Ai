/* File System Access API test double. All data remains in memory. */
(function(root){
  const enc=new TextEncoder();
  const error=(name,message)=>Object.assign(new Error(message),{name});
  class Directory{
    constructor(name='test-project',parent=null){this.name=name;this.kind='directory';this.parent=parent;this.children=new Map();this.failures=new Set();}
    async getDirectoryHandle(name,options={}){
      const existing=this.children.get(name);
      if(existing&&existing.kind!=='directory')throw error('TypeMismatchError',name);
      if(existing)return existing;
      if(!options.create)throw error('NotFoundError',name);
      const dir=new Directory(name,this);this.children.set(name,dir);return dir;
    }
    async getFileHandle(name,options={}){
      let file=this.children.get(name);
      if(file&&file.kind!=='file')throw error('TypeMismatchError',name);
      if(!file){if(!options.create)throw error('NotFoundError',name);file=new FileHandle(name,this);this.children.set(name,file);}
      return file;
    }
    async removeEntry(name){const node=this.children.get(name);if(!node)throw error('NotFoundError',name);if(node.children?.size)throw error('InvalidModificationError','Not empty');this.children.delete(name);}
    async *entries(){yield* this.children.entries();}
    async requestPermission(){return 'granted';}
    async resolve(node){const parts=[];for(let n=node;n;n=n.parent){if(n===this)return parts.reverse();parts.push(n.name);}return null;}
    async put(path,data){const parts=path.split('/'),name=parts.pop();let dir=this;for(const part of parts)dir=await dir.getDirectoryHandle(part,{create:true});const handle=await dir.getFileHandle(name,{create:true});handle.data=typeof data==='string'?enc.encode(data):new Uint8Array(data);return handle;}
    async read(path){const parts=path.split('/'),name=parts.pop();let dir=this;for(const part of parts)dir=await dir.getDirectoryHandle(part);return (await dir.getFileHandle(name)).data;}
    async paths(prefix=''){const list=[];for(const [name,node]of this.children){const p=prefix?prefix+'/'+name:name;if(node.kind==='file')list.push(p);else list.push(...await node.paths(p));}return list;}
  }
  class FileHandle{
    constructor(name,parent){this.name=name;this.parent=parent;this.kind='file';this.data=new Uint8Array();}
    async getFile(){return new Blob([this.data]);}
    async createWritable(){
      const file=this;let pending;
      return {async write(data){if(file.parent.failures.delete(file.name))throw error('QuotaExceededError','Simulated disk full');pending=typeof data==='string'?enc.encode(data):new Uint8Array(data);},async close(){file.data=pending||new Uint8Array();},async abort(){}};
    }
  }
  root.MemoryDirectory=Directory;
})(globalThis);
