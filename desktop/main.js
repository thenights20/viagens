const { app, BrowserWindow, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');

// Nome fixo = pasta de dados fixa entre versões do executável.
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
    autoHideMenuBar: true,
    backgroundColor: '#07111f',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webviewTag: false,
      // Mantém localStorage/cookies/cache no perfil persistente do app.
      partition: 'persist:viagens'
    }
  });

  win.maximize();
  win.setFullScreen(true);
  win.loadFile(path.join(__dirname, 'index.html'));
  win.once('ready-to-show', () => win.show());

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });

  win.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F11') { win.setFullScreen(!win.isFullScreen()); event.preventDefault(); }
    if (input.key === 'Escape' && win.isFullScreen()) { win.setFullScreen(false); event.preventDefault(); }
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
