// Electron main process: launches the Python backend (jarvis.server) as a
// child process, then opens the dashboard window pointed at it.

const { app, BrowserWindow } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

const PROJECT_ROOT = path.join(__dirname, "..");
const PYTHON_BIN = path.join(PROJECT_ROOT, ".venv", "bin", "python3");

let pythonProcess = null;
let mainWindow = null;

function startPythonBackend() {
  pythonProcess = spawn(PYTHON_BIN, ["-m", "jarvis.server"], {
    cwd: PROJECT_ROOT,
    env: process.env,
  });

  pythonProcess.stdout.on("data", (data) => {
    process.stdout.write(`[jarvis-backend] ${data}`);
  });
  pythonProcess.stderr.on("data", (data) => {
    process.stderr.write(`[jarvis-backend] ${data}`);
  });
  pythonProcess.on("exit", (code) => {
    console.log(`[jarvis-backend] exited with code ${code}`);
    pythonProcess = null;
  });
}

function stopPythonBackend() {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    show: false,
    backgroundColor: "#080c10",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.maximize();
    mainWindow.show();
  });

  const startUrl = process.env.ELECTRON_START_URL || `file://${path.join(__dirname, "dist", "index.html")}`;
  mainWindow.loadURL(startUrl);
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  stopPythonBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopPythonBackend);
