"""Renderiza o tour do app real em MP4 1080p com screenshots de demonstração.

Uso: python scripts/render_presentation.py
Requer Pillow e FFmpeg no PATH. Não acessa produção nem inventa telas.
"""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "presentation"
SHOTS = DOCS / "assets" / "screenshots"
OUTPUT = ROOT / "public" / "media" / "recepia-apresentacao.mp4"
WIDTH, HEIGHT = 1920, 1080


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["arial.ttf", "DejaVuSans.ttf"])
    roots = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")]
    for root in roots:
        for name in names:
            path = root / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    raise RuntimeError("Fonte Arial ou DejaVu não encontrada")


def timecode(seconds: int) -> str:
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02},000"


def write_text_assets(scenes: list[dict]) -> int:
    elapsed = 0
    subtitles = []
    narration = ["# Narração do tour — português do Brasil", "", "Gravar com voz brasileira natural e substituir a faixa silenciosa do MP4 se desejado.", ""]
    storyboard = ["# Storyboard do tour real do Recepia", "", "Formato: 1920×1080, 16:9. As telas vêm de uma instância local real com dados de demonstração.", ""]
    for index, scene in enumerate(scenes, 1):
        end = elapsed + scene["duration"]
        subtitles.append(f"{index}\n{timecode(elapsed)} --> {timecode(end)}\n{scene['narration']}\n")
        narration.append(f"## {timecode(elapsed)}–{timecode(end)} · {scene['title']}\n\n{scene['narration']}\n")
        screen = scene["screenshot"] or "Identidade visual do Recepia e texto do produto"
        storyboard.append(f"{index}. **{timecode(elapsed)}–{timecode(end)} · {scene['title']}** — {screen}. {scene['subtitle']}")
        elapsed = end
    (DOCS / "subtitles.srt").write_text("\n".join(subtitles), encoding="utf-8")
    (DOCS / "narration.md").write_text("\n".join(narration) + "\n", encoding="utf-8")
    (DOCS / "storyboard.md").write_text("\n".join(storyboard) + "\n", encoding="utf-8")
    return elapsed


def background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = (int(20 + ratio * 12), int(17 + ratio * 8), int(16 + ratio * 6))
        draw.line((0, y, WIDTH, y), fill=color)
    return image


def draw_brand(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 64) -> None:
    draw.rounded_rectangle((x, y, x + size, y + size), radius=17, fill="#ecc096")
    draw.text((x + size // 2, y + size // 2 - 3), "r", font=font(int(size * .72), True),
              anchor="mm", fill="#21160e")
    draw.text((x + size + 16, y + size // 2), "recepia", font=font(int(size * .58), True),
              anchor="lm", fill="#ffffff")


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, text_font, max_width: int) -> list[str]:
    lines = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=text_font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render_scene(scene: dict, index: int, total: int, target: Path) -> None:
    image = background()
    draw = ImageDraw.Draw(image)
    draw_brand(draw, 90, 55, 66)
    if scene["screenshot"]:
        shot_path = SHOTS / scene["screenshot"]
        with Image.open(shot_path) as source:
            shot = ImageOps.fit(source.convert("RGB"), (1460, 821), method=Image.Resampling.LANCZOS)
        image.paste(shot, (230, 154))
        draw.rounded_rectangle((228, 152, 1692, 978), radius=15, outline="#815a3a", width=4)
        draw.rounded_rectangle((1360, 169, 1665, 217), radius=17, fill="#2f2118")
        draw.text((1512, 193), "DADOS DE DEMONSTRAÇÃO", font=font(20, True),
                  anchor="mm", fill="#f2c697")
        draw.text((420, 56), scene["title"], font=font(52, True), fill="#f4e7dc")
        draw.rectangle((0, 944, WIDTH, HEIGHT), fill="#1a1513")
        for line_number, line in enumerate(wrapped_lines(draw, scene["narration"], font(33), 1470)[:3]):
            draw.text((230, 957 + line_number * 39), line, font=font(33), fill="#f1d2b6")
    else:
        draw.rounded_rectangle((190, 225, 1730, 850), radius=36, fill="#251b17", outline="#704b32", width=4)
        draw.text((960, 415), scene["title"], font=font(96, True), anchor="mm", fill="#ffffff")
        draw.text((960, 555), scene["subtitle"], font=font(48), anchor="mm", fill="#edc197")
        if index == 11:
            for x, label in zip((490, 960, 1430), ("PETS", "VEÍCULOS", "HOTEL")):
                draw.rounded_rectangle((x - 165, 660, x + 165, 738), radius=25, fill="#463020")
                draw.text((x, 699), label, font=font(35, True), anchor="mm", fill="#ffffff")
    draw.text((WIDTH - 92, 64), f"{index:02}/{total:02}", font=font(25, True), anchor="rm", fill="#c29d7b")
    image.save(target, format="PNG", optimize=True)


def render_video(scenes: list[dict], seconds: int, output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg não encontrado no PATH")
    missing = [s["screenshot"] for s in scenes if s["screenshot"] and not (SHOTS / s["screenshot"]).is_file()]
    if missing:
        raise RuntimeError("Screenshots reais ausentes: " + ", ".join(missing))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="recepia-tour-") as temp:
        directory = Path(temp)
        playlist = ["ffconcat version 1.0"]
        for index, scene in enumerate(scenes, 1):
            frame = directory / f"scene-{index:02}.png"
            render_scene(scene, index, len(scenes), frame)
            playlist.extend([f"file '{frame.as_posix()}'", f"duration {scene['duration']}"])
        playlist.append(f"file '{frame.as_posix()}'")
        concat = directory / "scenes.ffconcat"
        concat.write_text("\n".join(playlist) + "\n", encoding="utf-8")
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-y",
               "-safe", "0", "-i", str(concat),
               "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
               "-vf", "fps=24,format=yuv420p", "-t", str(seconds),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
               "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(output)]
        subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-only", action="store_true", help="gera roteiro e legendas sem renderizar MP4")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    scenes = json.loads((DOCS / "scenes.json").read_text(encoding="utf-8"))
    seconds = write_text_assets(scenes)
    if not args.assets_only:
        render_video(scenes, seconds, args.output)
        print(f"MP4 criado: {args.output} ({seconds} segundos, 1920x1080)")
    else:
        print(f"Roteiro, storyboard e SRT criados ({seconds} segundos)")


if __name__ == "__main__":
    main()
