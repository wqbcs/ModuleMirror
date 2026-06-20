from .ncd import NCD as NCD

try:
    from .jscpd_adapter import JscpdAdapter as JscpdAdapter
except ImportError:
    ...
