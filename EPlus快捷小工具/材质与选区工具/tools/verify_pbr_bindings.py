"""Verify upgraded render bindings against the installed addon resources."""
import copy
import json
import sys
from pathlib import Path
from audit_pbr_masks import ROOT, REPORT_ROOT, read_json

sys.path.insert(0, str(ROOT / 'behavior_pack_EP_JXK_0'))
from EpJxkScript.modCommon.pbrMaskRender import ApplyMaskRender, ResolvePartMaskRender, HasMaskTexture


def objects(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from objects(value)


def main():
    summary = read_json(REPORT_ROOT / 'summary.json')
    roots = [Path(path) for path in summary['roots']]
    controllers = set()
    for root in roots:
        for file in root.glob('resource*/render_controllers/**/*.json'):
            try:
                controllers.update(read_json(file).get('render_controllers', {}))
            except ValueError:
                pass  # Unrelated legacy controller JSON is outside this audit.
    changed, parts, failures = [], 0, []
    for root in roots:
        for file in root.glob('resource*/modconfigs/**/*.json'):
            for obj in objects(read_json(file)):
                if 'Texture' in obj and 'RenderController' in obj:
                    render = copy.deepcopy(obj)
                    ApplyMaskRender(render, render.get('DefaultSkinRender'))
                    old = set(item[0] for item in obj['RenderController'])
                    added = set(item[0] for item in render['RenderController']) - old
                    if added:
                        changed.append([str(file), sorted(added)])
                        for name in added:
                            if name not in controllers:
                                failures.append([str(file), name])
                if isinstance(obj.get('modelImage'), str):
                    resolved = ResolvePartMaskRender(obj.get('paintRender'), obj['modelImage'], 'ep_part')
                    parts += bool(HasMaskTexture(resolved))
    result = dict(upgraded_render_definitions=len(changed), mask_capable_parts=parts,
                  missing_controllers=failures, upgraded=changed)
    (REPORT_ROOT / 'bindings.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('upgraded=%d parts=%d missing_controllers=%d' % (len(changed), parts, len(failures)))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
