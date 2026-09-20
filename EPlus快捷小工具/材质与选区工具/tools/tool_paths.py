# -*- coding: utf-8 -*-
"""Paths for the external material toolkit (Python 2.7+)."""
import io
import json
import os

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with io.open(os.path.join(TOOL_ROOT, 'tool-settings.json'), encoding='utf-8-sig') as stream:
    SETTINGS = json.load(stream)
MOD_ROOT = os.environ.get('EPLUS_MOD_ROOT', SETTINGS['mod_root'])
WORKSPACE_DIR = os.environ.get('EPLUS_WORKSPACE_DIR', SETTINGS['workspace_dir'])
if not os.path.isdir(os.path.join(MOD_ROOT, 'behavior_pack_EP_JXK_0')):
    raise RuntimeError('Set mod_root in tool-settings.json to the armory addon directory')
