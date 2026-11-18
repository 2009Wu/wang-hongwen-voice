"""Opt-in usage metrics sent by a background thread, outside the generator."""
import json
import math
import queue
import sqlite3
import threading
import time
from contextlib import closing
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from analytics_schema import TOKEN, validate_event
from studio_paths import DATA, EXPORTS, PRODUCT, ROOT, STATE, WORKSPACES, owned_path, read_json

PREFERENCES = DATA / 'analytics-preferences.json'
QUEUE = queue.Queue(maxsize=64)
START_LOCK = threading.Lock()
_thread = None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def preferences():
    config = read_json(PREFERENCES, {})
    if not isinstance(config, dict) or config.get('enabled') is not True:
        return None
    base = config.get('collector')
    if not isinstance(base, str) or len(base) > 200:
        return None
    try:
        url = urlsplit(base)
        port = url.port
    except ValueError:
        return None
    local_test = (config.get('local_test') is True and url.scheme == 'http'
                  and url.hostname == '127.0.0.1' and port is not None)
    if (not url.hostname or (url.scheme != 'https' and not local_test)
            or url.username or url.password or url.query or url.fragment or url.path not in {'', '/'}):
        return None
    return config


def mix_level(value, low, high):
    if type(value) not in {int, float} or not math.isfinite(value):
        return 'unknown'
    return low if value < 0 else high if value >= 3 else 'balanced'


def duration_group(value):
    if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
        return 'unknown'
    if value < 30:
        return 'under_30s'
    if value < 120:
        return '30s_to_2m'
    return '2m_to_5m' if value < 300 else 'over_5m'


def known_song(request):
    hashes = read_json(DATA / 'analytics-song-matches.json')
    if hashes is None:
        hashes = read_json(ROOT / 'analytics-song-matches.json', {})
    checksum = request.get('input_sha256')
    song = hashes.get(checksum) if isinstance(hashes, dict) and isinstance(checksum, str) else None
    return song if isinstance(song, str) and TOKEN.fullmatch(song) else None


def observation(action, identifier, output_format, config):
    if not isinstance(identifier, str) or not TOKEN.fullmatch(identifier):
        return None
    record = read_json(STATE / 'history' / (identifier + '.json'), {})
    if not record or record.get('status') != 'completed' or record.get('preview'):
        return None
    result = record.get('result', {})
    if action == 'download':
        key = {'mp3': 'audio', 'flac': 'flac', 'wav': 'wav', 'mp4': 'video'}.get(output_format)
        if not result.get(key) or not owned_path(EXPORTS, result[key]).is_file():
            return None
    request = read_json(WORKSPACES / identifier / 'request.json', {})
    details_path = result.get('details')
    details = read_json(owned_path(EXPORTS, details_path), {}) if details_path else {}
    mode = record.get('mode')
    variant = 'redo' if request.get('operation') == 'redo' or details.get('redo_interval_seconds') else 'base'
    steps = details.get('steps', request.get('steps'))
    event = {
        'event_id': uuid4().hex,
        'studio': PRODUCT['id'], 'version': PRODUCT['version'],
        'action': action, 'mode': mode, 'variant': variant, 'format': output_format,
        'steps': steps if type(steps) is int and steps in (20, 40, 60) and mode == 'sing' else 0,
        'vocal_mix': mix_level(details.get('vocal_gain_db'), 'soft', 'forward'),
        'music_mix': mix_level(details.get('instrumental_gain_db'), 'quiet', 'forward'),
        'duration': duration_group(details.get('duration_seconds')),
        'song': (known_song(request) or 'unmatched') if config.get('public_song_counts') is True
                and (action, mode, variant) == ('generated', 'sing', 'base') else None,
    }
    return event if validate_event(event) else None


def deliver(event, config):
    url = config['collector'].rstrip('/') + '/v1/events'
    request = Request(url, data=json.dumps(event, separators=(',', ':')).encode('utf-8'),
                      headers={'Content-Type': 'application/json', 'User-Agent': 'VoiceStudio-Analytics/1'},
                      method='POST')
    # Never follow a redirect to another host.
    with build_opener(NoRedirect()).open(request, timeout=4) as response:
        return response.status == 204


def send_once(action, identifier, fmt, config):
    event = observation(action, identifier, fmt, config)
    if event is None:
        return
    STATE.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(STATE / 'analytics-delivery.sqlite3', timeout=2)) as database:
        database.execute("""CREATE TABLE IF NOT EXISTS deliveries(
            action TEXT, local_work TEXT, collector TEXT, delivery TEXT, stamp REAL, sent INTEGER,
            PRIMARY KEY (action, local_work, collector)
        )""")
        cutoff = time.time() - 90 * 86400
        with database:
            database.execute('DELETE FROM deliveries WHERE stamp < ?', (cutoff,))
            if action != 'generated':
                had_generation = database.execute(
                    "SELECT 1 FROM deliveries WHERE action='generated' AND local_work=? AND collector=? AND sent=1",
                    (identifier, config['collector']),
                ).fetchone()
                if not had_generation:
                    return
            database.execute('INSERT OR IGNORE INTO deliveries VALUES (?, ?, ?, ?, ?, 0)',
                             (action, identifier, config['collector'], event['event_id'], time.time()))
            delivery, sent = database.execute(
                'SELECT delivery, sent FROM deliveries WHERE action=? AND local_work=? AND collector=?',
                (action, identifier, config['collector']),
            ).fetchone()
        if sent or preferences() != config:
            return
        event['event_id'] = delivery
        if deliver(event, config):
            with database:
                database.execute('UPDATE deliveries SET sent=1 WHERE delivery=?', (delivery,))


def _send_forever():
    while True:
        action, identifier, fmt = QUEUE.get()
        try:
            config = preferences()
            if config:
                send_once(action, identifier, fmt, config)
        except (OSError, ValueError, KeyError, AttributeError, RuntimeError, sqlite3.Error, HTTPError):
            pass
        finally:
            QUEUE.task_done()


def record_usage(action, identifier, fmt='none'):
    """Queue locally without delaying generation or export."""
    global _thread
    try:
        if not preferences():
            return
        with START_LOCK:
            if _thread is None or not _thread.is_alive():
                _thread = threading.Thread(target=_send_forever, name='studio-analytics', daemon=True)
                _thread.start()
        QUEUE.put_nowait((action, identifier, fmt))
    except (OSError, ValueError, RuntimeError, queue.Full):
        pass
