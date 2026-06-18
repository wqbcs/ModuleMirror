"""
高性能JSON序列化模块

自动使用orjson（10x加速），降级到标准json。

Author: ModuleMirror
"""

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False

import json
from typing import Any, Union


def dumps(
    obj: Any,
    *,
    ensure_ascii: bool = True,
    indent: bool = False,
    sort_keys: bool = False,
    default=None,
) -> str:
    if HAS_ORJSON:
        opt = 0
        if not ensure_ascii:
            opt |= orjson.OPT_SERIALIZE_NUMPY
        if indent:
            opt |= orjson.OPT_INDENT_2
        if sort_keys:
            opt |= orjson.OPT_SORT_KEYS

        if default is not None:
            result = orjson.dumps(obj, option=opt, default=default)
        else:
            result = orjson.dumps(obj, option=opt)

        return result.decode("utf-8") if isinstance(result, bytes) else result
    else:
        return json.dumps(
            obj,
            ensure_ascii=ensure_ascii,
            indent=2 if indent else None,
            sort_keys=sort_keys,
            default=default,
        )


def loads(s: Union[str, bytes]) -> Any:
    if HAS_ORJSON:
        return orjson.loads(s)
    else:
        return json.loads(s)


__all__ = ["dumps", "loads", "HAS_ORJSON"]
