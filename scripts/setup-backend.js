const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const isWindows = process.platform === 'win32';
const backendDir = path.join(__dirname, '..', 'backend');
const venvDir = path.join(backendDir, 'venv');
const envFile = path.join(backendDir, '.env');

console.log('Setting up backend...');

if (!fs.existsSync(venvDir)) {
  console.log('Creating Python virtual environment...');
  try {
    const pythonCmd = isWindows ? 'python' : 'python3';
    execSync(`${pythonCmd} -m venv "${venvDir}"`, {
      cwd: backendDir,
      stdio: 'inherit'
    });
    console.log('✓ Virtual environment created');
  } catch (error) {
    console.error('✗ Failed to create virtual environment');
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
  console.log('✓ Python dependencies installed');
} catch (error) {
  console.error('✗ Failed to install Python dependencies');
  console.error(error.message);
  process.exit(1);
}

if (!fs.existsSync(envFile)) {
  console.log('\n⚠ Warning: backend/.env file not found');
  console.log('Creating template .env file...');

  const envTemplate = `# TMDB API Key (Required)
# Get your key at: https://www.themoviedb.org/settings/api
TMDB_API_KEY=your_tmdb_api_key_here

# Database (defaults work for local dev)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=nexarr
POSTGRES_PASSWORD=nexarr_password
POSTGRES_DB=nexarr

# Redis (defaults work for local dev)
REDIS_HOST=localhost
REDIS_PORT=6379

# qBittorrent (optional, for download testing)
QBITTORRENT_HOST=localhost
QBITTORRENT_PORT=8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=adminadmin
`;

  fs.writeFileSync(envFile, envTemplate);
  console.log('✓ Created backend/.env template');
  console.log('\n⚠ IMPORTANT: Edit backend/.env and add your TMDB API key before running dev server');
  console.log('Get your TMDB API key at: https://www.themoviedb.org/settings/api\n');
}

console.log('Backend setup complete!');
