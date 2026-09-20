# 军械库近战自定义伤害设置 SkillAgent 经验

## 核心结论

EP 军工近战包接入自定义伤害时，不能只按 `ep_jg_table_编号.json` 里直接列出的武器生成设置项。部分近战武器通过 `bind` 复用基础近战配置，再用自己的 `data` 覆盖伤害、等级、名称等字段；这些 bind 变体也必须进入设置。

正确流程是：以各包 `ep_jg_table_编号.json` 的 `melee_table` 作为分类来源，以主包 `ep_jg_table_0.json` 的 `melee_table_list` 映射中文分类名；直接近战和 bind 到近战基础武器的变体都生成 `danger` 设置项；分类内按 `gun_level` 从高到低排序。

## 可沉淀成的 Skill 名称

`modsdk-ep-armory-melee-damage-settings`

## 建议触发场景

当用户提出以下需求时，应使用这套经验：

- 给 EP 军工近战包新增或扩展自定义伤害设置。
- 处理 `EP军工4_求生之路`、`EP军工5_暗影突袭`、`EP军工11_LR堑壕战术`、`EP军工14_APX传家宝` 或其它包含近战的 EP 军工包。
- 生成 `resource_pack_*/modconfigs/EP_SET_DATA/ep_gun_set_data_编号.json` 和 `canvas/ep_gun_编号_setting.json`。
- 修复设置伤害不生效、切换武器后伤害回到配置值、配件加伤无法叠加、bind 变体武器缺失等问题。

## SkillAgent 的 SKILL.md 草案

可以把下面内容复制成一个 Codex Skill 的 `SKILL.md`。

