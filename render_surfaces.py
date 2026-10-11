"""Opaque RGB canvases independent of the platform's window alpha format."""
import pygame


def opaque_surface(size):
    # SDL3's macOS window format includes alpha. Inheriting that format for
    # world/fog compositing can make the scaled scene transparent at the end.
    return pygame.Surface(size, depth=32, masks=(0xFF0000, 0xFF00, 0xFF, 0))
