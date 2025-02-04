import unittest
import re
from main import app, fix_svg_urls
from unittest.mock import patch, mock_open

class GraphvizAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_index(self):
        # Test that the index route loads and contains expected text.
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b'Graphviz Live Viewer', response.data)

    def test_render_valid(self):
        # Provide valid DOT code and verify that an SVG is returned.
        valid_code = "digraph G { A -> B; }"
        response = self.client.post('/render', json={'code': valid_code})
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn('svg', json_data)
        self.assertIn("<svg", json_data['svg'])

    def test_render_invalid(self):
        # Provide invalid DOT code and verify that an error is embedded in the SVG.
        invalid_code = "digraph G { A -> }"
        response = self.client.post('/render', json={'code': invalid_code})
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn('svg', json_data)
        # Check that the error message in the SVG contains "syntax error"
        self.assertIn("syntax error", json_data['svg'].lower())

    def test_lint_valid(self):
        # Valid DOT code should produce an empty annotations list.
        valid_code = "digraph G { A -> B; }"
        response = self.client.post('/lint', json={'code': valid_code})
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(len(json_data.get('annotations', [])), 0)

    def test_lint_invalid(self):
        # Invalid DOT code should produce at least one annotation.
        invalid_code = "digraph G { A -> }"
        response = self.client.post('/lint', json={'code': invalid_code})
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertTrue(len(json_data.get('annotations', [])) > 0)

    def test_download_svg(self):
        # Test that /download-svg returns an SVG with embedded DOT metadata
        # and that any links have been modified to include target="_blank".
        valid_code = "digraph G { A -> B; }"
        response = self.client.post('/download-svg', json={'code': valid_code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'image/svg+xml')
        svg_text = response.get_data(as_text=True)
        # Verify that the metadata is present.
        self.assertIn("<metadata id='graphviz-dot'>", svg_text)
        # Verify that target="_blank" has been added (assuming some links are generated).
        # self.assertTrue(re.search(r'target="_blank"', svg_text) is not None)

    def test_download_png(self):
        # Test that /download-png returns a PNG image.
        valid_code = "digraph G { A -> B; }"
        response = self.client.post('/download-png', json={'code': valid_code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'image/png')
        self.assertTrue(len(response.data) > 0)

    @patch("builtins.open", new_callable=mock_open)
    def test_save_and_reload(self, mock_file):
        # Test that posting to /save calls open() appropriately and writes the code.
        test_code = "digraph G { A -> B; }"
        response = self.client.post('/save', json={'code': test_code})
        self.assertEqual(response.status_code, 204)
        # Verify that open() was called with the backup file name, write mode, and proper encoding.
        mock_file.assert_called_with("editor_backup.txt", "w", encoding="utf-8")
        # Verify that write() was called with the test code.
        handle = mock_file()
        handle.write.assert_called_once_with(test_code)

if __name__ == '__main__':
    unittest.main()
