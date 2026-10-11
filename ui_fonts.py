"""Bundled UI typefaces; no machine-dependent font substitution."""
from pathlib import Path
import unicodedata
import pygame

FONT_DIR=Path(__file__).resolve().parent/'assets'/'fonts'


def ui_font(size,semibold=False):
    filename='BarlowSemiCondensed-SemiBold.ttf' if semibold else 'BarlowSemiCondensed-Regular.ttf'
    return pygame.font.Font(str(FONT_DIR/filename),max(12,round(size)))


def normalize_text(value):
    text=unicodedata.normalize('NFC',str(value))
    # Direction keys are written out in menus. The priority separator uses a
    # normal supported glyph; Barlow's font metrics can report .notdef as valid.
    return text.replace('→','>').replace('←','<')


def ui_upper(value,turkish=False):
    text=normalize_text(value)
    if turkish:text=text.replace('i','İ').replace('ı','I')
    return text.upper()
