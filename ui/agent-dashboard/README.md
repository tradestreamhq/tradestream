# TradeStream Agent Dashboard

A modern React-based dashboard for the TradeStream viral trading signal platform.

## Tech Stack

- **Framework**: React 19
- **Build Tool**: Vite 7
- **Language**: TypeScript 5.9
- **Styling**: Tailwind CSS 4
- **State Management**: Zustand
- **Server State**: TanStack Query (React Query)
- **Routing**: React Router 7
- **HTTP Client**: Axios

## Project Structure

```
src/
├── components/     # Reusable UI components
├── pages/          # Page components (Landing, Login, Register, Dashboard)
├── hooks/          # Custom React hooks (useAuth, etc.)
├── services/       # API clients and services
├── store/          # Zustand stores
├── types/          # TypeScript type definitions
├── utils/          # Utility functions
├── App.tsx         # Main app component with providers
└── main.tsx        # App entry point
```

## Development

### Install Dependencies

```bash
npm install
```

### Start Dev Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Features

- Authentication (Email/Password + OAuth)
- Real-time signal streaming (SSE)
- User settings and watchlist management
- Provider profiles and social features
- Gamification (streaks, achievements, leaderboards)
- Referral program

## Environment Variables

Create a `.env` file with:

```
VITE_API_BASE_URL=http://localhost:8000
```

## Integration with Gateway API

The dashboard connects to the FastAPI gateway service at port 8000. See `specs/viral-platform/gateway-api/SPEC.md` for API documentation.
