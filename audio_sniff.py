"""Detect audio files by content, not by file name."""


def is_audio_file(path):
    """Check the file's actual content, not its name (a downloaded song is
    often saved as e.g. \"song.mp3.mpeg\")."""
    with open(path, "rb") as f:
        head = f.read(16)
    if not head:
        return False
    if head.startswith(b"ID3"):  # MP3 with ID3 tag
        return True
    if head[:4] in (b"fLaC", b"OggS"):  # FLAC / OGG
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":  # WAV
        return True
    if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):  # AIFF
        return True
    if head[4:8] == b"ftyp":  # MP4 / M4A / MOV
        return True
    if head[:16] == bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c"):  # WMA
        return True
    if head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:  # MPEG frame sync (MP3)
        return True
    with open(path, "rb") as f:
        chunk = f.read(65536)
    for sync in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa", b"\xff\xf2"):
        if chunk.find(sync) >= 0:
            return True
    return False
