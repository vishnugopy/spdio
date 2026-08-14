import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

ABOUT_TEXT = "Song Splitter\nVersion 1.0.0\nRuns entirely on this computer."
HELP_TEXT = (
    "Drop songs on the window or use File → Open. "
    "Vocals and music stay on this computer."
)

_MENU = [
    ("Song Splitter", ["About Song Splitter", "Quit"]),
    ("File", ["Open songs…"]),
    ("Window", ["Minimize", "Close"]),
    ("Help", ["How to use"]),
]
if sys.platform == "darwin":
    _MENU = [
        ("Song Splitter", ["About Song Splitter", "Hide", "Quit"]),
        ("File", ["Open songs…"]),
        ("Window", ["Minimize", "Close"]),
        ("Help", ["How to use"]),
    ]

MENU_SPEC = _MENU

_port = 0
_window = None

AUDIO_TYPES = (
    "Audio (*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg;*.aiff;*.aif;*.wma;*.mp4;*.m4v;*.mov;*.mkv)",
)


def menu_items():
    import webview
    from webview.menu import Menu, MenuAction

    def about():
        if _window:
            _window.create_confirmation_dialog("Song Splitter", ABOUT_TEXT)

    def help_():
        if _window:
            _window.create_confirmation_dialog("How to use", HELP_TEXT)

    def quit_():
        if _window:
            _window.destroy()
        threading.Thread(target=lambda: os._exit(0), daemon=True).start()

    def hide():
        if _window:
            _window.minimize()

    def minimize():
        if _window:
            _window.minimize()

    def close():
        if _window:
            _window.destroy()

    def open_():
        if _window:
            open_songs(_window)

    actions = {
        "About Song Splitter": about,
        "Quit": quit_,
        "Hide": hide,
        "Open songs…": open_,
        "Minimize": minimize,
        "Close": close,
        "How to use": help_,
    }
    menus = []
    for title, labels in MENU_SPEC:
        items = []
        for label in labels:
            items.append(MenuAction(label, actions[label]))
        menus.append(Menu(title, items))
    return menus


def _multipart(field, filename, data):
    boundary = "----SongSplitterBoundary"
    filename = Path(filename).name.replace('"', "")
    body = (
        ("--%s\r\n" % boundary).encode()
        + ('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (field, filename)).encode()
        + b"Content-Type: application/octet-stream\r\n\r\n"
        + data
        + ("\r\n--%s--\r\n" % boundary).encode()
    )
    return body, "multipart/form-data; boundary=%s" % boundary


def post_local_file(port, path):
    path = Path(path)
    data = path.read_bytes()
    body, ctype = _multipart("file", path.name, data)
    req = urllib.request.Request(
        "http://127.0.0.1:%s/api/upload" % port,
        data=body,
        method="POST",
        headers={"Content-Type": ctype},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def open_songs(window):
    import webview

    paths = window.create_file_dialog(
        webview.OPEN_DIALOG, allow_multiple=True, file_types=AUDIO_TYPES
    )
    if not paths:
        return
    for path in paths:
        try:
            post_local_file(_port, path)
        except Exception:
            window.create_confirmation_dialog(
                "Song Splitter", "Could not add %s." % Path(path).name
            )


def save_stem(window, job_id, stream, suggested_name):
    import webview

    dests = window.create_file_dialog(
        webview.SAVE_DIALOG,
        save_filename=suggested_name or ("%s.mp3" % stream),
    )
    if not dests:
        return
    dest = dests if isinstance(dests, str) else dests[0]
    url = "http://127.0.0.1:%s/api/download/%s/%s" % (_port, job_id, stream)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            Path(dest).write_bytes(resp.read())
    except (urllib.error.URLError, OSError) as exc:
        window.create_confirmation_dialog("Song Splitter", "Could not save the file.")
        raise exc


def _upload_argv():
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_file():
            try:
                post_local_file(_port, p)
            except Exception:
                pass


def start_window(port):
    import webview

    global _port, _window
    _port = int(port)
    _window = webview.create_window(
        "Song Splitter",
        "http://127.0.0.1:%s/" % _port,
        width=1024,
        height=700,
        min_size=(720, 500),
        easy_drag=False,
    )

    def on_closed():
        os._exit(0)

    _window.events.closed += on_closed
    _window.events.shown += lambda: threading.Thread(target=_upload_argv, daemon=True).start()
    webview.start(menu=menu_items())