```markdown
---
name: modsdk-ep-armory-melee-damage-settings
description: Add or repair custom melee damage settings for EP Armory / EP军工 NetEase ModSDK weapon packs, including melee package setting bridges, ep_jg_table category mapping, bind-variant discovery, setting JSON generation, and main armory melee damage application order.
---

# EP Armory Melee Damage Settings

Use this skill when adding, expanding, or debugging custom melee damage settings for EP 军工 / 军械库 NetEase ModSDK packs.

## Hard Constraints

- NetEase ModSDK runs Python 2.7. Do not use f-strings, type hints, async/await, or Python 3-only APIs.
- Before changing ModSDK API or event usage, check the local ModSDK docs. Do not guess event parameter names.
- Preserve client/server separation. Settings bridge systems should only sync through the existing setting system.
- Do not hand-edit unrelated pack files or revert existing user changes.
- For files outside the current writable workspace, request approval before writing.

## Important Files

Main armory package:

- `behavior_pack_EP_JXK_0/EpJxkScript/modCommon/modConfig.py`
- `behavior_pack_EP_JXK_0/EpJxkScript/EpJxkScriptClientSystem.py`
- `behavior_pack_EP_JXK_0/EpJxkScript/uiScript/epGun.py`
- `behavior_pack_EP_JXK_0/EpJxkScript/uiScript/epGunParts.py`
- `behavior_pack_EP_JXK_0/EpJxkScript/uiScript/epWeaponTable.py`
- `resource_pack_EP_JXK_0/modconfigs/ep_jg_table_0.json`

Melee package files:

- `resource_pack_*/modconfigs/ep_jg_table_编号.json`
- `resource_pack_*/modconfigs/EP_JG_DATA/*.json`
- `resource_pack_*/modconfigs/EP_SET_DATA/ep_gun_set_data_编号.json`
- `resource_pack_*/modconfigs/EP_SET_DATA/canvas/ep_gun_编号_setting.json`
- `behavior_pack_*/Script_NeteaseMod*/modMain.py`
- `behavior_pack_*/EpJxk_Gun_编号_Script/*`

## Main Armory Support

The main armory must know which non-gun packs expose damage settings.

In `modConfig.py`, keep a melee package index tuple such as:

```python
EP_MELEE_MOD_INDEX = (4, 5, 11, 14)
```

In `EpJxkScriptClientSystem.SetNowGunDataEvent`, merge both gun and melee setting systems:

```python
damageModIndex = tuple(modConfig.EP_GUN_MOD_INDEX) + tuple(getattr(modConfig, 'EP_MELEE_MOD_INDEX', ()))
for x in damageModIndex:
    gunSystem = clientApi.GetSystem("EpJxk_Gun_{}_Script".format(x), "EpJxkGun{}ClientSystem".format(x))
    nowSetData = getattr(gunSystem, 'nowSetData', None) if gunSystem else None
    if nowSetData:
        combined_data.update(nowSetData)
```

Skip empty `nowSetData`; some pack systems initialize after the main system.

## Melee Damage Application Order

Custom melee damage is a base damage override, not a final damage override.

The correct runtime order in `epGun.py` is:

1. Refresh settings: `self.GetSystem.SetNowGunDataEvent(False)`.
2. Apply custom base damage with forced base overwrite.
3. Render/apply parts so damage-increasing attachments stack on top.
4. Apply melee talent / enchant / stamina modifiers.
5. Combat reads `epGun.nowData['danger']`.

`ApplyCurrentGunDangerSetting` should support both `nowType == 0` and `nowType == 1`, with a force mode for re-equipping the same melee item:

```python
def ApplyCurrentGunDangerSetting(self, forceBase=False):
    if self.nowType not in (0, 1) or not self.nowData or not self.GetSystem or not self.GetSystem.mItemNameSpace:
        return False
    ...
    if forceBase or oldBaseDanger is None:
        self.nowData['danger'] = newBaseDanger
        self._gunDangerSettingBase = newBaseDanger
        return newBaseDanger != defaultDanger
```

In `RestMeleeData`, call forced base apply before `RenderParts()`:

```python
epMelee.RestNowMeleeData()
self.GetSystem.SetNowGunDataEvent(False)
self.ApplyCurrentGunDangerSetting(True)
self.RenderParts()
```

Do not place forced custom damage after `RenderParts()`, or attachment damage bonuses will be overwritten.

## Equipment UI

In `epGunParts.py`, when initializing the equipment UI, apply custom base damage before taking the bound default-data snapshot:

```python
nowType = self.gunAllData['type']
if nowType in (0, 1):
    self.GetSystem.SetNowGunDataEvent(False)
    index = self.mItemNameSpace.find(':')
    result = self.mItemNameSpace[index + 1:]
    danger = self.GetSystem.SetNowGunData.get(result, self.nowData['danger'])
    self.gunAllData['data']['danger'] = danger
```

Then `defaultData = copy.deepcopy(self.gunAllData)` lets attachment previews stack from the custom base damage.

## Weapon Table Preview

For melee table/tooltips, refresh settings before displaying type `1` damage:

```python
self.GetSystem.SetNowGunDataEvent(False)
danger = self.GetSystem.SetNowGunData.get(result, weaponData['danger'])
```

Use this value in the visible damage text.

## Setting Bridge System For A Melee Pack

Each melee pack needs a minimal bridge system named like the gun packs:

```text
behavior_pack_*/EpJxk_Gun_编号_Script/
|-- __init__.py
|-- modCommon/
|   |-- __init__.py
|   `-- modConfig.py
|-- EpJxkGun编号ClientSystem.py
|-- EpJxkGun编号ServerSystem.py
`-- plugins/MODSDKSpring/...
```

`modConfig.py`:

```python
MOD_NAMESPACE = "EpJxk_Gun_编号_Script"
MOD_VERSION = "0.0.1"
CLIENT_SYSTEM_NAME = "EpJxkGun编号ClientSystem"
CLIENT_SYSTEM_CLS_PATH = "EpJxk_Gun_编号_Script.EpJxkGun编号ClientSystem.EpJxkGun编号ClientSystem"
SERVER_SYSTEM_NAME = "EpJxkGun编号ServerSystem"
SERVER_SYSTEM_CLS_PATH = "EpJxk_Gun_编号_Script.EpJxkGun编号ServerSystem.EpJxkGun编号ServerSystem"
EP_SET_SYSTEM = "ep_gun_set_data_编号"
```

Client system:

```python
def GetMySetting(self):
    setClientSystem = clientApi.GetSystem("epSet_0", "epSet_0_ClientSystem")
    if setClientSystem:
        self.nowSetData = setClientSystem._Return_My_ModSetting(modConfig.EP_SET_SYSTEM) or {}

    gunSystem = clientApi.GetSystem("EpJxkScript", "EpJxkScriptClientSystem")
    if gunSystem:
        gunSystem.SetNowGunDataEvent()
