from __future__ import print_function

import json
import re

from _common import json_print, project_root, read_text, relative, resource_ui_root


TEXTURE_PATTERN = re.compile(r'"texture"\s*:\s*"(textures/ui/[^"$]+)"')
INHERIT_PATTERN = re.compile(r'"[^"@]+@([A-Za-z0-9_]+)\.[^"]+"')
EXTERNAL_NAMESPACES = {"common", "common_selection_wheels", "pause"}


def validate_ui_json():
    ui_root = resource_ui_root()
    files = sorted(path for path in ui_root.glob("*.json") if path.name != "_ui_defs.json")
    parsed = {}
    parse_errors = []
    namespaces = set(EXTERNAL_NAMESPACES)
    for path in files:
        try:
            data = json.loads(read_text(path))
            parsed[path] = data
            namespace = data.get("namespace")
            if namespace:
                namespaces.add(namespace)
        except Exception as error:
            parse_errors.append({"file": relative(path), "error": str(error)})

    defs_path = ui_root / "_ui_defs.json"
    defs_data = json.loads(read_text(defs_path))
    declared = set(item.replace("ui/", "") for item in defs_data.get("ui_defs", []))
    existing = set(path.name for path in files)
    missing_declared_files = sorted(declared - existing)
    undeclared_files = sorted(existing - declared)

    external_or_missing_textures = []
    unresolved_namespaces = []
    resource_root = project_root() / "src" / "SwordSoul_NewERA_R"
    for path in parsed:
        text = read_text(path)
        for texture in sorted(set(TEXTURE_PATTERN.findall(text))):
            texture_path = resource_root / (texture + ".png")
            if not texture_path.exists():
                external_or_missing_textures.append({
                    "file": relative(path),
                    "texture": texture,
                    "status": "not_in_project_resource_pack"
                })
        for namespace in sorted(set(INHERIT_PATTERN.findall(text))):
            if namespace not in namespaces:
                unresolved_namespaces.append({"file": relative(path), "namespace": namespace})

    return {
        "files_checked": len(files),
        "parse_errors": parse_errors,
        "missing_declared_files": missing_declared_files,
        "undeclared_files": undeclared_files,
        "external_or_missing_texture_references": external_or_missing_textures,
        "unresolved_namespaces": unresolved_namespaces,
    }


def main():
    json_print(validate_ui_json())


if __name__ == "__main__":
    main()
