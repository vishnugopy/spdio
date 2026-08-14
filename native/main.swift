import AppKit
import Darwin
import WebKit

// Song Splitter — native macOS shell.
// Launches the embedded Python engine (SongSplitterServer.app), waits for it
// to come up, then shows the web UI in a real window. 100% local, no cloud.

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var serverProcess: Process?
    private var serverPort: Int = 0
    private var quitting = false

    // MARK: - App lifecycle

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMenu()
        makeWindow()
        startServer()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationWillTerminate(_ notification: Notification) {
        quitting = true
        stopServer()
    }

    // MARK: - Menu

    private func buildMenu() {
        let mainMenu = NSMenu()

        let appItem = NSMenuItem()
        mainMenu.addItem(appItem)
        let appMenu = NSMenu()
        appItem.submenu = appMenu
        appMenu.addItem(NSMenuItem(
            title: "About Song Splitter",
            action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)),
            keyEquivalent: ""
        ))
        appMenu.addItem(.separator())
        appMenu.addItem(NSMenuItem(
            title: "Hide Song Splitter",
            action: #selector(NSApplication.hide(_:)),
            keyEquivalent: "h"
        ))
        appMenu.addItem(.separator())
        appMenu.addItem(NSMenuItem(
            title: "Quit Song Splitter",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        ))

        let windowItem = NSMenuItem()
        mainMenu.addItem(windowItem)
        let windowMenu = NSMenu(title: "Window")
        windowItem.submenu = windowMenu
        windowMenu.addItem(NSMenuItem(
            title: "Minimize",
            action: #selector(NSWindow.performMiniaturize(_:)),
            keyEquivalent: "m"
        ))
        windowMenu.addItem(NSMenuItem(
            title: "Close",
            action: #selector(NSWindow.performClose(_:)),
            keyEquivalent: "w"
        ))

        NSApp.mainMenu = mainMenu
    }

    // MARK: - Window

    private func makeWindow() {
        let config = WKWebViewConfiguration()
        config.mediaTypesRequiringUserActionForPlayback = []
        config.preferences.isElementFullscreenEnabled = true
        let prefs = WKWebpagePreferences()
        prefs.allowsContentJavaScript = true
        config.defaultWebpagePreferences = prefs

        let wv = WKWebView(frame: NSRect(x: 0, y: 0, width: 1024, height: 700), configuration: config)
        wv.navigationDelegate = self
        wv.setValue(false, forKey: "drawsBackground") // let the page paint its own theme
        webView = wv

        let win = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1024, height: 700),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        win.title = "Song Splitter"
        win.minSize = NSSize(width: 720, height: 500)
        win.contentView = wv
        win.center()
        win.setFrameAutosaveName("SongSplitterMainWindow")
        win.makeKeyAndOrderFront(nil)
        window = win
        NSApp.activate(ignoringOtherApps: true)
    }

    // MARK: - Engine process

    private func embeddedServerBinary() -> URL? {
        guard let res = Bundle.main.resourceURL else { return nil }
        let bin = res.appendingPathComponent(
            "SongSplitterServer.app/Contents/MacOS/SongSplitterServer"
        )
        return FileManager.default.isExecutableFile(atPath: bin.path) ? bin : nil
    }

    private func findFreePort() -> Int {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { return 8080 }
        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")
        addr.sin_port = 0
        let bound = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { p in
                Darwin.bind(fd, p, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
            }
        }
        guard bound else {
            close(fd)
            return 8080
        }
        var got = sockaddr_in()
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        let queried = withUnsafeMutablePointer(to: &got) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { p in
                getsockname(fd, p, &len) == 0
            }
        }
        let port = queried ? Int(got.sin_port.bigEndian) : 8080
        close(fd)
        return port
    }

    private func startServer() {
        guard let bin = embeddedServerBinary() else {
            showError("Could not find the engine inside the app bundle. The app may be corrupted.")
            return
        }
        serverPort = findFreePort()

        let proc = Process()
        proc.executableURL = bin
        var env = ProcessInfo.processInfo.environment
        env["PORT"] = String(serverPort)
        env["SONGSPLITTER_NO_BROWSER"] = "1"
        proc.environment = env
        proc.terminationHandler = { [weak self] _ in
            guard let self = self else { return }
            if !self.quitting {
                DispatchQueue.main.async {
                    self.showError("The audio engine stopped unexpectedly. Please reopen the app.")
                }
            }
        }
        serverProcess = proc
        do {
            try proc.run()
        } catch {
            showError("Could not start the engine: \(error.localizedDescription)")
            return
        }

        pollReady { [weak self] ok in
            guard let self = self else { return }
            if ok {
                self.loadHome()
            } else {
                self.showError("The engine did not start in time. Please reopen the app.")
            }
        }
    }

    private func pollReady(attempts: Int = 150, then: @escaping (Bool) -> Void) {
        let url = URL(string: "http://127.0.0.1:\(serverPort)/api/history")!
        var req = URLRequest(url: url)
        req.timeoutInterval = 1.0
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            if let http = resp as? HTTPURLResponse, http.statusCode == 200 {
                DispatchQueue.main.async { then(true) }
            } else if attempts > 0 {
                DispatchQueue.global().asyncAfter(deadline: .now() + 0.2) {
                    self.pollReady(attempts: attempts - 1, then: then)
                }
            } else {
                DispatchQueue.main.async { then(false) }
            }
        }.resume()
    }

    private func loadHome() {
        guard let wv = webView else { return }
        wv.load(URLRequest(url: URL(string: "http://127.0.0.1:\(serverPort)/")!))
    }

    private func stopServer() {
        if let proc = serverProcess, proc.isRunning {
            proc.terminate()
        }
        serverProcess = nil
    }

    // MARK: - Downloads & navigation

    // The web UI triggers downloads via <a href="/api/download/...">.
    // WKWebView's own download API isn't exposed by this SDK, so we intercept
    // the navigation and fetch the file natively into the user's Downloads
    // folder instead.
    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url,
              url.path.contains("/api/download/") else {
            decisionHandler(.allow)
            return
        }
        decisionHandler(.cancel)
        saveDownload(url: url)
    }

    private func saveDownload(url: URL) {
        var request = URLRequest(url: url)
        request.timeoutInterval = 60
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            guard let self = self, let data = data else {
                if let error = error {
                    DispatchQueue.main.async {
                        self?.showError("Download failed: \(error.localizedDescription)")
                    }
                }
                return
            }
            let name = url.pathComponents.last ?? "song.mp3"
            let downloads = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
                ?? FileManager.default.homeDirectoryForCurrentUser
            let dest = downloads.appendingPathComponent(name)
            do {
                try data.write(to: dest)
                DispatchQueue.main.async {
                    self.showDownloadNotification(url: dest)
                }
            } catch {
                DispatchQueue.main.async {
                    self.showError("Could not save \(name): \(error.localizedDescription)")
                }
            }
        }.resume()
    }

    private func showDownloadNotification(url: URL) {
        let note = NSUserNotification()
        note.title = "Song Splitter"
        note.informativeText = "Saved \(url.lastPathComponent) to Downloads."
        note.soundName = NSUserNotificationDefaultSoundName
        NSUserNotificationCenter.default.deliver(note)
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    // MARK: - Errors

    private func showError(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "Song Splitter"
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()