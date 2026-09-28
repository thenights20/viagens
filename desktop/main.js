const { app, BrowserWindow, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');

app.setName('Viagens');
app.commandLine.appendSwitch('disable-background-timer-throttling');
app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.commandLine.appendSwitch('disable-backgrounding-occluded-windows');

let win;

function ensurePersistentDataDir() {
  const dir = app.getPath('userData');
  try { fs.mkdirSync(dir, { recursive: true }); } catch {}
  return dir;
}

function createWindow() {
  ensurePersistentDataDir();
  win = new BrowserWindow({
    title: 'Viagens',
    show: false,
    autoHideMenuBar: false,
    frame: true,
    backgroundColor: '#07111f',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webviewTag: false,
      partition: 'persist:viagens'
    }
  });

  // Janela normal do Windows, apenas maximizada: mantém barra de título,
  // minimizar, maximizar/restaurar, fechar e menu/ferramentas.
  win.maximize();
  win.loadFile(path.join(__dirname, 'index.html'));
  win.once('ready-to-show', () => win.show());

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(() => {
  session.fromPartition('persist:viagens').setPermissionRequestHandler((webContents, permission, callback) => {
    callback(permission === 'notifications');
  });
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
