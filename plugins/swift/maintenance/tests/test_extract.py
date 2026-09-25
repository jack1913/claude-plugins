import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apicheck.extract import Name, code_fragments, declared_names, names_in, scan  # noqa: E402


def names(markdown: str) -> set[tuple[str, str]]:
    found = set()
    for fragment in code_fragments(markdown):
        found |= {(n.text, n.kind) for n in names_in(fragment)}
    return found


class FragmentTests(unittest.TestCase):
    def test_swift_and_unlabelled_fences_are_code_other_languages_are_not(self):
        md = "```swift\nGlassEffectContainer {}\n```\n```\nForEach {}\n```\n```bash\nPythonThing --x\n```\n"
        found = names(md)
        self.assertIn(("GlassEffectContainer", "type"), found)
        self.assertIn(("ForEach", "type"), found)
        self.assertNotIn(("PythonThing", "type"), found)

    def test_tilde_fence_and_info_string_extras(self):
        self.assertIn(("Toggle", "type"), names('~~~swift title="x"\nToggle()\n~~~\n'))

    def test_indented_fence_inside_list_item_is_code(self):
        md = "- item:\n  ```swift\n  GlassEffectContainer {}\n  ```\n- next\n"
        self.assertIn(("GlassEffectContainer", "type"), names(md))

    def test_closing_fence_may_be_dedented_within_three_spaces_commonmark(self):
        # CommonMark lets the closing fence's indentation differ from the
        # opening fence's by 0-3 spaces; the old code required an exact
        # (backreferenced) match and silently dropped the whole block.
        md = "  ```swift\n  GlassEffectContainer {}\n```\n"
        self.assertIn(("GlassEffectContainer", "type"), names(md))

    def test_closing_fence_may_be_more_indented_within_three_spaces(self):
        md = "```swift\nGlassEffectContainer {}\n   ```\n"
        self.assertIn(("GlassEffectContainer", "type"), names(md))

    def test_fence_nested_in_a_deeper_list_item_is_code(self):
        # Two levels of list nesting push the fence past the old code's
        # {0,4}-space cap on the opening indent, so it was never recognised
        # as a fence at all.
        md = "- outer\n  - item:\n      ```swift\n      GlassEffectContainer {}\n      ```\n"
        self.assertIn(("GlassEffectContainer", "type"), names(md))

    def test_deep_fence_closing_may_be_dedented_to_the_outer_list_level(self):
        md = "- outer\n  - item:\n      ```swift\n      GlassEffectContainer {}\n    ```\n"
        self.assertIn(("GlassEffectContainer", "type"), names(md))

    def test_indented_non_swift_fence_inside_list_item_is_not_code(self):
        # The non-swift fence's closer is dedented (indent 2, opener indent
        # 4) -- valid CommonMark, in the new tolerance. The old code's exact
        # (backreferenced) indent match skipped straight past that closer
        # looking for one indented exactly 4, latched onto the unrelated
        # bare "    ```" on the last line instead, and swallowed everything
        # in between -- including the real swift fence and its
        # GlassEffectContainer -- as (discarded) non-swift body. This test
        # failed on the old code on the GlassEffectContainer assertion, not
        # just on PythonThing.
        md = (
            "    ```bash\n"
            "    PythonThing --x\n"
            "  ```\n"
            "```swift\n"
            "GlassEffectContainer {}\n"
            "```\n"
            "    ```\n"
        )
        found = names(md)
        self.assertNotIn(("PythonThing", "type"), found)
        self.assertIn(("GlassEffectContainer", "type"), found)

    def test_inline_spans_are_code(self):
        self.assertIn(("glassEffect", "member"), names("Use `.glassEffect()` here."))

    def test_signature_span_counts_as_member(self):
        self.assertIn(
            ("scrollEdgeEffectStyle", "member"),
            names("See `scrollEdgeEffectStyle(_:for:)`."),
        )

    def test_strings_comments_directives_and_imports_are_dropped(self):
        md = '```swift\nimport SwiftUI\n#if DEBUG\nText("NotAType") // CommentType\n/* BlockType */\n#endif\n```\n'
        found = names(md)
        self.assertIn(("Text", "type"), found)
        for gone in ("NotAType", "CommentType", "BlockType", "DEBUG", "SwiftUI"):
            self.assertNotIn((gone, "type"), found)


class NamesInTests(unittest.TestCase):
    def test_modifier_chain_and_implicit_members(self):
        found = {
            (n.text, n.kind)
            for n in names_in('Text("x")\n    .bold()\n    .font(.system(size: 12))')
        }
        self.assertTrue(
            {("bold", "member"), ("font", "member"), ("system", "member")} <= found
        )

    def test_calls_on_variables_are_skipped_but_static_calls_are_kept(self):
        found = {
            n.text
            for n in names_in("model.load()\nself.reload()\nFont.system(size: 1)")
        }
        self.assertNotIn("load", found)
        self.assertNotIn("reload", found)
        self.assertIn("system", found)

    def test_attribute_is_not_also_a_type(self):
        found = names_in("@State private var x = 0")
        self.assertIn(Name("State", "attribute"), found)
        self.assertNotIn(Name("State", "type"), found)

    def test_single_letters_are_generic_parameters(self):
        self.assertNotIn(Name("T", "type"), names_in("func f<T>(_ x: T) {}"))


class DeclaredNamesTests(unittest.TestCase):
    def test_declarations_and_generic_parameters(self):
        code = "struct CardView<Content: View>: View {\n  let title: String\n  func load() {}\n}\nenum Phase { case idle }"
        declared = declared_names([code])
        self.assertTrue(
            {"CardView", "Content", "title", "load", "Phase", "idle"} <= declared
        )

    def test_conformances_and_extensions_are_not_declarations(self):
        declared = declared_names(["struct CardView: View {}\nextension Text {}"])
        self.assertNotIn("View", declared)
        self.assertNotIn("Text", declared)


class ScanTests(unittest.TestCase):
    def test_maps_names_to_files_and_skips_names_a_file_declares(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").mkdir()
            (root / "a" / "one.md").write_text(
                '```swift\nstruct CardView: View { var body: some View { Text("") } }\n```\n'
            )
            (root / "two.md").write_text("Use `CardView` and `.glassEffect()`.\n")
            found = scan(root)
            self.assertEqual(found[Name("Text", "type")], [root / "a" / "one.md"])
            self.assertEqual(
                found[Name("CardView", "type")], [root / "two.md"]
            )  # declared only in one.md
            self.assertIn(Name("glassEffect", "member"), found)


if __name__ == "__main__":
    unittest.main()
