const express = require('express');
const fs = require('fs').promises;
const path = require('path');
const cors = require('cors');
const { spawn } = require('child_process');

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// React 프로젝트 경로
const REACT_PROJECT_PATH = path.join(__dirname, 'dynamic-react-app');
const REACT_DEV_PORT = 3002;

let reactDevServer = null;

app.get('/api/test', (req, res) => {
  res.json({ message: 'Backend server is running', timestamp: new Date().toISOString() });
});

// npm install 실행 함수
async function installDependencies() {
  console.log('📦 Installing React dependencies...');

  return new Promise((resolve, reject) => {
    const isWindows = process.platform === 'win32';
    const npmCommand = isWindows ? 'npm.cmd' : 'npm';

    const installProcess = spawn(npmCommand, ['install'], {
      cwd: REACT_PROJECT_PATH,
      stdio: 'inherit',
    });

    installProcess.on('close', (code) => {
      if (code === 0) {
        console.log('✅ React dependencies installed successfully');
        resolve();
      } else {
        console.error(`❌ npm install failed with code ${code}`);
        reject(new Error(`npm install failed with code ${code}`));
      }
    });

    installProcess.on('error', (err) => {
      console.error('❌ npm install error:', err);
      reject(err);
    });
  });
}

// react-scripts 설치 확인
async function checkReactScriptsInstalled() {
  try {
    const packagePath = path.join(REACT_PROJECT_PATH, 'node_modules', 'react-scripts', 'package.json');
    await fs.access(packagePath);
    console.log('✅ react-scripts is installed');
    return true;
  } catch (error) {
    console.log('❌ react-scripts not found');
    return false;
  }
}

// React 개발 서버 시작
async function startReactDevServer() {
  if (reactDevServer) {
    return;
  }

  const scriptsInstalled = await checkReactScriptsInstalled();
  if (!scriptsInstalled) {
    console.log('⚠️ react-scripts not found, installing dependencies first...');
    await installDependencies();
  }

  console.log('Starting React dev server...');

  const isWindows = process.platform === 'win32';
  const npmCommand = isWindows ? 'npm.cmd' : 'npm';

  reactDevServer = spawn(npmCommand, ['start'], {
    cwd: REACT_PROJECT_PATH,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, PORT: REACT_DEV_PORT, BROWSER: 'none', CI: 'true' },
  });

  reactDevServer.stdout.on('data', (data) => {
    const output = data.toString();
    console.log(`React Dev: ${output}`);

    if (output.includes('webpack compiled') || output.includes('Compiled successfully')) {
      console.log('✅ React dev server is ready');
    }
  });

  reactDevServer.stderr.on('data', (data) => {
    console.log(`React Dev Error: ${data}`);
  });

  reactDevServer.on('error', (err) => {
    console.error('React dev server error:', err);
    reactDevServer = null;
  });

  reactDevServer.on('close', (code) => {
    console.log(`React dev server closed with code ${code}`);
    reactDevServer = null;
  });

  // 서버 시작 대기
  await new Promise((resolve) => setTimeout(resolve, 10000));
}

// React 개발 서버 중지
function stopReactDevServer() {
  if (reactDevServer) {
    reactDevServer.kill('SIGTERM');
    reactDevServer = null;
  }
}

app.put('/api/component/:filename', async (req, res) => {
  try {
    const filename = req.params.filename;
    const { content } = req.body;
    const filePath = path.join(REACT_PROJECT_PATH, 'src', filename);

    console.log(`📝 Updating component: ${filename}`);
    await fs.writeFile(filePath, content, 'utf8');
    console.log(`✅ Updated component: ${filename}`);

    res.json({ success: true, message: 'Component updated successfully' });
  } catch (error) {
    console.error('❌ Error updating component:', error);
    res.status(500).json({ error: 'Failed to update component', details: error.message });
  }
});

