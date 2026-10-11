#!/bin/zsh
cd -- "${0:A:h}" || exit 1
if [[ -x .venv/bin/python ]]; then
    game_python=.venv/bin/python
else
    game_python=python3
fi
if ! "$game_python" -c 'import pygame' >/dev/null 2>&1; then
    print 'Pygame bulunamadı. README.md içindeki kurulum adımlarını uygula.'
    read '?Kapatmak için Enter tuşuna bas...'
    exit 1
fi
"$game_python" main.py
exit_code=$?
if (( exit_code != 0 )); then
    read '?Bir hata oluştu. Kapatmak için Enter tuşuna bas...'
fi
exit "$exit_code"
