"""Convert the existing game-native hatch mark to a macOS icon."""
from pathlib import Path
from PIL import Image, ImageDraw

project = Path(__file__).resolve().parent.parent
mark = Image.open(project/'assets/branding/emblem.png').convert('RGBA')
canvas = Image.new('RGBA', (1024, 1024))
draw = ImageDraw.Draw(canvas)
draw.rounded_rectangle((56, 56, 968, 968), radius=184, fill=(18, 22, 23),
                       outline=(55, 59, 58), width=5)
mark = mark.resize((710, 710), Image.Resampling.LANCZOS)
canvas.alpha_composite(mark, (157, 157))
canvas.save(project/'assets/branding/AppIcon.icns', format='ICNS')
print('Created AppIcon.icns from the game-native mark.')
