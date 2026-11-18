"""Allowlist for the only fields accepted by the Studio analytics collector."""
import re

PRODUCTS = {'wang-hongwen-voice', 'custom-voice-studio', 'deng-xiaoping-voice'}
EVENTS = {'generated', 'download', 'adopt_b'}
STEPS = {0, 20, 40, 60}
VOCAL_MIX = {'unknown', 'soft', 'balanced', 'forward'}
MUSIC_MIX = {'unknown', 'quiet', 'balanced', 'forward'}
LENGTHS = {'unknown', 'under_30s', '30s_to_2m', '2m_to_5m', 'over_5m'}
VARIANTS = {'base', 'redo'}
FORMATS = {'none', 'mp3', 'flac', 'wav', 'mp4'}
EVENT_FIELDS = {
    'event_id', 'studio', 'version', 'action', 'mode', 'variant', 'format',
    'steps', 'vocal_mix', 'music_mix', 'duration', 'song',
}
TOKEN = re.compile(r'[a-f0-9]{32}')


def validate_event(value):
    if not isinstance(value, dict) or set(value) != EVENT_FIELDS:
        return False
    string_fields = EVENT_FIELDS - {'steps', 'song'}
    if any(not isinstance(value[key], str) for key in string_fields):
        return False
    if type(value['steps']) is not int:
        return False
    song = value['song']
    return bool(
        TOKEN.fullmatch(value['event_id'])
        and value['studio'] in PRODUCTS
        and re.fullmatch(r'[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}', value['version'])
        and value['action'] in EVENTS
        and value['mode'] in {'sing', 'speak'}
        and value['variant'] in VARIANTS
        and value['format'] in FORMATS
        and (value['action'] == 'download') == (value['format'] != 'none')
        and (value['action'] != 'adopt_b' or (value['mode'], value['variant']) == ('sing', 'redo'))
        and value['steps'] in STEPS
        and value['vocal_mix'] in VOCAL_MIX
        and value['music_mix'] in MUSIC_MIX
        and value['duration'] in LENGTHS
        and (song is None or (
            isinstance(song, str) and (song == 'unmatched' or TOKEN.fullmatch(song))
            and (value['action'], value['mode'], value['variant']) == ('generated', 'sing', 'base')
        ))
    )
