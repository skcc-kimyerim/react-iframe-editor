import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Message = {
  role: 'user' | 'assistant' | 'system' | 'error';
  content: string;
};

export type ProjectState = {
  name: string;
  isInitialized: boolean;
  isServerRunning: boolean;
  chatHistory: Message[];
  devServerUrl: string;
  fileTree: any[];
  selectedFilePath: string;
  code: string;
  routePath: string;
  availableRoutes: string[];
  createdAt: string;
  lastModified: string;
};

export type ProjectStore = {
  // 현재 활성 프로젝트
  currentProject: ProjectState | null;

  // 프로젝트 목록 (이름을 키로 한 맵)
  projects: Record<string, ProjectState>;

  // 프로젝트 관련 액션
  createProject: (name: string) => void;
  selectProject: (name: string) => void;
  deleteProject: (name: string) => void;
  clearCurrentProject: () => void;

  // 현재 프로젝트 상태 업데이트
  updateCurrentProject: (updates: Partial<ProjectState>) => void;

  // 채팅 히스토리 관리
  addMessage: (message: Message) => void;
  clearChatHistory: () => void;

  // 프로젝트 초기화 상태 관리
  setProjectInitialized: (initialized: boolean) => void;
  setServerRunning: (running: boolean) => void;

  // 파일 및 코드 관리
  setFileTree: (tree: any[]) => void;
  setSelectedFile: (path: string, content: string) => void;
  updateFileContent: (content: string) => void;

  // 라우트 관리
  setRoutePath: (path: string) => void;
  setAvailableRoutes: (routes: string[]) => void;

  // 유틸리티
  getProjectNames: () => string[];
  hasProjects: () => boolean;
};

const createDefaultProject = (name: string): ProjectState => ({
  name,
  isInitialized: false,
  isServerRunning: false,
  chatHistory: [
    {
      role: 'assistant',
      content: `안녕하세요! "${name}" 프로젝트에 오신 것을 환영합니다. 질문을 보내면 프로젝트 생성과 개발을 도와드릴게요.`,
    },
  ],
  devServerUrl: '',
  fileTree: [],
  selectedFilePath: '',
  code: '',
  routePath: '/',
  availableRoutes: ['/'],
  createdAt: new Date().toISOString(),
  lastModified: new Date().toISOString(),
});

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set, get) => ({
      currentProject: null,
      projects: {},

      createProject: (name: string) => {
        const trimmedName = name.trim();
        if (!trimmedName) return;

        const newProject = createDefaultProject(trimmedName);

        set((state) => ({
          projects: {
            ...state.projects,
            [trimmedName]: newProject,
          },
          currentProject: newProject,
        }));
      },

      selectProject: (name: string) => {
        const project = get().projects[name];
        if (project) {
          set((state) => ({
            currentProject: {
              ...project,
              lastModified: new Date().toISOString(),
            },
          }));
        }
      },

      deleteProject: (name: string) => {
        set((state) => {
          const newProjects = { ...state.projects };
          delete newProjects[name];

          const currentProject = state.currentProject?.name === name ? null : state.currentProject;

          return {
            projects: newProjects,
            currentProject,
          };
        });
      },

      clearCurrentProject: () => {
        set((state) => ({
          ...state,
          currentProject: null,
        }));
      },

      updateCurrentProject: (updates: Partial<ProjectState>) => {
        set((state) => {
          if (!state.currentProject) return state;

          const updatedProject = {
            ...state.currentProject,
            ...updates,
            lastModified: new Date().toISOString(),
          };

          return {
            currentProject: updatedProject,
            projects: {
              ...state.projects,
              [updatedProject.name]: updatedProject,
            },
          };
        });
      },

      addMessage: (message: Message) => {
        set((state) => {
          if (!state.currentProject) return state;

          const updatedProject = {
            ...state.currentProject,
            chatHistory: [...state.currentProject.chatHistory, message],
            lastModified: new Date().toISOString(),
          };

          return {
            currentProject: updatedProject,
            projects: {
              ...state.projects,
              [updatedProject.name]: updatedProject,
            },
          };
        });
      },

      clearChatHistory: () => {
        get().updateCurrentProject({
          chatHistory: [
            {
              role: 'assistant',
              content: `안녕하세요! "${
                get().currentProject?.name
              }" 프로젝트에 오신 것을 환영합니다. 질문을 보내면 프로젝트 생성과 개발을 도와드릴게요.`,
            },
          ],
        });
      },

      setProjectInitialized: (initialized: boolean) => {
        get().updateCurrentProject({ isInitialized: initialized });
      },

      setServerRunning: (running: boolean) => {
        get().updateCurrentProject({ isServerRunning: running });
      },

      setFileTree: (tree: any[]) => {
        get().updateCurrentProject({ fileTree: tree });
      },

      setSelectedFile: (path: string, content: string) => {
        get().updateCurrentProject({
          selectedFilePath: path,
          code: content,
        });
      },

      updateFileContent: (content: string) => {
        get().updateCurrentProject({ code: content });
      },

      setRoutePath: (path: string) => {
        get().updateCurrentProject({ routePath: path });
      },

      setAvailableRoutes: (routes: string[]) => {
        get().updateCurrentProject({ availableRoutes: routes });
      },

      getProjectNames: () => {
        return Object.keys(get().projects).sort((a, b) => {
          const projectA = get().projects[a];
          const projectB = get().projects[b];
          return new Date(projectB.lastModified).getTime() - new Date(projectA.lastModified).getTime();
        });
      },

      hasProjects: () => {
        return Object.keys(get().projects).length > 0;
      },
    }),
    {
      name: 'project-store',
      partialize: (state) => ({
        projects: state.projects,
        currentProject: state.currentProject,
      }),
    }
  )
);