```

Server system:

```python
@ListenEvent.Server(eventName="ClientLoadAddonsFinishServerEvent")
def ClientLoadAddonsFinishServerEvent(self, args):
    setSystem = serverApi.GetSystem("epSet_0", "epSet_0_ServerSystem")
    if setSystem:
        setSystem.AddUseMod(modConfig.EP_SET_SYSTEM, modConfig.MOD_NAMESPACE, modConfig.CLIENT_SYSTEM_NAME,
                            modConfig.SERVER_SYSTEM_NAME)
```

The package entry `Script_NeteaseMod*/modMain.py` must register these systems in `InitServer` and `InitClient`. Keep the existing `@Mod.Binding(name="Script_NeteaseMod...")` name unless the pack already uses another binding.

Python 2 package imports require every Python folder to include `__init__.py`, including `plugins/__init__.py`.

## Generate Setting JSON

Generate two files:

```text
resource_pack_*/modconfigs/EP_SET_DATA/ep_gun_set_data_编号.json
resource_pack_*/modconfigs/EP_SET_DATA/canvas/ep_gun_编号_setting.json
```

Top-level index JSON:

```json
{
  "data": {
    "title": "EP军工编号_包名",
    "icon": "textures/ui/epGun/gun_编号",
    "canvas": "modconfigs/EP_SET_DATA/canvas/ep_gun_编号_setting.json",
    "ui_pos_key_list": [],
    "index": [
      {
        "title": "分类中文名",
        "icon": "textures/ui/epGun/gun_编号",
        "main": ["weapon_key", "rest0"]
      },
      {
        "title": "导出/导入配置",
        "icon": "textures/ui/epGun/gun_编号",
        "main": ["save_setting", "input_setting"]
      }
    ]
  }
}
```

Canvas JSON item:

```json
{
  "default": 4.5,
  "item": "ep_jxk:melee_frying_pan",
  "range": [0.01, 50],
  "type": "danger",
  "server": true
}
```

Always include:

```json
"save_setting": {
  "type": "save",
  "china": "保存当前设置",
  "server": true
},
"input_setting": {
  "type": "input",
  "china": "导入预设",
  "server": true
}
```

Use readable UTF-8 Chinese in JSON. When writing Chinese from Python 2 automation, prefer unicode literals or `\u` escapes to avoid mojibake.

## Category Mapping

Do not invent setting category names.

Use:

- pack table: `resource_pack_*/modconfigs/ep_jg_table_编号.json`
- main category map: `resource_pack_EP_JXK_0/modconfigs/ep_jg_table_0.json`

For melee:

```python
category_name = main_table["melee_table_list"][category_key]
```

Example:

- EP4 `ep_jg_table_4.json`: `ep_jxk:melee_frying_pan` is in `melee_table["5"]`.
- Main `ep_jg_table_0.json`: `melee_table_list["5"] == "其它武器"`.
- Setting page title must be `其它武器`.

## Bind Variant Discovery

This is the most important non-obvious rule.

`GetAllBindData` merges a bound weapon by copying the base weapon and overlaying the current weapon fields:

```python
bindData = copy.deepcopy(self.GetJgData(bindItem))
for key, value in data.items():
    if key not in bindData:
        bindData[key] = value
    else:
        if isinstance(value, dict):
            for v0, v1 in value.items():
                bindData[key][v0] = v1
        else:
            bindData[key] = value
