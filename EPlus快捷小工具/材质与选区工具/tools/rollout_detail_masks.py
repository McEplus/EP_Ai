"""Inspect/apply mask pairs; use Git for backups, no per-addon backup folders."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from PIL import Image, PngImagePlugin
from audit_pbr_masks import ROOT, WORKSPACES, REPORT_ROOT, read_json
from pbr_mask_core import build

TAG = 'EplusMaskVersion'
VERSION = 'detail-v1'


def inventory():
    rows = []
    for workspace in sorted(WORKSPACES.glob('EP*.code-workspace')):
        for folder in read_json(workspace)['folders']:
            root = (workspace.parent / folder['path']).resolve()
            for pack in root.glob('resource*'):
                for mask in pack.glob('textures/**/*_color_mask.png'):
                    if mask == ROOT/'resource_pack_EP_JXK_0/textures/pbr/detail/basp_tf_color_mask.png':
                        continue
                    base = mask.with_name(mask.name[:-15] + '.png')
                    # The standard suffix includes the .png extension (15 chars).
                    row = dict(project=workspace.stem, root=str(root), pack=str(pack),
                               mask=str(mask), base=str(base), status='ready')
                    with Image.open(mask) as image:
                        row['size'] = list(image.size)
                        row['compiled'] = image.info.get(TAG) == VERSION
                    if not base.is_file():
                        row['status'] = 'missing-base'
                    else:
                        with Image.open(base) as image:
                            if list(image.size) != row['size']:
                                row['status'] = 'ready-uv-resample'
                                row['base_size'] = list(image.size)
                    rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--rebuild', action='store_true', help='Rebuild using current base pixels and mask region identity')
    args = parser.parse_args()
    rows = inventory()
    stats = {}
    for row in rows:
        label = row['project']
        stats.setdefault(label, {})
        stats[label][row['status']] = stats[label].get(row['status'], 0) + 1
    print(json.dumps(stats, ensure_ascii=True, indent=2), flush=True)
    if args.apply:
        for index, row in enumerate(rows):
            if row['status'] not in ('ready', 'ready-uv-resample'):
                continue
            root, pack, mask = (Path(row[key]).resolve() for key in ('root','pack','mask'))
            assert mask.is_relative_to(pack) and pack.is_relative_to(root)
            with Image.open(mask) as current:
                compiled = current.info.get(TAG) == VERSION
            row['output_sha256'] = hashlib.sha256(mask.read_bytes()).hexdigest()
            if compiled and not args.rebuild:
                row['status'] = 'already-compiled'
                continue
            original = mask.read_bytes()
            row['source_sha256'] = hashlib.sha256(original).hexdigest()
            # build() uses only region identity and alpha from the mask, so an
            # existing compiled mask can be rebuilt without a separate backup.
            with Image.open(row['base']) as source, Image.open(mask) as authored:
                result, _, _, _ = build(source, authored)
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text(TAG, VERSION)
            metadata.add_text('EplusMaskSourceSHA256', row['source_sha256'])
            result.save(mask, pnginfo=metadata, optimize=True)
            row['status'] = 'converted'
            row['output_sha256'] = hashlib.sha256(mask.read_bytes()).hexdigest()
            if index % 20 == 0:
                print('processed %d/%d' % (index+1, len(rows)), flush=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report = REPORT_ROOT/'rollout.json'
    report.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print('total=%d unresolved=%d' % (len(rows), sum(r['status'] == 'missing-base' for r in rows)), flush=True)


if __name__ == '__main__':
    main()
