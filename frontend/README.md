# FlowPilot Frontend

React frontend for FlowPilot workflow automation.

## Tech Stack

- **React 19** with TypeScript
- **Vite** for development and building
- **Tailwind CSS 4** for styling
- **shadcn/ui** for components
- **TanStack Query** for API state management
- **Zustand** for client state
- **React Router** for navigation
- **Vitest** for testing

## Development

```bash
# Install dependencies
bun install

# Start development server
bun dev

# Run tests
bun test

# Build for production
bun build

# Preview production build
bun preview
```

## Scripts

- `bun dev` - Start development server with HMR
- `bun build` - Build for production
- `bun preview` - Preview production build
- `bun test` - Run tests in watch mode
- `bun test:run` - Run tests once
- `bun lint` - Run ESLint
- `bun lint:fix` - Fix ESLint errors
- `bun format` - Format with Prettier
- `bun typecheck` - Run TypeScript type checking

## Project Structure

```
src/
├── components/
│   ├── ui/           # shadcn/ui components
│   ├── layout/       # Layout components (AppLayout, Sidebar, Header)
│   └── common/       # Shared components
├── pages/
│   ├── workflows/    # Workflow pages
│   ├── executions/   # Execution pages
│   └── settings/     # Settings pages
├── hooks/            # Custom React hooks
├── lib/
│   ├── api.ts        # API client
│   ├── utils.ts      # Utility functions
│   └── constants.ts  # App constants
├── stores/           # Zustand stores
├── types/            # TypeScript types
├── App.tsx
├── main.tsx
└── index.css
```

## API Proxy

Development server proxies API requests to the backend:

- `/api/*` → `http://localhost:8080/api/*`
- `/hooks/*` → `http://localhost:8080/hooks/*`

Start the FlowPilot server before development:

```bash
# From project root
flowpilot serve
```