```

Therefore setting generation must include:

1. Direct items listed in `melee_table`.
2. Every `EP_JG_DATA/*.json` whose top-level `bind` points to an item listed in `melee_table`.

For bind variants:

- category comes from the bound base weapon;
- setting key is the variant config filename without `.json`;
- `item` is `"ep_jxk:" + setting_key` unless the project has a specific reason to use an original item identifier;
- default damage comes from the variant's own `data.danger`;
- sorting level comes from the variant's own `data.gun_level`, defaulting to `0` if missing.

Example EP4 bind variants:

- `melee_bat_g` binds `ep_jxk:melee_bat`, category `棒类`.
- `melee_fire_axe_h` binds `ep_jxk:melee_fire_axe`, category `大斧类型`.
- `melee_chainsaw_a` binds `ep_jxk:melee_chainsaw`, category `耗油武器`.
- `netherite_sword` binds `ep_jxk:melee_electric_guitar`, category inherited from that base item.

## Sorting

Within each category, sort setting keys by:

1. `data.gun_level` descending.
2. Original table/order discovery order for stable ties.

Do not sort alphabetically if levels differ.

## Known Pack Counts After Bind Handling

At the time this experience was recorded:

- EP4 求生之路: 69 melee settings, 8 groups.
- EP5 暗影突袭: 10 melee settings, 1 group.
- EP11 LR堑壕战术: 7 melee settings, 1 group.
- EP14 APX传家宝: 8 melee settings, 1 group.

These counts are useful as sanity checks, but regenerate from config files rather than hardcoding them.

## Validation Checklist

After editing:

- Run Python 2 `compile(open(path, 'rb').read(), path, 'exec')` on changed `.py` files.
- Run `json.load(open(path, 'rb'))` on generated setting JSON.
- Verify every setting page title equals the category name from `melee_table_list`.
- Verify each category is sorted by level high to low.
- Verify bind variants are included, not only direct `melee_table` entries.
- In game, test:
  - setting appears;
  - changed damage applies on first equip;
  - changed damage persists after switching away and back;
  - attachment damage stacks on top of setting damage;
  - equipment UI and weapon table preview show the custom base damage.
```

## 本次踩坑记录

### 1. 只处理 direct melee 会漏掉大量武器

`EP军工4_求生之路` 直接表内近战只有 9 把，但 bind 变体补全后是 69 把。后续不要用 `type == 1` 作为唯一筛选条件；需要把 bind 到近战基础武器的配置也视为近战。

### 2. `ApplyCurrentGunDangerSetting` 不能只在设置变化时写入

切出再切回同一把近战时，`nowData` 会重新从配置拷贝成默认伤害，但 `_gunDangerSettingBase` 仍记录上次设置值。如果看到“设置值没变”就直接返回，会导致二次切回失效。近战初始化需要 `forceBase=True`。

### 3. 自定义伤害不能覆盖配件加成

自定义伤害是基础伤害。必须先写入基础伤害，再 `RenderParts()` 叠加配件；如果反过来，配件加伤会被覆盖。

### 4. Python 2 中文写文件容易乱码

用 Python 2 命令行直接写中文字符串可能被系统编码污染。写 JSON 自动化时，用 UTF-8 文件脚本、unicode 字面量，或 `\u` 转义。

### 5. `plugins/__init__.py` 不能漏

`EpJxk_Gun_编号_Script.plugins.MODSDKSpring...` 在 Python 2 下要求中间目录也是 package。少 `plugins/__init__.py` 会导致系统 import 失败，设置页不会注册。
