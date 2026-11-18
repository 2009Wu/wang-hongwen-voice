"""Consent and opt-out command for Windows Studio, separate from its interface."""
import argparse
import os
from pathlib import Path

from studio_paths import DATA, atomic_json, read_json
from studio_analytics import PREFERENCES, preferences


def main():
    parser = argparse.ArgumentParser(description='管理三个语音工作室的匿名使用统计。')
    parser.add_argument('--collector', help='维护者提供的 HTTPS 收集地址。')
    parser.add_argument('--disable', action='store_true', help='关闭上报。')
    args = parser.parse_args()
    if args.disable:
        PREFERENCES.unlink(missing_ok=True)
        for database in DATA.glob('*/analytics-delivery.sqlite3'):
            try:
                database.unlink(missing_ok=True)
            except OSError:
                print('尚有工作室运行，本地统计缓存暂时不能删除。上报已关闭。')
        print('已关闭匿名使用统计。')
        return
    defaults = read_json(Path(__file__).with_name('analytics-defaults.json'), {})
    base = args.collector or defaults.get('collector')
    if not base or not base.startswith('https://'):
        parser.error('需要维护者提供 HTTPS 收集地址。')
    print('是否加入匿名使用统计？三款工作室共用这个设置。')
    print('发送生成次数、首次下载格式、A/B 采用和粗略生成参数。')
    print('不会发送音频、文件名、输入文字、参考人声、用户账号或设备编号。')
    print('接收地址为 ' + base)
    if input('启用统计请输入 yes，直接回车退出：').strip().lower() != 'yes':
        print('设置未更改。')
        return
    songs = input('也分享已登记公开歌曲的转换次数？输入 yes 启用：').strip().lower() == 'yes'
    old = read_json(PREFERENCES)
    atomic_json(PREFERENCES, {'enabled': True, 'collector': base, 'public_song_counts': songs})
    if preferences() is None:
        if old is None:
            PREFERENCES.unlink(missing_ok=True)
        else:
            atomic_json(PREFERENCES, old)
        parser.error('收集地址必须是有效的 HTTPS 域名，且不能包含路径或账号信息。')
    print('已启用。随时可用 --disable 关闭。')


if __name__ == '__main__':
    main()
