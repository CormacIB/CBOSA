'use strict'

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  closeCapture: () => ipcRenderer.send('close-capture'),
  getPort: () => ipcRenderer.invoke('get-port'),
  platform: process.platform,
})
