"""Validate actual report preservation and escaping using synthetic homework."""
import copy
from pathlib import Path
import tempfile
import unittest
from save_homework import save


class HomeworkTests(unittest.TestCase):
    def data(self):
        return {'child': 'Synthetic child', 'week_start': '2026-10-19',
                'checked_days': ['2026-10-' + str(day) for day in range(19, 26)],
                'complete': True, 'tasks': [
                    {'due': '2026-10-20', 'subject': 'Math', 'text': 'Read | <example>',
                     'materials': [{'title': 'Book [1]', 'url': 'https://example.com/book'}]}]}

    def test_partial_cannot_replace_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            data = self.data()
            target = save(data, folder)
            original = target.read_bytes()
            partial = copy.deepcopy(data)
            partial.update(complete=False, checked_days=['2026-10-20'])
            result = save(partial, folder)
            self.assertNotEqual(target, result)
            self.assertEqual(target.read_bytes(), original)
            self.assertIn('&#124;', target.read_text('utf-8'))
            self.assertIn('&lt;example&gt;', target.read_text('utf-8'))

    def test_cross_child_and_incomplete_complete_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            data = self.data()
            save(data, folder)
            data['child'] = 'Another synthetic child'
            with self.assertRaises(ValueError):
                save(data, folder)
            data = self.data()
            data['checked_days'] = ['2026-10-20']
            with self.assertRaises(ValueError):
                save(data, folder)
