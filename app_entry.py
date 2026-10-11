"""Finder entry point and an explicit diagnostic for the packaged game."""
import os
from pathlib import Path
import sys


def smoke_test(output, windowed=False):
    """Exercise the bundled renderer, audio decoders and save/load in isolation."""
    import json
    import platform
    import tempfile
    if not windowed:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    import pygame
    from main import Game, PHASE_PLAYING
    from localization import set_language
    from maintenance import PanelWork, KINDS
    from game_storage import default_storage_root
    from ui_fonts import ui_font

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parent/'assets'
    report = {'frozen': bool(getattr(sys, 'frozen', False)),
              'architecture': platform.machine(), 'python': platform.python_version(),
              'default_save_directory': str(default_storage_root()),
              'audio_files': len(list((assets/'audio').glob('*.ogg')))
                             + len(list((assets/'audio').glob('*.mp3')))}
    if report['frozen'] and sys.platform == 'darwin':
        assert default_storage_root() == Path.home()/'Library/Application Support/Second Presence'
        assert not default_storage_root().is_relative_to(Path(sys.executable).parent.parent)
    with tempfile.TemporaryDirectory(prefix='second-presence-check-', dir=output.parent) as directory:
        game = Game(directory)
        assert game.phase == 'MAIN_MENU'
        assert game.audio.available, game.audio.error
        assert {'engine', 'hull', 'vent'} <= game.audio.layers.keys()
        assert {'repair', 'latch', 'open', 'creature', 'terminal'} <= game.audio.sounds.keys()
        assert len(game.audio.footstep_channels) == 2
        for file in (assets/'audio').iterdir():
            if file.suffix in ('.ogg', '.mp3'):
                assert pygame.mixer.Sound(str(file)).get_length() > 0, file.name
        for bold in (False, True):
            assert ui_font(23, bold).size('İkinci Varlık · Çağrı, güç, ışık')[0] > 100
        for lang in ('tr', 'en'):
            set_language(lang)
            game.presentation.refresh()
            game._render()
            # The crew circle must remain visible when a Cocoa display uses
            # an alpha channel; this caught a black-menu regression on macOS.
            pixel = game.screen.get_at((980, 720))
            assert max(pixel[:3]) > 80 and pixel.a == 255, 'Menu scene became transparent'
            if windowed:
                pygame.display.flip()
            pygame.image.save(game.screen, str(output.with_name('macos-menu-'+lang+'.png')))
            game.menu.open_settings()
            game._render()
            game.menu.back()
        game.menu.start_loading(game._new_game_from_menu)
        game._update(.05)
        game._render()
        for _ in range(16):
            game._update(.05)
        game._advance_from_transition()
        assert game.phase == PHASE_PLAYING
        game.day_time = 42
        game.integrity = 84
        task = game.tasks.tasks['Power']
        task.step = 1
        work = PanelWork('Power', task.operation, game.day, task.step)
        work.stage = 1
        task.sessions[(task.step, task.revision)] = work
        assert game.store.save(game)
        game.store.save_settings({'language': 'en', 'volume': .4, 'brightness': 1.2})
        game.integrity = 3
        game.store.load(game)
        assert game.integrity == 84 and game.day_time == 42
        assert game.tasks.tasks['Power'].sessions[(1, 0)].stage == 1
        assert game.store.settings()['brightness'] == 1.2
        for day in (1, 2, 3):
            game.day = day
            game._start_day()
            game.conditions.update(2, 11, False)
            game._render()
        for kind in KINDS:
            game.panel_work = PanelWork('Power', kind, 3)
            game._render()
        game.panel_work = None
        report.update({'status': 'passed', 'languages': ['tr', 'en'],
                       'task_panels': len(KINDS), 'save_load': 'passed',
                       'audio': 'all bundled files decoded', 'daily_lighting': 'passed',
                       'video_driver': pygame.display.get_driver(), 'menu_scene': 'visible'})
    pygame.quit()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    if len(sys.argv) == 3 and sys.argv[1] in ('--smoke-test', '--window-test'):
        smoke_test(sys.argv[2], windowed=sys.argv[1] == '--window-test')
        return
    # A windowed app has no terminal. Keep unexpected failures inspectable.
    if getattr(sys, 'frozen', False) and sys.stderr is None:
        log_root = Path.home()/'Library/Logs/Second Presence'
        log_root.mkdir(parents=True, exist_ok=True)
        sys.stderr = (log_root/'game.log').open('a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stderr
    from main import Game
    Game().run()


if __name__ == '__main__':
    main()
