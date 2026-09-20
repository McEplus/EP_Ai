# -*- coding: utf-8 -*-
import ast
import base64
import copy
import json
import os
import sys
import unittest
import zlib

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(TOOL_ROOT, 'tools'))
from tool_paths import MOD_ROOT
ROOT = MOD_ROOT
sys.path.insert(0, os.path.join(ROOT, 'behavior_pack_EP_JXK_0'))
from EpJxkScript.modCommon.pbrMaskRender import (
    ApplyMaskRender, HasMaskTexture, GetTintMask, ResolvePartMaskRender, MISSING_MASKS)


def load_methods(relative, names, namespace):
    path = os.path.join(ROOT, 'behavior_pack_EP_JXK_0/EpJxkScript', relative)
    with open(path, 'rb') as f:
        tree = ast.parse(f.read(), path)
    methods = {}
    nodes = [node for cls in tree.body if isinstance(cls, ast.ClassDef) for node in cls.body]
    for node in nodes:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            module = ast.Module(body=[node])
            exec(compile(module, path, 'exec'), namespace)
            methods[node.name] = namespace[node.name]
    assert set(methods) == set(names), set(names) - set(methods)
    return type('Methods', (object,), methods)


class Uniforms(object):
    def __init__(self):
        self.values = {1: (0, 0, 0, 0), 2: (0, 0, 0, 7), 3: (12, 13, 14, 15), 4: (0, 0, 0, 0)}

    def GetEntityExtraUniforms(self, index):
        return self.values[index]

    def SetEntityExtraUniforms(self, index, values):
        self.values[index] = values


