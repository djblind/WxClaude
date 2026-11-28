from pathlib import Path

import pytest

from wxclaude.core.file_follower import LINES_AT_START, FileFollower

pytestmark = pytest.mark.unit


def test_the_start_gives_the_last_lines_then_only_what_is_added(tmp_path: Path) -> None:
    log = tmp_path / "work.log"
    log.write_text("".join(f"line {n}\n" for n in range(1, 9)), encoding="utf-8")
    follower = FileFollower(log)
    assert follower.new_lines() == [f"line {n}" for n in range(9 - LINES_AT_START, 9)]
    assert follower.new_lines() == []
    with log.open("a", encoding="utf-8") as handle:
        handle.write("line 9\nline 10\n")
    assert follower.new_lines() == ["line 9", "line 10"]


def test_an_unfinished_line_waits_for_its_end(tmp_path: Path) -> None:
    log = tmp_path / "work.log"
    log.write_bytes(b"")
    follower = FileFollower(log)
    assert follower.new_lines() == []
    with log.open("ab") as handle:
        handle.write(b"[1/43] lot ...")
    assert follower.new_lines() == []
    with log.open("ab") as handle:
        handle.write(b"..\r\nnext\n")
    assert follower.new_lines() == ["[1/43] lot .....", "next"]


def test_utf8_a_bom_and_blank_lines(tmp_path: Path) -> None:
    log = tmp_path / "work.log"
    log.write_bytes("﻿Début\n\n   \nFin é\n".encode())
    assert FileFollower(log).new_lines() == ["Début", "Fin é"]


def test_a_file_emptied_is_read_again_and_a_missing_one_gives_nothing(tmp_path: Path) -> None:
    log = tmp_path / "work.log"
    follower = FileFollower(log)
    assert follower.new_lines() == []  # not there yet
    log.write_text("one\ntwo\n", encoding="utf-8")
    assert follower.new_lines() == ["one", "two"]
    log.write_text("new\n", encoding="utf-8")
    assert follower.new_lines() == ["new"]
    log.unlink()
    assert follower.new_lines() == []
