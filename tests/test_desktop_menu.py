import desktop


def test_about_and_help_copy():
    assert desktop.ABOUT_TEXT == (
        "Song Splitter\nVersion 1.0.0\nRuns entirely on this computer."
    )
    assert desktop.HELP_TEXT == (
        "Drop songs on the window or use File → Open. Vocals and music stay on this computer."
    )


def test_menu_spec_labels():
    titles = [title for title, _items in desktop.MENU_SPEC]
    assert titles == ["Song Splitter", "File", "Window", "Help"]
    by_title = dict(desktop.MENU_SPEC)
    assert "About Song Splitter" in by_title["Song Splitter"]
    assert "Quit" in by_title["Song Splitter"]
    assert "Open songs…" in by_title["File"]
    assert "Minimize" in by_title["Window"]
    assert "Close" in by_title["Window"]
    assert "How to use" in by_title["Help"]
