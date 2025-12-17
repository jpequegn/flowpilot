import { create } from "zustand"

interface AppState {
  sidebarOpen: boolean
  selectedWorkflow: string | null
  theme: "light" | "dark" | "system"
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  selectWorkflow: (name: string | null) => void
  setTheme: (theme: "light" | "dark" | "system") => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  selectedWorkflow: null,
  theme: "system",
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  selectWorkflow: (name) => set({ selectedWorkflow: name }),
  setTheme: (theme) => set({ theme }),
}))
