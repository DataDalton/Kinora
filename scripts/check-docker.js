const { execSync } = require('child_process');

console.log('Checking prerequisites...');

try {
  execSync('docker --version', { stdio: 'pipe' });
  console.log('Docker is installed');
} catch (error) {
  console.error('Docker is not installed or not running');
  console.error('Please install Docker Desktop: https://www.docker.com/products/docker-desktop');
  process.exit(1);
}

try {
  execSync('docker info', { stdio: 'pipe' });
  console.log('Docker daemon is running');
} catch (error) {
  console.error('Docker daemon is not running');
  console.error('Please start Docker Desktop');
  process.exit(1);
}

try {
  execSync('python --version', { stdio: 'pipe' });
  console.log('Python is installed');
} catch (error) {
  try {
    execSync('python3 --version', { stdio: 'pipe' });
    console.log('Python3 is installed');
  } catch (error) {
    console.error('Python is not installed');
    console.error('Please install Python 3.14+: https://www.python.org/downloads/');
    process.exit(1);
  }
}

console.log('All prerequisites met!');
