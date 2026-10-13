"""法条条款库：加载 + 依据解析（FR-6.2）。

呈现纪律（data/README §四）：以「法律名 + 条号 + 要点」形式呈现，规避全文转载；
``points`` 为要点摘述，非逐字全文。

依据联动：引擎结果只携带条款 id 列表；由本模块解析成详情。id 不存在时抛
:class:`LawBasisError`（exit 1）——防止结论挂空依据。
"""

from __future__ import annotations

import os

from .data_paths import find_data_dir
from .decimalutil import load_json_decimal
from .errors import LawBasisError, ParamSchemaError

STATUS_PENDING = "pending"
STATUS_VERIFIED = "verified"


class Clause(object):
    """单条法条。"""

    __slots__ = ("raw",)

    def __init__(self, raw):
        # type: (dict) -> None
        self.raw = raw

    @property
    def id(self):
        # type: () -> str
        return str(self.raw.get("id", ""))

    @property
    def law(self):
        # type: () -> str
        return str(self.raw.get("law", ""))

    @property
    def article(self):
        # type: () -> str
        return str(self.raw.get("article", ""))

    @property
    def title(self):
        # type: () -> str
        return str(self.raw.get("title", ""))

    @property
    def points(self):
        # type: () -> list
        return list(self.raw.get("points") or [])

    @property
    def status(self):
        # type: () -> str
        return str(self.raw.get("status", STATUS_PENDING))

    @property
    def source(self):
        # type: () -> dict
        return dict(self.raw.get("source") or {})

    @property
    def citation(self):
        # type: () -> str
        """人类可读引用串：``《法律名》条号``。"""
        if self.article:
            return "《{}》{}".format(self.law, self.article)
        return "《{}》".format(self.law)

    def as_dict(self):
        # type: () -> dict
        return {
            "id": self.id,
            "law": self.law,
            "article": self.article,
            "title": self.title,
            "points": self.points,
            "status": self.status,
            "citation": self.citation,
            "source": self.source,
        }

    def __repr__(self):
        # type: () -> str
        return "Clause(id={!r}, status={!r})".format(self.id, self.status)


class ClauseLibrary(object):
    """条款库：id → Clause 索引 + 依据解析。"""

    def __init__(self, raw, source_file=None):
        # type: (dict, object) -> None
        self.raw = raw
        self.source_file = source_file
        self._index = {}
        for item in raw.get("clauses") or []:
            clause = Clause(item)
            if clause.id:
                self._index[clause.id] = clause

    def ids(self):
        # type: () -> list
        return sorted(self._index)

    def clauses(self):
        # type: () -> list
        return [self._index[key] for key in self.ids()]

    def has(self, clause_id):
        # type: (str) -> bool
        return clause_id in self._index

    def get(self, clause_id):
        # type: (str) -> Clause
        if clause_id not in self._index:
            raise LawBasisError(
                "条款 id {!r} 不在条款库中（依据不得悬挂）".format(clause_id),
                ["可用条款: {}".format(", ".join(self.ids()) or "（空）")],
            )
        return self._index[clause_id]

    def resolve(self, clause_ids):
        # type: (object) -> list
        """把 id 列表解析为条款详情列表；任一 id 缺失即报错。"""
        return [self.get(str(item)) for item in clause_ids]

    def pending_ids(self):
        # type: () -> list
        return [clause.id for clause in self.clauses() if clause.status != STATUS_VERIFIED]

    def __repr__(self):
        # type: () -> str
        return "ClauseLibrary(count={})".format(len(self._index))


def load_library(data_dir=None, validate=True):
    # type: (object, bool) -> ClauseLibrary
    path = os.path.join(find_data_dir(data_dir), "law", "clauses.json")
    if not os.path.isfile(path):
        raise ParamSchemaError("缺少条款库: {}".format(path))
    library = ClauseLibrary(load_json_decimal(path), source_file=path)
    if validate:
        validate_library(library)
    return library


def validate_library(library):
    # type: (ClauseLibrary) -> ClauseLibrary
    problems = []
    if not library.ids():
        problems.append("条款库为空")
    for clause in library.clauses():
        if not clause.law:
            problems.append("{}: 缺 law".format(clause.id or "<无 id>"))
        if not clause.article:
            problems.append("{}: 缺 article".format(clause.id or "<无 id>"))
        if clause.status == STATUS_VERIFIED and not clause.source.get("channel"):
            problems.append("{}: status=verified 但缺 source.channel".format(clause.id))
        # 要点缺失/过短同样拒绝：无要点即无依据留痕（呈现纪律）
        if not clause.points:
            problems.append("{}: 缺 points".format(clause.id or "<无 id>"))
        elif clause.status == STATUS_VERIFIED:
            for point in clause.points:
                if len(point) < 4:
                    problems.append("{}: 要点过短 {!r}".format(clause.id, point))
    if problems:
        raise ParamSchemaError("条款库校验失败", problems)
    return library


__all__ = [
    "STATUS_PENDING",
    "STATUS_VERIFIED",
    "Clause",
    "ClauseLibrary",
    "load_library",
    "validate_library",
]