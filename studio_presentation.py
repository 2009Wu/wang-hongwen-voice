"""Local desktop styling and interface translations."""
from base64 import b64encode
from html import escape
import json
from pathlib import Path

import gradio as gr

from settings import MAX_MB, MAX_TEXT
from studio_paths import EXPORTS, PRODUCT, SHARED_CACHE

INTERFACE = Path(__file__).parent / 'assets' / 'interface'
# Ethnologue 2026 total speakers (L1 + L2). Traditional is a Mandarin script option.
RANKED = (
    ('en', 'English'), ('zh-CN', '简体中文'), ('hi', 'हिन्दी'),
    ('es', 'Español'), ('ar', 'العربية الفصحى'), ('fr', 'Français'),
    ('bn', 'বাংলা'), ('pt', 'Português'), ('id', 'Bahasa Indonesia'),
    ('ur', 'اردو'), ('ru', 'Русский'), ('de', 'Deutsch'), ('ja', '日本語'),
    ('pcm', 'Naijá'), ('arz', 'العربية المصرية'), ('mr', 'मराठी'),
    ('vi', 'Tiếng Việt'), ('te', 'తెలుగు'), ('sw', 'Kiswahili'), ('ha', 'Hausa'),
)
RTL = {'ar', 'arz', 'ur'}
NAMES = dict(RANKED) | {'zh-TW': '繁體中文'}
PRODUCT_TRANSLATIONS = {
    'wang-hongwen-voice': ('wang', 'Wang Hongwen Voice Studio', '王洪文語音工作室', '王洪文ボイススタジオ'),
    'deng-xiaoping-voice': ('deng', 'Deng Xiaoping Voice Studio', '鄧小平語音工作室', '鄧小平ボイススタジオ'),
    'custom-voice-studio': ('custom', 'Custom Voice Studio', '自選音色工作室', 'カスタム音声スタジオ'),
}
ACCENT, ENGLISH_NAME, TRADITIONAL_NAME, JAPANESE_NAME = PRODUCT_TRANSLATIONS[PRODUCT['id']]

CHROME = (
    ('Interface language', '界面语言', '介面語言'),
    ('Find a language', '搜索语言', '搜尋語言'),
    ('No matching languages', '没有匹配的语言', '沒有相符的語言'),
    ('Drop a file here', '将文件拖放到此处', '將檔案拖放到這裡'),
    ('Click to upload', '点击上传', '點擊上傳'),
    ('or', '或', '或'),
    ('Click to upload or drop files', '点击上传或拖入文件', '點擊上傳或拖入檔案'),
)


def language_control():
    rows = []
    for rank, (locale, name) in enumerate(RANKED, 1):
        direction = 'rtl' if locale in RTL else 'auto'
        option = (f'<button type="button" data-locale="{locale}" lang="{locale}" '
                  f'aria-pressed="false"><bdi dir="{direction}">{escape(name)}</bdi></button>')
        if locale == 'zh-CN':
            option += ('<button class="studio-script" type="button" data-locale="zh-TW" '
                       'lang="zh-TW" aria-pressed="false">繁體中文</button>')
        rows.append(f'<li value="{rank}"><span class="studio-rank" aria-hidden="true">'
                    f'{rank:02}</span>{option}</li>')
    return '''<div id="studio-locale-control">
    <button type="button" class="studio-locale-toggle" aria-label="界面语言 · 简体中文"
            aria-expanded="false" aria-controls="studio-locale-options">
        <span class="studio-locale-name">简体中文</span>
        <span class="studio-locale-chevron" aria-hidden="true">▾</span>
    </button>
    <div class="studio-locale-options" id="studio-locale-options" popover="manual" role="group" aria-label="界面语言" hidden>
        <input class="studio-locale-search" type="search" autocomplete="off" placeholder="搜索语言" aria-label="搜索语言">
        <ol class="studio-locale-list">''' + ''.join(rows) + '''</ol>
        <p class="studio-locale-empty" hidden>没有匹配的语言</p>
    </div>
</div>'''


