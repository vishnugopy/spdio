import desktop
import version


def test_about_and_help_copy():
    assert "Spdio\nVersion %s" % version.VERSION in desktop.ABOUT_TEXT
    assert "Your songs are never uploaded." in desktop.ABOUT_TEXT
    assert "https://vishnugopy.dev/spdio" in desktop.ABOUT_TEXT
    assert "Copyright © 2026 Vishnu Gopy." in desktop.ABOUT_TEXT
    assert desktop.HELP_TEXT == (
        "Drop songs on the window or use File → Open. Vocals and music stay on this computer."
    )


def test_menu_spec_labels():
    titles = [title for title, _items in desktop.MENU_SPEC]
    assert titles == ["Spdio", "File", "Window", "Help"]
    by_title = dict(desktop.MENU_SPEC)
    assert "About Spdio" in by_title["Spdio"]
    assert "Quit" in by_title["Spdio"]
    assert "Open songs…" in by_title["File"]
    assert "Minimize" in by_title["Window"]
    assert "Close" in by_title["Window"]
    assert "How to use" in by_title["Help"]
