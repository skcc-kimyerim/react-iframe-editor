import React, { useState, useEffect, useRef } from 'react';
import './ReactEditor.css';

const ReactEditor = () => {
  const [code, setCode] = useState('');
  const [devServerUrl, setDevServerUrl] = useState('');
  const [isServerRunning, setIsServerRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const iframeRef = useRef(null);

  const API_BASE = 'http://localhost:3001/api';

  // 초기 컴포넌트 코드
  const initialCode = `import React, { useState } from 'react';

function App() {
  const [count, setCount] = useState(0);

  return (
    <div style={{ 
      padding: '20px', 
      fontFamily: 'Arial, sans-serif',
      textAlign: 'center',
      maxWidth: '400px',
      margin: '50px auto',
      border: '2px solid #007bff',
      borderRadius: '10px',
      backgroundColor: '#f8f9fa'
    }}>
      <h1 style={{ color: '#007bff' }}>Dynamic React Component</h1>
      <div style={{ 
        fontSize: '24px', 
        margin: '20px 0',
        padding: '20px',
        backgroundColor: '#e9ecef',
        borderRadius: '5px'
      }}>
        Count: <strong>{count}</strong>
      </div>
      <div>
        <button 
          onClick={() => setCount(count + 1)}
          style={{
            padding: '10px 20px',
            margin: '5px',
            backgroundColor: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          ➕ Increment
        </button>
        <button 
          onClick={() => setCount(count - 1)}
          style={{
            padding: '10px 20px',
            margin: '5px',
            backgroundColor: '#dc3545',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          ➖ Decrement
        </button>
      </div>
      <button 
        onClick={() => setCount(0)}
        style={{
          padding: '10px 20px',
          margin: '10px 5px',
          backgroundColor: '#6c757d',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer',
          fontSize: '16px'
        }}
      >
        🔄 Reset
      </button>
    </div>
  );
}

export default App;`;

  useEffect(() => {
    setCode(initialCode);
  }, []);

  // 에러 클리어
  const clearError = () => setError('');

  // API 호출 헬퍼 함수
  const apiCall = async (endpoint, options = {}) => {
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API call failed:', error);
      setError(error.message);
      throw error;
    }
  };

  // 프로젝트 초기화
  const initializeProject = async () => {
    console.log('Initializing project...');
    await apiCall('/init-project', {
      method: 'POST',
      body: JSON.stringify({
        componentCode: code,
        dependencies: {},
      }),
    });
    console.log('Project initialized successfully');
  };

  // React 개발 서버 시작
  const startDevServer = async () => {
    console.log('Starting development server...');
    const data = await apiCall('/start-dev-server', {
      method: 'POST',
    });

    setDevServerUrl(data.devServerUrl);
    setIsServerRunning(true);

    // iframe 로드를 위한 딜레이
    setTimeout(() => {
      if (iframeRef.current) {
        iframeRef.current.src = data.devServerUrl;
      }
    }, 3000);

    console.log('Development server started:', data.devServerUrl);
  };

  // React 개발 서버 중지
  const stopDevServer = async () => {
    try {
      await apiCall('/stop-dev-server', {
        method: 'POST',
      });
      setIsServerRunning(false);
      setDevServerUrl('');
      if (iframeRef.current) {
        iframeRef.current.src = '';
      }
      console.log('Development server stopped');
    } catch (error) {
      console.error('Error stopping dev server:', error);
    }
  };

  // 컴포넌트 업데이트
  const updateComponent = async () => {
    try {
      clearError();
      await apiCall('/component/App.js', {
        method: 'PUT',
        body: JSON.stringify({ content: code }),
      });
      console.log('Component updated successfully');
    } catch (error) {
      console.error('Error updating component:', error);
    }
  };

  // 전체 프로세스 실행
  const runFullProcess = async () => {
    setLoading(true);
    clearError();

    try {
      await initializeProject();
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await startDevServer();
    } catch (error) {
      console.error('Error in full process:', error);
    } finally {
      setLoading(false);
    }
  };

  // 샘플 코드 로드
  const loadSample = (sampleName) => {
    const samples = {
      counter: initialCode,
      todo: `import React, { useState } from 'react';

function App() {
  const [todos, setTodos] = useState([]);
  const [input, setInput] = useState('');

  const addTodo = () => {
    if (input.trim()) {
      setTodos([...todos, { id: Date.now(), text: input, done: false }]);
      setInput('');
    }
  };

  const toggleTodo = (id) => {
    setTodos(todos.map(todo => 
      todo.id === id ? { ...todo, done: !todo.done } : todo
    ));
  };

  return (
    <div style={{ padding: '20px', maxWidth: '400px', margin: '0 auto' }}>
      <h1>Todo App</h1>
      <div style={{ marginBottom: '20px' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && addTodo()}
          placeholder="Add a todo..."
          style={{ padding: '8px', marginRight: '10px', width: '200px' }}
        />
        <button onClick={addTodo} style={{ padding: '8px 16px' }}>Add</button>
      </div>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {todos.map(todo => (
          <li key={todo.id} style={{ margin: '10px 0' }}>
            <label style={{ 
              textDecoration: todo.done ? 'line-through' : 'none',
              cursor: 'pointer'
            }}>
              <input
                type="checkbox"
                checked={todo.done}
                onChange={() => toggleTodo(todo.id)}
                style={{ marginRight: '10px' }}
              />
              {todo.text}
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;`,
      form: `import React, { useState } from 'react';

function App() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    message: ''
  });

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    alert('Form submitted: ' + JSON.stringify(formData, null, 2));
  };

  return (
    <div style={{ padding: '20px', maxWidth: '400px', margin: '0 auto' }}>
      <h1>Contact Form</h1>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px' }}>Name:</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
            required
          />
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px' }}>Email:</label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
            required
          />
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '5px' }}>Message:</label>
          <textarea
            name="message"
            value={formData.message}
            onChange={handleChange}
            rows="4"
            style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
            required
          />
        </div>
        <button 
          type="submit"
          style={{ 
            backgroundColor: '#007bff', 
            color: 'white', 
            padding: '10px 20px', 
            border: 'none', 
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Submit
        </button>
      </form>
    </div>
  );
}

export default App;`,
    };

    setCode(samples[sampleName] || initialCode);
  };

  return (
    <div className="react-editor">
      {/* 상단 툴바 */}
      <div className="toolbar">
        <h1>🚀 React Live Editor</h1>
        <div className="status">
          Status: {isServerRunning ? '🟢 Running' : '🔴 Stopped'}
          {devServerUrl && <span className="url"> - {devServerUrl}</span>}
        </div>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="error-banner">
          ⚠️ {error}
          <button onClick={clearError} className="error-close">
            ×
          </button>
        </div>
      )}

      <div className="main-content">
        {/* 왼쪽 패널: 코드 에디터 */}
        <div className="editor-panel">
          <div className="panel-header">
            <h2>Code Editor</h2>
            <div className="button-group">
              <button onClick={runFullProcess} disabled={loading} className="btn btn-primary">
                {loading ? '⏳ Setting up...' : '🚀 Initialize & Start'}
              </button>

              <button onClick={updateComponent} disabled={!isServerRunning} className="btn btn-success">
                💾 Update Component
              </button>

              <button onClick={stopDevServer} disabled={!isServerRunning} className="btn btn-danger">
                🛑 Stop Server
              </button>
            </div>
          </div>

          {/* 샘플 코드 버튼들 */}
          <div className="sample-buttons">
            <span>Samples:</span>
            <button onClick={() => loadSample('counter')} className="btn-sample">
              Counter
            </button>
            <button onClick={() => loadSample('todo')} className="btn-sample">
              Todo App
            </button>
            <button onClick={() => loadSample('form')} className="btn-sample">
              Form
            </button>
          </div>

          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="code-editor"
            placeholder="Enter your React component code here..."
          />
        </div>

        {/* 오른쪽 패널: iframe 프리뷰 */}
        <div className="preview-panel">
          <div className="panel-header">
            <h2>Live Preview</h2>
            {devServerUrl && (
              <button
                onClick={() => {
                  if (iframeRef.current) {
                    iframeRef.current.src = devServerUrl;
                  }
                }}
                className="btn-refresh"
              >
                🔄 Refresh
              </button>
            )}
          </div>

          {devServerUrl ? (
            <iframe ref={iframeRef} src={devServerUrl} className="preview-iframe" title="React Preview" />
          ) : (
            <div className="preview-placeholder">
              {loading ? (
                <div className="loading">
                  <div className="spinner"></div>
                  <p>Starting development server...</p>
                </div>
              ) : (
                <div className="welcome-message">
                  <h3>🎨 Welcome to React Live Editor!</h3>
                  <p>Click "Initialize & Start" to begin coding</p>
                  <div className="features">
                    <div>✨ Real-time preview</div>
                    <div>🔄 Hot reload</div>
                    <div>📱 Responsive design</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReactEditor;
