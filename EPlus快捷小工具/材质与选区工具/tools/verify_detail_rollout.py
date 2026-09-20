"""Check every migrated mask against its authored backup and current references."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from audit_pbr_masks import ROOT, WORKSPACES, REPORT_ROOT, read_json, pairs
from pbr_mask_core import region


def main():
    rows=read_json(REPORT_ROOT/'rollout.json')
    checked=0;errors=[];projects={}
    for row in rows:
        if row['status'] not in ('converted','already-compiled'):
            continue
        mask=Path(row['mask']);root=Path(row['root']);pack=Path(row['pack'])
        backup=root/'tools/pbr-mask-sources'/pack.name/mask.relative_to(pack)
        try:
            image=Image.open(mask)
            assert image.info.get('EplusMaskVersion')=='detail-v1'
            compiled=image.convert('RGBA')
            assert list(compiled.size)==row['size']
            if backup.is_file():
                original=Image.open(backup).convert('RGBA')
                assert compiled.size==original.size
                assert compiled.getchannel('A').tobytes()==original.getchannel('A').tobytes()
                assert [region(p[:3]) for p in compiled.getdata()]==[region(p[:3]) for p in original.getdata()]
                if row.get('source_sha256'):
                    assert hashlib.sha256(backup.read_bytes()).hexdigest()==row['source_sha256']
            else:
                assert row.get('output_sha256'), 'No historical output hash available'
                assert hashlib.sha256(mask.read_bytes()).hexdigest()==row['output_sha256'], 'Runtime mask changed since verified rollout'
            checked+=1;projects[row['project']]=projects.get(row['project'],0)+1
        except Exception as e:errors.append([str(mask),str(e)])
    known={r['mask']:r for r in rows};same_as_base=[];uncompiled=[]
    packs={pack for workspace in WORKSPACES.glob('EP*.code-workspace') for folder in read_json(workspace)['folders']
           for pack in (workspace.parent/folder['path']).resolve().glob('resource*')}
    for pack in sorted(packs):
        for config in pack.glob('modconfigs/**/*.json'):
            for alias,path in pairs(read_json(config)):
                file=pack/(path+'.png')
                if file.is_file() and not path.endswith('_color_mask'):
                    same_as_base.append([str(config),alias,path])
                elif str(file) in known and known[str(file)]['status']=='missing-base':
                    uncompiled.append([str(config),path])
    assert not (ROOT/'resource_pack_EP_JXK_0/textures/pbr/detail/basp_tf_color_mask.png').exists()
    report=dict(verified=checked,projects=projects,errors=errors,nonstandard_mask_references=same_as_base,uncompiled_references=uncompiled)
    (REPORT_ROOT/'rollout-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:len(v) if isinstance(v,list) else v for k,v in report.items() if k!='projects'},ensure_ascii=True))
    assert not errors and not uncompiled


if __name__=='__main__':main()
