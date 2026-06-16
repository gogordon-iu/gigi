import logging
print("Before RKNN:", logging._nameToLevel)
try:
    from rknnlite.api import RKNNLite
    print("After RKNN:", logging._nameToLevel)
except Exception as e:
    print("RKNN load error:", e)
