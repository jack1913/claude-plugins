"""The colour arithmetic of the divergence row (scripts/boardlib/divergence.py): sRGB to OKLab, the distance, and the reading of a style attribute.
Pure functions, so these tests need no project, no browser and no setup. The row on a board is tested in test_board_lint.py."""
import sys

import pytest
from helpers import ROOT

sys.path.insert(0, str(ROOT / "scripts" / "boardlib"))
import divergence  # noqa: E402


def test_oklab_matches_the_published_reference_values():
    # Ottosson's reference table: white (1, 0, 0), black (0, 0, 0), pure red (0.628, 0.225, 0.126), pure blue (0.452, -0.032, -0.312)
    for rgb, want in (((255, 255, 255), (1.0, 0.0, 0.0)), ((0, 0, 0), (0.0, 0.0, 0.0)), ((255, 0, 0), (0.628, 0.225, 0.126)), ((0, 0, 255), (0.452, -0.032, -0.312))):
        assert divergence.oklab(rgb) == pytest.approx(want, abs=1e-3), rgb


def test_the_distance_is_zero_for_a_colour_and_itself_and_symmetric():
    a, b = (249, 247, 238), (13, 27, 45)
    assert divergence.distance(a, a) == 0
    assert divergence.distance(a, b) == pytest.approx(divergence.distance(b, a))
    assert divergence.distance((0, 0, 0), (255, 255, 255)) == pytest.approx(1.0, abs=1e-6)   # black to white is one unit of lightness


@pytest.mark.parametrize("value, want", [("#fff", (255, 255, 255)), ("#F9F7EE", (249, 247, 238)), ("  #0d1b2d ", (13, 27, 45)),
                                         ("#ffff", None), ("#f9f7eeff", None), ("rgb(1 2 3)", None), ("white", None), ("", None), ("[[fill: #hex]]", None)])
def test_only_rgb_and_rrggbb_are_colours(value, want):
    assert divergence.parse_hex(value) == want


def test_a_style_attribute_gives_all_three_colours_or_none():
    got = divergence.read_colours("--d-paper:#fff; --d-ink : #000;--d-accent:#00f;--d-paper-dark:#123456")
    assert got == {"--d-paper": (255, 255, 255), "--d-ink": (0, 0, 0), "--d-accent": (0, 0, 255)}
    assert divergence.read_colours("--d-paper:#fff;--d-paper:#eee;--d-ink:#000;--d-accent:#00f")["--d-paper"] == (238, 238, 238)   # the last wins
    assert divergence.read_colours("--d-paper:#fff;--d-ink:#000") is None   # a missing property
    assert divergence.read_colours("--d-paper:#fff;--d-ink:#000;--d-accent-dark:#00f") is None   # another property that starts alike
    assert divergence.read_colours("") is None


def test_the_row_warns_for_an_alike_pair_passes_distinct_ones_and_is_info_with_fewer_than_two():
    ink, paper = "--d-ink:#000;", "--d-paper:#fff;"
    same = paper + ink + "--d-accent:#007d71"
    # an accent a hair away is alike, an accent far away is not, and the accent is the only thing that differs here
    assert divergence.row([("A", same), ("B", paper + ink + "--d-accent:#017d71")])[0] == "warn"
    assert divergence.row([("A", same), ("B", paper + ink + "--d-accent:#c27a12")])[0] == "pass"
    assert divergence.row([("A", same)])[0] == "info"
    assert divergence.row([])[0] == "info"
