const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const isWindows = process.platform === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');
const venvDir = path.join(backendDir, 'venv');

console.log('Setting up backend...');

if (!fs.existsSync(venvDir)) {
  console.log('Creating Python virtual environment...');
  try {
    const pythonCmd = isWindows ? 'python' : 'python3';
    execSync(`${pythonCmd} -m venv "${venvDir}"`, {
      cwd: backendDir,
      stdio: 'inherit'
    });
    console.log('Virtual environment created');
  } catch (error) {
    console.error('Failed to create virtual environment');
    console.error(error.message);
    process.exit(1);
  }
}

console.log('Installing Python dependencies...');
try {
  const pipCmd = isWindows
    ? `"${path.join(venvDir, 'Scripts', 'pip.exe')}"`
    : `"${path.join(venvDir, 'bin', 'pip')}"`;

  execSync(`${pipCmd} install -r requirements.txt`, {
    cwd: backendDir,
    stdio: 'inherit'
  });
  console.log('Python dependencies installed');
} catch (error) {
  console.error('Failed to install Python dependencies');
  console.error(error.message);
  process.exit(1);
}

console.log('Backend setup complete!');
