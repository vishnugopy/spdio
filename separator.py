import os
import shutil
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

import app_paths


def model_path():
    return app_paths.models_dir() / "baseline.pth"
MODEL_RELEASE_URL = (
    "https://github.com/tsurumeso/vocal-remover/releases/download/"
    "v5.1.1/vocal-remover-v5.1.1.zip"
)

SAMPLE_RATE = 44100
N_FFT = 2048
HOP_LENGTH = 1024
CROPSIZE = 256
BATCHSIZE = 4


def _find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _ensure_ffmpeg_on_path():
    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        d = str(Path(ffmpeg).parent)
        current = os.environ.get("PATH", "")
        if d not in current.split(os.pathsep):
            os.environ["PATH"] = d + os.pathsep + current


class CancelledError(Exception):
    pass


def encode_mp3(wav_path, mp3_path, check_cancel=None):
    import subprocess

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg was not found and could not be installed")
    if check_cancel and check_cancel():
        raise CancelledError
    mp3_path = Path(mp3_path)
    tmp = mp3_path.with_suffix(".tmp.mp3")
    cmd = [ffmpeg, "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "2", str(tmp)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while True:
        try:
            rc = proc.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            if check_cancel and check_cancel():
                proc.kill()
                proc.wait()
                tmp.unlink(missing_ok=True)
                raise CancelledError
            continue
        if rc != 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("ffmpeg failed with exit code %s" % rc)
        break
    tmp.replace(mp3_path)


def ensure_model(progress_cb=None):
    dest = model_path()
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if progress_cb:
        progress_cb("Downloading the AI model (first run only)...")
    tmp_zip = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as fh:
            tmp_zip = fh.name
        with urllib.request.urlopen(MODEL_RELEASE_URL) as response, open(tmp_zip, "wb") as out:
            shutil.copyfileobj(response, out)
        with zipfile.ZipFile(tmp_zip) as zf:
            names = [n for n in zf.namelist() if n.endswith("baseline.pth")]
            if not names:
                raise RuntimeError("Model file not found in the downloaded archive")
            with zf.open(names[0]) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
    finally:
        if tmp_zip:
            try:
                os.unlink(tmp_zip)
            except OSError:
                pass


class VocalSeparator:
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._device = None

    def load(self, progress_cb=None):
        import engine_bootstrap

        engine_bootstrap.activate()
        ensure_model(progress_cb)
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            _ensure_ffmpeg_on_path()
            import torch

            from lib import nets

            device = torch.device("cpu")
            if torch.backends.mps.is_available() and torch.backends.mps.is_built():
                device = torch.device("mps")
            model = nets.CascadedNet(N_FFT, HOP_LENGTH, 32, 128)
            model.load_state_dict(torch.load(str(model_path()), map_location="cpu"))
            model.to(device)
            self._model = model
            self._device = device

    def _separate_masks(self, X_spec, progress_cb=None):
        import numpy as np
        import torch

        from lib import dataset

        n_frame = X_spec.shape[2]
        pad_l, pad_r, roi_size = dataset.make_padding(n_frame, CROPSIZE, self._model.offset)
        X_spec_pad = np.pad(X_spec, ((0, 0), (0, 0), (pad_l, pad_r)), mode="constant")
        X_spec_pad /= np.abs(X_spec).max()

        self._model.eval()
        patches = (X_spec_pad.shape[2] - 2 * self._model.offset) // roi_size
        total_batches = (patches + BATCHSIZE - 1) // BATCHSIZE
        mask_list = []
        with torch.no_grad():
            for b in range(total_batches):
                start = b * BATCHSIZE
                end = min(start + BATCHSIZE, patches)
                crops = [
                    X_spec_pad[:, :, i * roi_size : i * roi_size + CROPSIZE]
                    for i in range(start, end)
                ]
                X_batch = torch.from_numpy(np.asarray(crops)).to(self._device)
                mask = self._model.predict_mask(torch.abs(X_batch))
                mask = mask.detach().cpu().numpy()
                mask = np.concatenate(mask, axis=2)
                mask_list.append(mask)
                if progress_cb:
                    progress_cb((b + 1) / total_batches)
        return np.concatenate(mask_list, axis=2)[:, :, :n_frame]

    def separate(self, input_path, out_dir, progress_cb=None, check_cancel=None):
        import numpy as np
        import soundfile as sf

        from lib import spec_utils

        _ensure_ffmpeg_on_path()
        if check_cancel and check_cancel():
            raise CancelledError
        if progress_cb:
            progress_cb("Reading audio...")
        X, sr = _load_audio(input_path)
        if X.ndim == 1:
            X = np.asarray([X, X])

        X_spec = spec_utils.wave_to_spectrogram(X, HOP_LENGTH, N_FFT)
        if progress_cb:
            progress_cb("Separating vocals...")
        mask = self._separate_masks(X_spec, progress_cb)

        X_mag = np.abs(X_spec)
        X_phase = np.angle(X_spec)
        music_spec = mask * X_mag * np.exp(1j * X_phase)
        vocals_spec = (1 - mask) * X_mag * np.exp(1j * X_phase)

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if progress_cb:
            progress_cb("Rendering audio...")
        music_wav = out_dir / "music.wav"
        vocals_wav = out_dir / "vocals.wav"
        sf.write(str(music_wav), spec_utils.spectrogram_to_wave(music_spec, HOP_LENGTH).T, sr)
        if check_cancel and check_cancel():
            raise CancelledError
        sf.write(str(vocals_wav), spec_utils.spectrogram_to_wave(vocals_spec, HOP_LENGTH).T, sr)
        if check_cancel and check_cancel():
            raise CancelledError

        if progress_cb:
            progress_cb("Encoding MP3...")
        encode_mp3(music_wav, out_dir / "music.mp3", check_cancel)
        if check_cancel and check_cancel():
            raise CancelledError
        encode_mp3(vocals_wav, out_dir / "vocals.mp3", check_cancel)
        if check_cancel and check_cancel():
            raise CancelledError

        music_wav.unlink(missing_ok=True)
        vocals_wav.unlink(missing_ok=True)
        if progress_cb:
            progress_cb(1.0)
        return out_dir


def _load_audio(input_path):
    import numpy as np
    import librosa

    return librosa.load(
        input_path, sr=SAMPLE_RATE, mono=False, dtype=np.float32, res_type="kaiser_fast"
    )