LOCALE_CONTROL = language_control()


def portrait():
    if ACCENT != 'wang':
        return ''
    encoded = b64encode((INTERFACE.parent / 'icon-source.jpg').read_bytes()).decode('ascii')
    return f'<img class="studio-portrait-image" src="data:image/jpeg;base64,{encoded}" alt="" aria-hidden="true">'


def translations():
    extra = json.loads((INTERFACE / 'extra-locales.json').read_text(encoding='utf-8'))
    catalog = {locale: {} for locale in NAMES}
    keys = {}
    for line in (INTERFACE / 'translations.tsv').read_text(encoding='utf-8-sig').splitlines():
        if not line or line.startswith('#'):
            continue
        chinese, english, traditional = line.split('\t')
        key = f'studio_{len(keys)}'
        keys[chinese] = key
        for locale, data in catalog.items():
            data[key] = {'zh-CN': chinese, 'zh-TW': traditional, 'en': english}[locale] \
                if locale in ('zh-CN', 'zh-TW', 'en') else extra[locale][english]

    def label(english, chinese, traditional, locale):
        if locale == 'zh-CN':
            return chinese
        if locale == 'zh-TW':
            return traditional
        if locale == 'en':
            return english
        return extra[locale][english]

    intro = ('Add a reference voice, then enter text or upload a song. Your projects save automatically.',
             '上传参考人声，再输入文字或放入歌曲。生成后会自动保存作品。',
             '上傳參考人聲，再輸入文字或上傳歌曲。作品會自動儲存。') if ACCENT == 'custom' else (
             'Enter text or upload a song or video with vocals. Your projects save automatically.',
             '输入文字，或上传带原唱的歌曲或视频。生成后会自动保存作品。',
             '輸入文字，或上傳有原唱的歌曲或影片。作品會自動儲存。')
    custom_titles = {'zh-CN': PRODUCT['name'], 'zh-TW': TRADITIONAL_NAME, 'ja': JAPANESE_NAME}
    browser_copy = {}
    for locale, data in catalog.items():
        def word(english, chinese, traditional):
            return label(english, chinese, traditional, locale)

        title = custom_titles.get(locale, ENGLISH_NAME)
        data['studio_hero'] = f'# {title}\n\n{word(*intro)}'
        version = word('Current version', '当前版本', '目前版本')
        folder = word('Project folder', '作品目录', '作品資料夾')
        cache = word('Shared model cache', '共用模型缓存', '共用模型快取')
        data['studio_about'] = (f'{version} · **{PRODUCT["version"]}**\n\n'
                                f'{folder} · `{EXPORTS}`\n\n{cache} · `{SHARED_CACHE}`')
        choose = word('Choose text or a song.', '文字与歌曲任选一种。', '文字與歌曲任選一種。')
        limit = word('Maximum text length', '文字上限', '文字上限')
        file_size = word('Maximum file size', '文件大小上限', '檔案大小上限')
        data['studio_limits'] = f'{choose} {limit} · {MAX_TEXT} / {file_size} · {MAX_MB} MB'
        browser_copy[locale] = {
            'menu': word(*CHROME[0]), 'search': word(*CHROME[1]), 'empty': word(*CHROME[2]),
            'tabs': [data[keys[key]] for key in ('生成作品', '作品历史', '更新与帮助')],
            'upload': [word(*CHROME[i]) for i in (3, 4, 5)],
            'uploadName': word(*CHROME[6]),
        }
    return gr.I18n(**catalog), keys, browser_copy


I18N, KEYS, BROWSER_COPY = translations()


def tr(chinese):
    return I18N(KEYS[chinese])