class MaskTests(unittest.TestCase):
    def test_default_binding_and_idempotence(self):
        render = {'Texture': [['ep_item', 'textures/models/basp_tf']],
                  'RenderController': [['controller.render.ep_item', 'condition'], ['controller.render.ep_arm', '']]}
        self.assertTrue(ApplyMaskRender(render))
        self.assertEqual(render['RenderController'][0], ['controller.render.ep_item_color', 'condition'])
        self.assertIn(['ep_item_color_mask', 'textures/models/basp_tf_color_mask'], render['Texture'])
        before = copy.deepcopy(render)
        ApplyMaskRender(render)
        self.assertEqual(render, before)

    def test_base_texture_cannot_be_used_as_mask(self):
        render = {'Texture': [['ep_item', 'textures/models/an94'], ['ep_item_color_mask', 'textures/models/an94']],
                  'RenderController': [['controller.render.ep_item_color', '']]}
        self.assertFalse(ApplyMaskRender(render))
        self.assertEqual(render['RenderController'][0][0], 'controller.render.ep_item')
        self.assertEqual(len(render['Texture']), 1)

    def test_different_skin_does_not_inherit_default_mask(self):
        render = {'Texture': [['ep_item', 'textures/other_skin']],
                  'RenderController': [['controller.render.ep_item', '']]}
        candidate = {'Texture': [['ep_item', 'textures/models/basp_tf'],
                                 ['ep_item_color_mask', 'textures/models/basp_tf_color_mask']]}
        self.assertFalse(ApplyMaskRender(render, candidate))
        self.assertEqual(len(render['Texture']), 1)

    def test_missing_mask_falls_back(self):
        for path in MISSING_MASKS:
            render = {'Texture': [['ep_item', path[:-11]], ['ep_item_color_mask', path]],
                      'RenderController': [['controller.render.ep_item_color', '']]}
            self.assertFalse(ApplyMaskRender(render))
            self.assertEqual(render['RenderController'][0][0], 'controller.render.ep_item')
            self.assertEqual(len(render['Texture']), 1)

    def test_barrel_texture_change_drops_stale_mask_but_keeps_attachment_controller(self):
        candidate = {'Texture': [['ep_item', 'textures/models/basp_tf'],
                                 ['ep_item_color_mask', 'textures/models/basp_tf_color_mask']]}
        render = {'Texture': [['ep_item', 'textures/unmasked_barrel'], candidate['Texture'][1]],
                  'RenderController': [['controller.render.ep_item_color', ''],
                                       ['controller.render.ep_up_slider_color', '']]}
        ApplyMaskRender(render, candidate)
        self.assertEqual(render['RenderController'][0][0], 'controller.render.ep_item')
        self.assertEqual(render['RenderController'][1][0], 'controller.render.ep_up_slider_color')
        self.assertEqual(len(render['Texture']), 1)

    def test_attachment_uses_own_mask(self):
        render = ResolvePartMaskRender({}, 'textures/models/parts/slider/slider_a1', 'ep_up_slider')
        self.assertTrue(HasMaskTexture(render))
        self.assertEqual(render['Texture'][0][0], 'ep_up_slider_color_mask')

    def test_quality_modes(self):
        names = ['_GetRenderMaterialName', '_UseFastRenderMode', '_UseBalanceRenderMode']
        client = load_methods('EpJxkScriptClientSystem.py', names, {})()
        for choice, expected in [('0', 'ep_color_mask'), ('1', 'ep_color_mask_fast'),
                                 ('2', 'ep_color_mask_balance')]:
            client.nowSetData = {'p0_property_choice': choice}
            self.assertEqual(client._GetRenderMaterialName('ep_color_mask'), expected)

    def test_legacy_black_and_explicit_black(self):
        self.assertEqual(GetTintMask({}), 0)
        self.assertEqual(GetTintMask({'paint': True, 'red': [0, 0, 0], 'blue': [1, 0, 0]}), 4)
        self.assertEqual(GetTintMask({'paint': True, 'tint_mask': 1, 'red': [0, 0, 0]}), 1)
        self.assertEqual(GetTintMask({'tint_mask': {'__value__': 16}}), 16)

    def test_uniform_roundtrip_and_fire_isolation(self):
        uniforms = Uniforms()
        names = ['_ClampPbrValue', '_CleanPbrList', '_PackPbrValue', 'SetEpSkinPbr', 'skin_init']
        cls = load_methods('EpJxkScriptClientSystem.py', names, dict(ActorRenderComp=uniforms))
        client = cls()
        values = [[1, 23, 56, 100], [100, 0, 0, 1], [33, 66, 25, 75], [0, 0, 0, 0], [80, 90, 60, 70]]
        client.SetEpSkinPbr(values, 17)
        packed = list(uniforms.values[4]) + [uniforms.values[2][1]]
        for source, value in zip(values, packed):
            self.assertLessEqual(value, 16777215)
            for i, expected in enumerate(source):
                actual = (int(value) // (64 ** i)) % 64 * 100.0 / 63
                self.assertLessEqual(abs(actual - expected), 0.8)
        self.assertEqual(uniforms.values[2][2], 17)
        self.assertEqual(uniforms.values[3], (12, 13, 14, 15))
        client.skin_init()
        self.assertEqual(uniforms.values[2], (0, 0, 0, 0))
        self.assertEqual(uniforms.values[3], (12, 13, 14, 15))

    def test_programmatic_slider_changes_do_not_overwrite_regions(self):
        names = ['SetPbrSliders', 'OnPbrSlider', '_ReadPbrSliders']
        cls = load_methods('uiScript/epGunParts.py', names, dict(CUSTOM_PBR_SLOT_COUNT=5))
        ui = cls()
        ui.customs_color_index = 2
        ui.customs_pbr_list = [[i, i+1, i+2, i+3] for i in range(5)]
        ui._CleanCustomPbrList = lambda x: copy.deepcopy(x)
        ui._setting_pbr_sliders = False
        class Slider(object):
            def SetSliderValue(self, value):
                ui.OnPbrSlider(value, True, None)
        ui.Ui = dict((key, Slider()) for key in ('metal_slider', 'rough_slider', 'glass_slider', 'colorful_slider'))
        before = copy.deepcopy(ui.customs_pbr_list)
        ui.SetPbrSliders(2)
        self.assertEqual(before, ui.customs_pbr_list)
        self.assertFalse(ui._setting_pbr_sliders)

    def test_skin_code_preserves_reserved_values_and_tint(self):
        names = ['_EncodeCustomSkinCode', '_UnpackMinCustomSkinData', '_CleanCustomPbrList',
                 '_DefaultCustomPbrList', '_ClampCustomPbrValue', '_ClampSkinCodeColor']
        namespace = dict(base64=base64, json=json, zlib=zlib, GetTintMask=GetTintMask,
                         RANGE=xrange, CUSTOM_PBR_SLOT_COUNT=5, CUSTOM_PBR_VALUE_COUNT=4,
                         CUSTOM_SKIN_MIN_CODE_PREFIX='TEST:', TEXT_TYPE=unicode)
        cls = load_methods('uiScript/epGunParts.py', names, namespace)
        ui = cls()
        ui._TextToSkinCodeBytes = lambda text: text.encode('utf-8')
        ui._SkinCodeBytesToText = lambda value: str(value).decode('utf-8')
        ui._MaskSkinCodeBytes = lambda value: str(value)
        ui._BuildMinCustomSkinData = lambda name, item: dict(name=name, itemName=item, paint=True)
        skin = dict(name='sample', itemName='ep_jxk:basp_tf', paint=True, tint_mask=4,
                    pbr=[[10, 20, 30, 40], [0, 1, 99, 100], [1, 2, 3, 4], [50]*4, [0]*4])
        skin.update((key, [0, 0, 0]) for key in ('red', 'green', 'blue', 'yellow', 'magenta'))
        code = ui._EncodeCustomSkinCode(skin)[5:]
        raw = bytearray(base64.urlsafe_b64decode(code + '=' * ((-len(code)) % 4)))
        restored = ui._UnpackMinCustomSkinData(raw)
        self.assertEqual(restored['pbr'], skin['pbr'])
        self.assertEqual(restored['tint_mask'], 4)
        old = ui._UnpackMinCustomSkinData(raw[:-1])
        self.assertEqual(old['pbr'], skin['pbr'])
        self.assertEqual(GetTintMask(old), 0)
        oldest = ui._UnpackMinCustomSkinData(raw[:-21])
        self.assertEqual(oldest['pbr'], [[0]*4 for _ in range(5)])


if __name__ == '__main__':
    unittest.main()
