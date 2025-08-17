import React, { useState } from 'react';
import { Plus, FolderOpen, Trash2, Clock } from 'lucide-react';
import { useProjectStore } from '../stores/projectStore';

interface ProjectSelectorProps {
  onProjectSelected: () => void;
}

export const ProjectSelector: React.FC<ProjectSelectorProps> = ({ onProjectSelected }) => {
  const [newProjectName, setNewProjectName] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [projectType, setProjectType] = useState<'figma' | 'basic'>('basic');

  const { projects, currentProject, createProject, selectProject, deleteProject, getProjectNames, hasProjects } =
    useProjectStore();

  const handleCreateProject = () => {
    const trimmedName = newProjectName.trim();
    if (!trimmedName) return;

    if (projects[trimmedName]) {
      alert('이미 존재하는 프로젝트 이름입니다.');
      return;
    }

    createProject(trimmedName, projectType);
    setNewProjectName('');
    setShowCreateForm(false);
    setProjectType('basic'); // 리셋
    onProjectSelected();
  };

  const handleSelectProject = (name: string) => {
    selectProject(name);
    onProjectSelected();
  };

  const handleDeleteProject = (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`"${name}" 프로젝트를 삭제하시겠습니까?`)) {
      deleteProject(name);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 1) return '오늘';
    if (diffDays === 2) return '어제';
    if (diffDays <= 7) return `${diffDays - 1}일 전`;
    return date.toLocaleDateString('ko-KR');
  };

  const projectNames = getProjectNames();

  return (
    <div className="flex h-full flex-col bg-slate-900/50 border-r border-white/10">
      {/* 헤더 */}
      <div className="p-4 border-b border-white/10">
        <h2 className="text-lg font-semibold text-white mb-3">프로젝트</h2>

        {/* 새 프로젝트 생성 버튼/폼 */}
        {!showCreateForm ? (
          <button
            onClick={() => setShowCreateForm(true)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-white/30 text-white/70 hover:text-white hover:border-white/50 transition-colors"
          >
            <Plus size={16} />새 프로젝트 생성
          </button>
        ) : (
          <div className="space-y-3">
            {/* 프로젝트 이름과 타입을 한 줄에 */}
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <input
                    type="text"
                    placeholder="프로젝트 이름을 입력하세요"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreateProject();
                      if (e.key === 'Escape') {
                        setShowCreateForm(false);
                        setNewProjectName('');
                        setProjectType('basic');
                      }
                    }}
                    className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder:text-white/50 focus:outline-none focus:border-indigo-400"
                    autoFocus
                  />
                </div>

                {/* 프로젝트 타입 스위치 */}
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-medium transition-colors ${
                      projectType === 'basic' ? 'text-white' : 'text-white/50'
                    }`}
                  >
                    Basic
                  </span>

                  {/* 토글 스위치 */}
                  <button
                    type="button"
                    onClick={() => setProjectType(projectType === 'basic' ? 'figma' : 'basic')}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-800 ${
                      projectType === 'figma' ? 'bg-indigo-600' : 'bg-white/20'
                    }`}
                    title={projectType === 'basic' ? 'Basic 프로젝트' : 'Figma 프로젝트'}
                  >
                    <span
                      className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                        projectType === 'figma' ? 'translate-x-5' : 'translate-x-1'
                      }`}
                    />
                  </button>

                  <span
                    className={`text-xs font-medium transition-colors ${
                      projectType === 'figma' ? 'text-white' : 'text-white/50'
                    }`}
                  >
                    Figma
                  </span>
                </div>
              </div>

              <p className="text-xs text-white/50 px-1">
                {projectType === 'basic'
                  ? 'React 기본 템플릿으로 프로젝트를 시작합니다.'
                  : 'Figma 디자인을 React 코드로 변환할 수 있습니다.'}
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleCreateProject}
                disabled={!newProjectName.trim()}
                className="flex-1 px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                생성
              </button>
              <button
                onClick={() => {
                  setShowCreateForm(false);
                  setNewProjectName('');
                  setProjectType('basic');
                }}
                className="flex-1 px-3 py-1.5 bg-white/10 text-white rounded-md text-sm font-medium hover:bg-white/20"
              >
                취소
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 프로젝트 목록 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {!hasProjects() ? (
          <div className="text-center text-white/50 py-8">
            <FolderOpen size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">아직 프로젝트가 없습니다.</p>
            <p className="text-xs">새 프로젝트를 생성해보세요!</p>
          </div>
        ) : (
          projectNames.map((name) => {
            const project = projects[name];
            const isActive = currentProject?.name === name;

            return (
              <div
                key={name}
                onClick={() => handleSelectProject(name)}
                className={`group relative p-3 rounded-lg border cursor-pointer transition-all ${
                  isActive
                    ? 'bg-indigo-600/20 border-indigo-400/50 text-white'
                    : 'bg-white/5 border-white/10 text-white/80 hover:bg-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{name}</h3>
                    <div className="flex items-center gap-2 mt-1 text-xs text-white/50">
                      <Clock size={12} />
                      <span>{formatDate(project.lastModified)}</span>
                      {project.isInitialized && (
                        <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">초기화됨</span>
                      )}
                      {project.isServerRunning && (
                        <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs">실행중</span>
                      )}
                    </div>
                    <p className="text-xs text-white/40 mt-1 truncate">메시지 {project.chatHistory.length}개</p>
                  </div>

                  <button
                    onClick={(e) => handleDeleteProject(name, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-red-400 transition-opacity"
                    title="프로젝트 삭제"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
