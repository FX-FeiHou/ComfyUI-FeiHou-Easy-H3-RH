"""CPU-only verification against the unmodified RunningHub ZIP supplied by the user."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
import zipfile

ROOT = Path(__file__).parents[1]
ARCHIVE = Path(os.environ.get('FEIHOU_RH_BASELINE_ZIP', 'rh-baseline.zip'))


class RHBaselineTests(unittest.TestCase):
    @unittest.skipUnless(ARCHIVE.is_file(), 'Set FEIHOU_RH_BASELINE_ZIP to the original RunningHub archive')
    def test_platform_code_and_contract_are_preserved(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            before = ast.parse(archive.read('comfyui-feihou-easy-h3-rh/nodes.py').decode('utf-8-sig'))
            self.assertEqual(archive.read('comfyui-feihou-easy-h3-rh/rh_llm.py'), (ROOT / 'rh_llm.py').read_bytes())
        after = ast.parse((ROOT / 'nodes.py').read_text(encoding='utf-8-sig'))
        after.body = [n for n in after.body if not (isinstance(n, ast.FunctionDef) and n.name == '_validate_reference_media_transport')]
        main = next(n for n in after.body if isinstance(n, ast.ClassDef) and n.name == 'FeiHouEasyH3')
        generate = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == 'generate')
        guards = [n for n in generate.body if isinstance(n, ast.If) and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == '_validate_reference_media_transport' for c in ast.walk(n))]
        self.assertEqual(len(guards), 1)
        self.assertEqual(ast.unparse(guards[0].test), 'mode == MODE_REFERENCE')
        generate.body.remove(guards[0])
        # This covers the complete old AST, including LLM auth, billing, model
        # choices, input/widget order, media fallback, cropping and sampling.
        self.assertEqual(ast.dump(before), ast.dump(after))

    def test_guard_rejects_missing_and_unresolved_media(self):
        tree = ast.parse((ROOT / 'nodes.py').read_text(encoding='utf-8-sig'))
        guard = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_validate_reference_media_transport')
        scope = {}
        exec(compile(ast.Module(body=[guard], type_ignores=[]), 'guard', 'exec'), scope)
        validate = scope[guard.name]
        for items in [[], [SimpleNamespace(media_type='audio')]]:
            with self.assertRaises(ValueError):
                validate('text', items)
        for kind in ['image', 'video']:
            items = [SimpleNamespace(media_type=kind)]
            validate('normal prompt', items)
            with self.assertRaises(ValueError):
                validate('__MINIMAX_H3_UNRESOLVED_REF_image__', items)

    @unittest.skipUnless(ARCHIVE.is_file(), 'Set FEIHOU_RH_BASELINE_ZIP to the original RunningHub archive')
    def test_other_original_files_are_byte_identical(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                relative = info.filename.split('/', 1)[1]
                if relative in {'nodes.py', 'web/feihou_easy_h3_ui.js', 'pyproject.toml', 'CHANGELOG.md', '.gitignore'}:
                    continue
                self.assertEqual(archive.read(info), (ROOT / relative).read_bytes(), relative)


if __name__ == '__main__':
    unittest.main()
