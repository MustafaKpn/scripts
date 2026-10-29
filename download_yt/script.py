import subprocess

urls = [
    "https://youtu.be/Yb16N8Tth5I",
    "https://youtu.be/f2ia1QT7818",
    "https://youtu.be/N71dvaghX7o",
    "https://youtu.be/OVm_jWi1BXU",
    "https://youtu.be/Fr4915b2YY0",
    "https://youtu.be/9FEjEj8FH6k",
    "https://youtu.be/oRWwoZBAmKA",
    "https://youtu.be/JAizy_fYGeQ",
    "https://youtu.be/DL6F6baI_Ts",
    "https://youtu.be/xq2gHPOxXTE",
    "https://youtu.be/arh7EVlcbC8",
    "https://youtu.be/z3YA6ll_zgg",
    "https://youtu.be/ufEhLloDHDk",
    "https://youtu.be/W5iPV_EPvwU",
    "https://youtu.be/mK2MUELUgAA",
    "https://youtu.be/gsO4uyRwT1g",
    "https://youtu.be/TBi6Qq27_mk",
    "https://youtu.be/n9eou_vFNec",
    "https://youtu.be/vK8qJ7crjYU",
]

for url in urls:
    subprocess.run([
        "yt-dlp",
        "-f", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "-o", "%(title)s.%(ext)s",
        url
    ], check=False)
