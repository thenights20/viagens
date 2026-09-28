const { app, BrowserWindow, shell, session, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');

// Nome e appId devem permanecer estáveis para que todas as versões usem o mesmo perfil.
app.setName('Viagens');
app.commandLine.appendSwitch('disable-background-timer-throttling');
app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.commandLine.appendSwitch('disable-backgrounding-occluded-windows');

let win;
const profileDir = app.getPath('userData');
const ownerFile = path.join(profileDir, 'apple-monitor-owner.json');

function ensurePersistentDataDir(){ try{fs.mkdirSync(profileDir,{recursive:true});}catch{} }
function processExists(pid){ if(!pid || pid===process.pid)return false; try{process.kill(pid,0);return true}catch{return false} }
function terminateOld(pid){
  if(!processExists(pid))return true;
  try{
    if(process.platform==='win32') execFileSync('taskkill',['/PID',String(pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
    else process.kill(pid,'SIGTERM');
  }catch{}
  return !processExists(pid);
}
function claimCurrentVersion(){
  ensurePersistentDataDir();
  try{
    const old=JSON.parse(fs.readFileSync(ownerFile,'utf8'));
    if(old && old.pid && old.pid!==process.pid && processExists(old.pid)) terminateOld(old.pid);
  }catch{}
  try{fs.writeFileSync(ownerFile,JSON.stringify({pid:process.pid,exe:process.execPath,startedAt:new Date().toISOString()}));}catch{}
}
function clearOwnership(){
  try{const x=JSON.parse(fs.readFileSync(ownerFile,'utf8'));if(x.pid===process.pid)fs.unlinkSync(ownerFile)}catch{}
}

function createWindow(){
  win=new BrowserWindow({
    title:'Apple Stock Monitor',show:false,autoHideMenuBar:false,frame:true,backgroundColor:'#07111f',
    webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,webviewTag:false,partition:'persist:viagens'}
  });
  win.maximize();
  win.loadFile(path.join(__dirname,'index.html'));
  win.once('ready-to-show',()=>win.show());
  win.webContents.setWindowOpenHandler(({url})=>{if(/^https?:/i.test(url))shell.openExternal(url);return{action:'deny'}});
}

app.whenReady().then(()=>{
  claimCurrentVersion();
  session.fromPartition('persist:viagens').setPermissionRequestHandler((wc,permission,callback)=>callback(permission==='notifications'));
  createWindow();
  app.on('activate',()=>{if(BrowserWindow.getAllWindows().length===0)createWindow()});
});
app.on('before-quit',clearOwnership);
app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit()});
