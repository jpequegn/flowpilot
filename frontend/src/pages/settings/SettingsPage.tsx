import { Button } from "@/components/ui/button"

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Configure FlowPilot preferences and integrations.
        </p>
      </div>

      <div className="space-y-4">
        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold">General</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            General application settings.
          </p>
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">
              Settings will be available in a future update.
            </p>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold">Server</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            FlowPilot server configuration.
          </p>
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Server Status</span>
              <span className="text-sm text-green-500">Connected</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">API Endpoint</span>
              <code className="text-sm text-muted-foreground">/api</code>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold">About</h2>
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Version</span>
              <span className="text-sm text-muted-foreground">0.1.0</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Documentation</span>
              <Button variant="link" size="sm" className="h-auto p-0">
                View Docs
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
