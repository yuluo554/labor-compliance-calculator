# -*- coding: utf-8 -*-
"""条款库与依据联动（FR-6.2）。"""

from __future__ import annotations

import json

import pytest

from lcc import law
from lcc.errors import LawBasisError, ParamSchemaError


def test_load_library(data_dir):
    library = law.load_library(data_dir)
    assert library.ids()
    assert library.has("LCL-47")


def test_clause_citation_and_points(data_dir):
    library = law.load_library(data_dir)
    clause = library.get("LCL-47")
    assert clause.law == "中华人民共和国劳动合同法"
    assert clause.article == "第四十七条"
    assert clause.points
    assert clause.citation == "《中华人民共和国劳动合同法》第四十七条"


def test_resolve_unknown_id_raises(data_dir):
    library = law.load_library(data_dir)
    with pytest.raises(LawBasisError) as exc:
        library.resolve(["NOPE-1"])
    assert "NOPE-1" in str(exc.value)


def test_engine_referenced_clause_ids_exist(data_dir):
    """引擎声明的依据 id 必须都在条款库中（依据不得悬挂）。"""
    from lcc.engine import severance

    library = law.load_library(data_dir)
    referenced = set()
    for ids in severance.FORMULA_CLAUSE_IDS.values():
        referenced.update(ids)
    missing = sorted(item for item in referenced if not library.has(item))
    assert not missing, "引擎引用但条款库缺失: {}".format(missing)


def test_validate_rejects_verified_without_channel(tmp_path):
    (tmp_path / "rules").mkdir()
    path = tmp_path / "law"
    path.mkdir()
    payload = {
        "schema_version": 1,
        "clauses": [
            {"id": "X-1", "law": "某法", "article": "第一条", "points": ["要点"],
             "status": "verified"}
        ],
    }
    (path / "clauses.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ParamSchemaError) as exc:
        law.load_library(data_dir=str(tmp_path))
    assert "channel" in str(exc.value)


def test_validate_rejects_missing_points(tmp_path):
    (tmp_path / "rules").mkdir()
    path = tmp_path / "law"
    path.mkdir()
    payload = {
        "schema_version": 1,
        "clauses": [{"id": "X-1", "law": "某法", "article": "第一条", "status": "pending"}],
    }
    (path / "clauses.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ParamSchemaError) as exc:
        law.load_library(data_dir=str(tmp_path))
    assert "points" in str(exc.value)


def test_clause_library_has_no_verbatim_long_text(data_dir):
    """呈现纪律：要点为摘述，单条要点不得过长（规避全文转载）。"""
    library = law.load_library(data_dir)
    for clause in library.clauses():
        for point in clause.points:
            assert len(point) <= 200, "{} 要点过长，疑为全文转载".format(clause.id)