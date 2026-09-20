# coding=utf-8
"""坚守者退出战斗后原生移动/攻击组件延迟恢复回归。"""

from test_warden_deployment import AssertRuntimeComponentAndDamageTransitions


if __name__ == "__main__":
    CaseCount = AssertRuntimeComponentAndDamageTransitions()
    print("warden native restore retry checks passed: cases=%d" % CaseCount)
