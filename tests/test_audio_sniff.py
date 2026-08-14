import audio_sniff


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_id3_mp3(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "a.mp3", b"ID3" + b"\x00" * 20))


def test_mpeg_frame_sync(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "b.bin", b"\xff\xfb" + b"\x00" * 20))


def test_wav(tmp_path):
    assert audio_sniff.is_audio_file(
        _write(tmp_path, "c.wav", b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 8)
    )


def test_flac(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "d.flac", b"fLaC" + b"\x00" * 12))


def test_ogg(tmp_path):
    assert audio_sniff.is_audio_file(_write(tmp_path, "e.ogg", b"OggS" + b"\x00" * 12))


def test_rejects_empty(tmp_path):
    assert not audio_sniff.is_audio_file(_write(tmp_path, "empty.bin", b""))


def test_rejects_text(tmp_path):
    assert not audio_sniff.is_audio_file(_write(tmp_path, "note.txt", b"this is not audio"))
