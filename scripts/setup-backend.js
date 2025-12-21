const { execSync } = require('child_process');
const path = require('path');

const backendDir = path.join(__dirname, '..', 'backend');

console.log('Setting up backend with uv...');

try {
  // Check if uv is installed
  execSync('uv --version', { stdio: 'pipe' });
} catch (error) {
  console.error('uv is not installed. Install it with: pip install uv');
  console.error('Or visit: https://docs.astral.sh/uv/getting-started/installation/');
  process.exit(1);
}

console.log('Installing Python dependencies...');
try {
  execSync('uv sync --all-extras', {
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