// React 프로젝트 초기화
app.post('/api/init-project', async (req, res) => {
  try {
    const { componentCode, dependencies } = req.body;
    console.log('📦 Initializing project...');

    if (require('fs').existsSync(REACT_PROJECT_PATH)) {
      console.log('🗑️ Removing existing project...');
      await fs.rm(REACT_PROJECT_PATH, { recursive: true, force: true });
    }

    // React 프로젝트 디렉토리 생성
    await fs.mkdir(REACT_PROJECT_PATH, { recursive: true });

    // package.json 생성
    const packageJson = {
      name: 'dynamic-react-app',
      version: '0.1.0',
      private: true,
      dependencies: {
        react: '^18.2.0',
        'react-dom': '^18.2.0',
        'react-scripts': '^5.0.1',
        ...dependencies,
      },
      scripts: {
        start: 'react-scripts start',
        build: 'react-scripts build',
      },
      eslintConfig: {
        extends: ['react-app', 'react-app/jest'],
      },
      browserslist: {
        production: ['last 1 Chrome version', 'last 1 Firefox version', 'last 1 Safari version'],
        development: ['last 1 Chrome version', 'last 1 Firefox version', 'last 1 Safari version'],
      },
    };

    await fs.writeFile(path.join(REACT_PROJECT_PATH, 'package.json'), JSON.stringify(packageJson, null, 2));

    // src 디렉토리 생성
    await fs.mkdir(path.join(REACT_PROJECT_PATH, 'src'), { recursive: true });
    await fs.mkdir(path.join(REACT_PROJECT_PATH, 'public'), { recursive: true });

    // App.js 생성
    await fs.writeFile(path.join(REACT_PROJECT_PATH, 'src', 'App.js'), componentCode);

    // index.js 생성
    const indexJs = `
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
`;

    await fs.writeFile(path.join(REACT_PROJECT_PATH, 'src', 'index.js'), indexJs);

    // public/index.html 생성
    const indexHtml = `
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dynamic React App</title>
</head>
<body>
  <div id="root"></div>
</body>
</html>
`;

    await fs.writeFile(path.join(REACT_PROJECT_PATH, 'public', 'index.html'), indexHtml);

    await installDependencies();
    console.log('✅ Project initialized successfully');
    res.json({ success: true, message: 'Project initialized successfully' });
  } catch (error) {
    console.error('❌ Error initializing project:', error);
    res.status(500).json({ error: 'Failed to initialize project' });
  }
});

// React 개발 서버 시작 엔드포인트
app.post('/api/start-dev-server', async (req, res) => {
  try {
    console.log('🚀 Attempting to start React dev server...');

    // 프로젝트 존재 확인
    const projectExists = require('fs').existsSync(REACT_PROJECT_PATH);
    if (!projectExists) {
      return res.status(400).json({ error: 'React project not initialized. Please initialize first.' });
    }

    await startReactDevServer();

    const devServerUrl = `http://localhost:${REACT_DEV_PORT}`;
    console.log(`✅ React dev server started at ${devServerUrl}`);

    res.json({
      success: true,
      devServerUrl,
      message: 'React dev server started successfully',
    });
  } catch (error) {
    console.error('❌ Error starting dev server:', error);
    res.status(500).json({ error: 'Failed to start dev server', details: error.message });
  }
});

// React 개발 서버 중지 엔드포인트
app.post('/api/stop-dev-server', (req, res) => {
  stopReactDevServer();
  res.json({ success: true, message: 'React dev server stopped' });
});

// 서버 시작
app.listen(PORT, () => {
  console.log(`🚀 Backend server running on http://localhost:${PORT}`);
  console.log(`📡 API endpoints available at http://localhost:${PORT}/api/`);
});

// 프로세스 종료 시 React 개발 서버도 종료
process.on('SIGINT', () => {
  console.log('Shutting down servers...');
  stopReactDevServer();
  process.exit(0);
});