def launch_presentation():
    frontend = Path(gr.__file__).parent / 'templates' / 'frontend' / 'assets'
    bundle = next(path for path in frontend.glob('core-*.js')
                  if 'as changeLocale' in path.read_text(encoding='utf-8'))
    script = (INTERFACE / 'studio_locale.js').read_text(encoding='utf-8-sig')
    script = script.replace('LOCALE_ASSET', json.dumps(bundle.name), 1)
    script = script.replace('STUDIO_LOCALES', json.dumps({
        'names': NAMES, 'rtl': sorted(RTL), 'copy': BROWSER_COPY,
    }, ensure_ascii=False), 1)
    return {
        'i18n': I18N,
        'css_paths': [INTERFACE / 'studio_theme.css', INTERFACE / 'studio_design.css'],
        'js': script,
    }


def studio_theme():
    common = {
        'block_label_background_fill': 'transparent',
        'block_title_background_fill': 'transparent',
        'block_label_shadow': 'none',
        'button_secondary_shadow': 'none',
        'button_primary_shadow': 'none',
        'shadow_drop': 'none',
        'input_shadow': 'none',
        'block_border_width': '0px',
        'input_border_width': '1px',
    }
    if ACCENT == 'wang':
        palette = dict(body_background_fill='#0e1016', body_text_color='#eef0f5',
                       body_text_color_subdued='#a2abc0', background_fill_primary='#191c27',
                       background_fill_secondary='#222635', border_color_primary='#363b4d',
                       block_background_fill='#171a25', block_label_text_color='#c4cadb',
                       block_title_text_color='#d7dcea', input_background_fill='#11131c',
                       input_border_color='#373d50', input_placeholder_color='#929bb0',
                       button_primary_background_fill='#ef806f', button_primary_text_color='#271318',
                       button_primary_background_fill_hover='#ffa08d', button_primary_text_color_hover='#271318',
                       button_secondary_background_fill='#212636', button_secondary_text_color='#eef0f5',
                       button_secondary_border_color='#3a4054', button_secondary_background_fill_hover='#2c3244')
        hue = 'red'
    elif ACCENT == 'deng':
        palette = dict(body_background_fill='#f3eee1', body_text_color='#252f28',
                       body_text_color_subdued='#5e655a', background_fill_primary='#fcf9f0',
                       background_fill_secondary='#f0ebdd', border_color_primary='#d8cfbc',
                       block_background_fill='#fcf9f0', block_label_text_color='#385647',
                       block_title_text_color='#385647', input_background_fill='#fffdf7',
                       input_border_color='#d8cfbc', input_placeholder_color='#707469',
                       button_primary_background_fill='#224a37', button_primary_text_color='#fffdf6',
                       button_primary_background_fill_hover='#30624b', button_primary_text_color_hover='#fffdf6',
                       button_secondary_background_fill='#faf5e7', button_secondary_text_color='#303d32',
                       button_secondary_border_color='#d8cfbc', button_secondary_background_fill_hover='#f1ead9')
        hue = 'green'
    else:
        palette = dict(body_background_fill='#f2f1fa', body_text_color='#252239',
                       body_text_color_subdued='#645c7e', background_fill_primary='#fff',
                       background_fill_secondary='#eeebf8', border_color_primary='#ddd6ee',
                       block_background_fill='#fff', block_label_text_color='#51418a',
                       block_title_text_color='#3d3163', input_background_fill='#faf9ff',
                       input_border_color='#dfd8ef', input_placeholder_color='#6b6281',
                       button_primary_background_fill='#5138a8', button_primary_text_color='#fff',
                       button_primary_background_fill_hover='#654cc0', button_primary_text_color_hover='#fff',
                       button_secondary_background_fill='#f4f0ff', button_secondary_text_color='#3f3274',
                       button_secondary_border_color='#e3dbf6', button_secondary_background_fill_hover='#ede7ff')
        hue = 'violet'
    stable_colors = {f'{key}_dark': value for key, value in palette.items()}
    return gr.themes.Soft(
        primary_hue=hue, neutral_hue='slate',
        font=['Noto Sans SC', 'Microsoft YaHei UI', 'Segoe UI Variable Text', 'Segoe UI', 'sans-serif'],
    ).set(**common, **palette, **stable_colors)
