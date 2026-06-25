'use strict'

const { app, BrowserWindow, globalShortcut, Tray, Menu, nativeImage, ipcMain } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

const PORT = 8765
const isDev = process.env.NODE_ENV === 'development'
const projectRoot = path.join(__dirname, '..')

let mainWindow = null
let captureWindow = null
let tray = null
let pythonProcess = null

// ── Python server ────────────────────────────────────────────────────────────

function startPythonServer() {
  const python = process.platform === 'win32' ? 'python' : 'python3'
  pythonProcess = spawn(python, ['server.py', '--port', String(PORT)], {
    cwd: projectRoot,
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  pythonProcess.stdout.on('data', (d) => process.stdout.write('[python] ' + d))
  pythonProcess.stderr.on('data', (d) => process.stderr.write('[python] ' + d))

  pythonProcess.on('exit', (code) => {
    console.log(`[python] exited with code ${code}`)
  })
}

function waitForServer(timeout = 15000) {
  return new Promise((resolve, reject) => {
    const start = Date.now()
    function poll() {
      http.get(`http://127.0.0.1:${PORT}/api/health`, (res) => {
        if (res.statusCode === 200) return resolve()
        retry()
      }).on('error', retry)
    }
    function retry() {
      if (Date.now() - start > timeout) return reject(new Error('Server did not start in time'))
      setTimeout(poll, 300)
    }
    poll()
  })
}

// ── Windows ──────────────────────────────────────────────────────────────────

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#000000',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    mainWindow.loadURL(`http://localhost:5173`)
    // mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function createCaptureWindow() {
  if (captureWindow) {
    captureWindow.focus()
    return
  }

  captureWindow = new BrowserWindow({
    width: 600,
    height: 180,
    resizable: false,
    alwaysOnTop: true,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#000000',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    captureWindow.loadURL(`http://localhost:5173/?mode=capture`)
  } else {
    captureWindow.loadFile(path.join(__dirname, 'dist', 'index.html'), {
      query: { mode: 'capture' },
    })
  }

  captureWindow.once('ready-to-show', () => {
    captureWindow.show()
    captureWindow.focus()
  })

  captureWindow.on('closed', () => {
    captureWindow = null
  })

  captureWindow.on('blur', () => {
    captureWindow?.close()
  })
}

// ── Tray ─────────────────────────────────────────────────────────────────────

function createTray() {
  // Minimal 16x16 icon as base64 PNG
  const iconData = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAA' +
    'BmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH6AkKDC' +
    'w0NTY0ZQAAAB1pVFh0Q29tbWVudAAAAAAAQ3JlYXRlZCB3aXRoIEdJTVBkLmUHAAAA' +
    'J0lEQVQ4y2NgGAWDDfz//5+BgYGBgXEUDBoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=='
  )

  tray = new Tray(iconData)
  tray.setToolTip('CBOSA')

  const menu = Menu.buildFromTemplate([
    { label: 'Open CBOSA', click: () => mainWindow ? mainWindow.focus() : createMainWindow() },
    { label: 'Quick Capture', click: createCaptureWindow },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ])

  tray.setContextMenu(menu)
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show()
    } else {
      createMainWindow()
    }
  })
}

// ── IPC handlers ─────────────────────────────────────────────────────────────

ipcMain.on('close-capture', () => {
  captureWindow?.close()
})

ipcMain.handle('get-port', () => PORT)

// ── App lifecycle ────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startPythonServer()

  try {
    await waitForServer()
    console.log('[electron] Python server ready')
  } catch (e) {
    console.error('[electron] Python server failed to start:', e.message)
  }

  createMainWindow()
  createTray()

  // Global capture shortcut: Cmd+Shift+Space (macOS) / Ctrl+Shift+Space (Win/Linux)
  const captureKey = process.platform === 'darwin'
    ? 'CommandOrControl+Shift+Space'
    : 'CommandOrControl+Shift+Space'

  globalShortcut.register(captureKey, createCaptureWindow)

  app.on('activate', () => {
    if (!mainWindow) createMainWindow()
  })
})

app.on('window-all-closed', () => {
  // Keep app alive via tray on macOS; quit on other platforms
  if (process.platform !== 'darwin') {
    cleanup()
    app.quit()
  }
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
  cleanup()
})

function cleanup() {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM')
    pythonProcess = null
  }
}
