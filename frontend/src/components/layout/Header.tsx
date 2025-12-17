import { Menu, Settings } from "lucide-react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useAppStore } from "@/stores/app"
import { APP_NAME } from "@/lib/constants"

export function Header() {
  const { toggleSidebar } = useAppStore()

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center gap-4 border-b bg-background px-4 lg:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={toggleSidebar}
      >
        <Menu className="h-5 w-5" />
        <span className="sr-only">Toggle sidebar</span>
      </Button>

      <div className="flex-1">
        <Link to="/" className="flex items-center gap-2 font-semibold">
          <span className="text-lg">{APP_NAME}</span>
        </Link>
      </div>

      <nav className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/settings">
            <Settings className="h-5 w-5" />
            <span className="sr-only">Settings</span>
          </Link>
        </Button>
      </nav>
    </header>
  )
}
