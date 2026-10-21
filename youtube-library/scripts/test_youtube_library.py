import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import youtube_library as lib

A, B = 'abcdefghijk', 'lmnopqrstuv'


class Tests(unittest.TestCase):
    def incoming(self):
        return dict(videos={A: dict(id=A, title='Song | [live]', channel='Channel', category='10')},
                    playlists={'PLone': dict(id='PLone', title='Same title', source='api', entries=[dict(id=A), dict(id=A)])},
                    likes={A: dict(source='api', date='')}, source='api', fetched='2026-10-13', warnings=[])

    def test_pagination_and_repeat_failure(self):
        api = lib.YouTube('never-used')
        with patch.object(api, 'get', side_effect=[{'items': [1], 'nextPageToken': 'next'}, {'items': [2]}]) as get:
            self.assertEqual(len(list(api.pages('playlists', part='snippet'))), 2)
            self.assertEqual(get.call_args.kwargs['pageToken'], 'next')
        with patch.object(api, 'get', return_value={'nextPageToken': 'loop'}):
            with self.assertRaises(RuntimeError): list(api.pages('playlists'))

    def test_notes_and_damaged_markers(self):
        old = 'Preface\n' + lib.BEGIN + '\nold\n' + lib.END + '\nMy thoughts\n'
        updated = lib.managed_content(old, 'new')
        self.assertIn('My thoughts', updated)
        self.assertTrue(updated.startswith('Preface'))
        with self.assertRaises(RuntimeError): lib.managed_content('personal text', 'new')
        with self.assertRaises(RuntimeError): lib.managed_content(lib.BEGIN, 'new')

    def test_merge_likes_keeps_history_and_date(self):
        first = self.incoming(); first['likes'][A] = dict(source='takeout', date='2020-01-01')
        state = lib.merge({}, first)
        second = self.incoming(); second['likes'][B] = dict(source='api', date='')
        state = lib.merge(state, second)
        self.assertEqual(state['likes'][A]['date'], '2020-01-01')
        self.assertEqual(state['likes'][A]['sources'], ['api', 'takeout'])
        self.assertIn(B, state['likes'])
        wrong = self.incoming(); wrong['channel_id'] = 'other'
        state['channel_id'] = 'mine'
        with self.assertRaises(RuntimeError): lib.merge(state, wrong)

    def test_render_duplicates_and_escape(self):
        incoming = self.incoming()
        incoming['playlists']['PLtwo'] = dict(incoming['playlists']['PLone'], id='PLtwo')
        state = lib.merge({}, incoming)
        output, counts = lib.render(state, {A: 'Music'})
        self.assertEqual(counts['Music'], 1)
        self.assertIn('YouTube/Playlists/Playlist-PLone.md', output)
        self.assertIn('YouTube/Playlists/Playlist-PLtwo.md', output)
        self.assertEqual(output['YouTube/Playlists/Playlist-PLone.md'].count('watch?v='), 2)
        self.assertIn('&#124;', output['Music/YouTube - Videos.md'])
        self.assertIn('&#91;', output['Music/YouTube - Videos.md'])

    def test_local_classifier_fallback(self):
        self.assertEqual(lib.classify(dict(category='10')), 'Music')
        def offline(*args): raise OSError('offline')
        self.assertEqual(lib.classify(dict(title='ambiguous'), offline), 'Review')
        def uncertain(*args): return {'response': '{"topic":"Technology","certain":false}'}
        self.assertEqual(lib.classify(dict(title='ambiguous'), uncertain), 'Review')

    def test_playlist_reconcile_and_partial_fetch(self):
        first = self.incoming(); state = lib.merge({}, first)
        second = self.incoming(); second['source'] = 'takeout'
        playlist = second['playlists'].pop('PLone'); playlist['source'] = 'takeout'
        second['playlists']['takeout-abcd'] = playlist
        self.assertEqual(len(lib.merge(state, second)['playlists']), 1)
        class BrokenApi:
            def pages(self, endpoint, **kwargs):
                if endpoint == 'channels':
                    yield {'items': [{'id': 'mine'}]}
                else:
                    raise RuntimeError('API quota exceeded')
        with self.assertRaises(RuntimeError): lib.fetch(BrokenApi())
        self.assertEqual(len(state['playlists']), 1)

    def test_fetch_all_lists_and_unavailable_metadata(self):
        class Api:
            def pages(self, endpoint, **kwargs):
                if endpoint == 'channels': yield {'items': [{'id': 'mine'}]}
                elif endpoint == 'playlists': yield {'items': [{'id': 'PLone', 'snippet': {'title': 'A'}}]}
                elif endpoint == 'playlistItems':
                    yield {'items': [{'snippet': {'resourceId': {'videoId': A}, 'position': 0, 'title': 'Private video'}}]}
                elif endpoint == 'videos':
                    yield {'items': [{'id': B, 'snippet': {'title': 'Like', 'categoryId': '10'}}]}
            def get(self, *args, **kwargs): return {'items': []}
        result = lib.fetch(Api())
        self.assertTrue(result['videos'][A]['unavailable'])
        self.assertIn(B, result['likes'])

    def test_takeout_csv_json_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'takeout.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('YouTube/playlists/My list-videos.csv', 'Video ID,Time Added\n' + A + ',2020\n' + A + ',2021\n')
                z.writestr('YouTube/ratings/ratings.csv', 'Video ID,Rating\n' + A + ',like\n' + B + ',dislike\n')
                z.writestr('My Activity/YouTube/likes.json', json.dumps([dict(title='Book talk', titleUrl='https://www.youtube.com/watch?v=' + B, time='2022')]))
                z.writestr('YouTube/playlists/unknown.json', '{"unknown":true}')
            data = lib.takeout(archive)
            self.assertEqual(set(data['likes']), {A, B})
            self.assertEqual(len(next(iter(data['playlists'].values()))['entries']), 2)
            self.assertTrue(data['warnings'])
            empty = root / 'empty'; empty.mkdir()
            with self.assertRaises(RuntimeError): lib.takeout(empty)

    def test_publish_preflight_and_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); library = root / 'library'; runtime = root / 'runtime'
            lib.publish(library, runtime, {'Music/A.md': '# first'})
            file = library / 'Music/A.md'
            file.write_text(file.read_text('utf-8') + 'Personal note\n', 'utf-8')
            lib.publish(library, runtime, {'Music/A.md': '# second'})
            self.assertIn('Personal note', file.read_text('utf-8'))
            self.assertEqual(len(list((runtime / 'backups').rglob('A.md'))), 1)
            before = file.read_text('utf-8')
            other = library / 'Books/B.md'; other.parent.mkdir(); other.write_text('Protected note', 'utf-8')
            with self.assertRaises(RuntimeError): lib.publish(library, runtime, {'Music/A.md': 'changed', 'Books/B.md': 'bad'})
            self.assertEqual(file.read_text('utf-8'), before)

    def test_dpapi_roundtrip(self):
        payload = b'fixture, not a real credential'
        encrypted = lib.dpapi(payload)
        self.assertNotEqual(encrypted, payload)
        self.assertEqual(lib.dpapi(encrypted, decrypt=True), payload)

    def test_complete_import_no_real_vault(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(lib, 'request', side_effect=OSError('offline')):
                lib.ingest(self.incoming(), root / 'runtime', root / 'library')
            self.assertTrue((root / 'library/YouTube/Liked Videos.md').exists())
            saved = lib.read_json(root / 'runtime/state.json', {})
            self.assertEqual(len(saved['videos']), 1)


if __name__ == '__main__':
    unittest.main()
