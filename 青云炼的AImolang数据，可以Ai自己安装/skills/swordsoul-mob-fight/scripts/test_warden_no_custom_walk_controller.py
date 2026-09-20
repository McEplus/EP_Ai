# coding=utf-8
from test_warden_deployment import AssertNoCustomWardenWalkController


if __name__ == "__main__":
    RefCount = AssertNoCustomWardenWalkController()
    print("warden original fight-none fallback checks passed: refs=%d" % RefCount)
