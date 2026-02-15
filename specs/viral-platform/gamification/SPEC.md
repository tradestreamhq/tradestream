# Gamification Specification

## Goal

Drive daily engagement and viral growth through streaks, achievements, badges, leaderboards, and a tiered referral program.

## Target Behavior

Gamification features create multiple engagement loops:

- **Daily**: Login streaks encourage daily visits
- **Achievement**: Milestones provide satisfaction and sharing moments
- **Competition**: Leaderboards create aspirational goals
- **Growth**: Referrals create viral coefficient > 0.15

## Feature Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    GAMIFICATION ECOSYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   Streaks   │───▶│ Achievements│───▶│   Leaderboards     │  │
│  │ (Daily)     │    │  (Badges)   │    │   (Competition)    │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│         │                  │                     │              │
│         │                  │                     │              │
│         ▼                  ▼                     ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  Retention  │    │  Sharing    │    │   Referral         │  │
│  │  (+47%)     │    │  Moments    │    │   Program          │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Streaks

### Streak Types

| Type              | Description                             | Reset Condition        |
| ----------------- | --------------------------------------- | ---------------------- |
| Login             | Consecutive days visiting platform      | Miss a calendar day    |
| Profitable Signal | Consecutive profitable signals followed | Signal results in loss |
| Analysis Post     | Consecutive days posting analysis       | Miss a calendar day    |
| Provider Signal   | Consecutive days publishing signals     | Miss a calendar day    |

### Streak Display

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR STREAKS                                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🔥 LOGIN STREAK                                                │
│  ████████████████░░░░░░░░░░░░░░  14 days                       │
│  Next milestone: 30 days (🏆 Monthly Dedication)                │
│                                                                  │
│  📈 PROFITABLE STREAK                                           │
│  ██████░░░░░░░░░░░░░░░░░░░░░░░░  3 signals                     │
│  Best: 8 signals                                                │
│                                                                  │
│  ⚠️ Don't lose your streak! Come back tomorrow.                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Streak Service Implementation

```python
# services/gateway/services/streak_service.py

from datetime import date, datetime, timedelta
from typing import Optional
import asyncpg


class StreakService:
    def __init__(self, db: asyncpg.Pool):
        self.db = db

    async def record_activity(
        self,
        user_id: str,
        streak_type: str,
        activity_date: Optional[date] = None,
    ) -> dict:
        """Record an activity and update streak."""
        if activity_date is None:
            activity_date = date.today()

        # Get current streak
        streak = await self.db.fetchrow(
            """
            SELECT current_count, longest_count, last_activity_date
            FROM user_streaks
            WHERE user_id = $1 AND streak_type = $2
            """,
            user_id,
            streak_type,
        )

        if not streak:
            # First activity - create streak
            await self.db.execute(
                """
                INSERT INTO user_streaks (user_id, streak_type, current_count, longest_count, last_activity_date, streak_started_at)
                VALUES ($1, $2, 1, 1, $3, NOW())
                """,
                user_id,
                streak_type,
                activity_date,
            )
            return {"current_count": 1, "longest_count": 1, "is_new_record": False}

        last_date = streak["last_activity_date"]
        current = streak["current_count"]
        longest = streak["longest_count"]

        if last_date == activity_date:
            # Already recorded today
            return {
                "current_count": current,
                "longest_count": longest,
                "is_new_record": False,
            }

        if last_date == activity_date - timedelta(days=1):
            # Consecutive day - increment streak
            new_count = current + 1
            new_longest = max(longest, new_count)
            is_new_record = new_count > longest

            await self.db.execute(
                """
                UPDATE user_streaks
                SET current_count = $3, longest_count = $4, last_activity_date = $5, updated_at = NOW()
                WHERE user_id = $1 AND streak_type = $2
                """,
                user_id,
                streak_type,
                new_count,
                new_longest,
                activity_date,
            )

            # Check for achievement unlock
            await self._check_streak_achievements(user_id, streak_type, new_count)

            return {
                "current_count": new_count,
                "longest_count": new_longest,
                "is_new_record": is_new_record,
            }
        else:
            # Streak broken - record old streak and reset
            await self._record_streak_history(
                user_id, streak_type, current, streak["streak_started_at"]
            )

            await self.db.execute(
                """
                UPDATE user_streaks
                SET current_count = 1, last_activity_date = $3, streak_started_at = NOW(), updated_at = NOW()
                WHERE user_id = $1 AND streak_type = $2
                """,
                user_id,
                streak_type,
                activity_date,
            )

            return {
                "current_count": 1,
                "longest_count": longest,
                "is_new_record": False,
                "streak_lost": True,
                "previous_streak": current,
            }

    async def _record_streak_history(
        self,
        user_id: str,
        streak_type: str,
        count: int,
        started_at: datetime,
    ):
        """Record completed streak to history."""
        await self.db.execute(
            """
            INSERT INTO streak_history (user_id, streak_type, final_count, started_at, ended_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            user_id,
            streak_type,
            count,
            started_at,
        )

    async def _check_streak_achievements(
        self,
        user_id: str,
        streak_type: str,
        count: int,
    ):
        """Check and unlock streak achievements."""
        if streak_type != "login":
            return

        milestones = {
            7: "streak_7",
            30: "streak_30",
            100: "streak_100",
            365: "streak_365",
        }

        if count in milestones:
            achievement_id = milestones[count]
            await self.unlock_achievement(user_id, achievement_id)

    async def unlock_achievement(self, user_id: str, achievement_id: str):
        """Unlock an achievement for a user."""
        await self.db.execute(
            """
            INSERT INTO user_achievements (user_id, achievement_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, achievement_id) DO NOTHING
            """,
            user_id,
            achievement_id,
        )

    async def get_user_streaks(self, user_id: str) -> list:
        """Get all streaks for a user."""
        return await self.db.fetch(
            """
            SELECT streak_type, current_count, longest_count, last_activity_date
            FROM user_streaks
            WHERE user_id = $1
            """,
            user_id,
        )

    async def check_streak_at_risk(self, user_id: str) -> list:
        """Check which streaks are at risk of being lost."""
        yesterday = date.today() - timedelta(days=1)
        return await self.db.fetch(
            """
            SELECT streak_type, current_count
            FROM user_streaks
            WHERE user_id = $1
              AND last_activity_date = $2
              AND current_count >= 7
            """,
            user_id,
            yesterday,
        )
```

### StreakBanner Component

```tsx
// ui/agent-dashboard/src/components/Gamification/StreakBanner.tsx

import { useQuery } from "@tanstack/react-query";
import { Flame, TrendingUp, AlertTriangle } from "lucide-react";
import { achievementsApi } from "@/api/achievements";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export function StreakBanner() {
  const { data: streaks, isLoading } = useQuery({
    queryKey: ["user-streaks"],
    queryFn: achievementsApi.getStreaks,
  });

  if (isLoading || !streaks?.length) return null;

  const loginStreak = streaks.find((s) => s.streak_type === "login");
  const profitStreak = streaks.find(
    (s) => s.streak_type === "profitable_signal",
  );

  // Determine next milestone
  const nextMilestone = getNextMilestone(loginStreak?.current_count || 0);

  return (
    <Card className="p-4 bg-gradient-to-r from-orange-500/10 to-red-500/10 border-orange-500/20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          {/* Login streak */}
          {loginStreak && (
            <div className="flex items-center gap-2">
              <Flame className="h-6 w-6 text-orange-500" />
              <div>
                <div className="font-bold text-lg">
                  {loginStreak.current_count} day streak
                </div>
                <div className="text-xs text-muted-foreground">
                  Login streak
                </div>
              </div>
            </div>
          )}

          {/* Profit streak */}
          {profitStreak && profitStreak.current_count > 0 && (
            <div className="flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-green-500" />
              <div>
                <div className="font-bold text-lg">
                  {profitStreak.current_count} wins
                </div>
                <div className="text-xs text-muted-foreground">
                  Profit streak
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Next milestone */}
        {loginStreak && nextMilestone && (
          <div className="text-right">
            <div className="text-xs text-muted-foreground mb-1">
              Next: {nextMilestone.name} ({nextMilestone.days} days)
            </div>
            <Progress
              value={(loginStreak.current_count / nextMilestone.days) * 100}
              className="w-32 h-2"
            />
          </div>
        )}
      </div>

      {/* At risk warning */}
      {loginStreak && isAtRisk(loginStreak) && (
        <div className="mt-3 flex items-center gap-2 text-sm text-amber-500">
          <AlertTriangle className="h-4 w-4" />
          Don't lose your streak! Come back tomorrow.
        </div>
      )}
    </Card>
  );
}

function getNextMilestone(current: number) {
  const milestones = [
    { days: 7, name: "Week Warrior" },
    { days: 30, name: "Monthly Dedication" },
    { days: 100, name: "Century Club" },
    { days: 365, name: "Year of Commitment" },
  ];

  return milestones.find((m) => m.days > current);
}

function isAtRisk(streak: { last_activity_date: string }) {
  const lastDate = new Date(streak.last_activity_date);
  const today = new Date();
  const diffDays = Math.floor(
    (today.getTime() - lastDate.getTime()) / (1000 * 60 * 60 * 24),
  );
  return diffDays === 0; // Activity was today, need to come back tomorrow
}
```

## Achievements

### Achievement Categories

| Category   | Examples                     | Color  |
| ---------- | ---------------------------- | ------ |
| Trading    | First win, 10 wins, 100 wins | Green  |
| Engagement | Streak milestones            | Orange |
| Social     | Followers milestones         | Blue   |
| Provider   | First signal, verified       | Purple |
| Special    | Early adopter, events        | Gold   |

### Achievement Rarity

| Rarity    | Color       | % of Users |
| --------- | ----------- | ---------- |
| Common    | Gray        | 50%+       |
| Uncommon  | Green       | 25-50%     |
| Rare      | Blue        | 10-25%     |
| Epic      | Purple      | 1-10%      |
| Legendary | Orange/Gold | <1%        |

### Achievement Display

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR ACHIEVEMENTS                          Total Points: 425   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  UNLOCKED (8)                                                   │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐│
│  │ 🎯 │ │ 🏆 │ │ 📈 │ │ 🔥 │ │ 💪 │ │ 👥 │ │ 📡 │ │ 🤝 ││
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘│
│                                                                  │
│  IN PROGRESS (3)                                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 💰 Consistent Winner (100 wins)                     70/100  ││
│  │ ████████████████████████████████████░░░░░░░░░░░░░░    70%   ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ⭐ Century Club (100-day streak)                    14/100  ││
│  │ ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    14%   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### AchievementBadge Component

```tsx
// ui/agent-dashboard/src/components/Gamification/AchievementBadge.tsx

import { useState } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface AchievementBadgeProps {
  achievement: {
    id: string;
    name: string;
    description: string;
    icon: string;
    rarity: "common" | "uncommon" | "rare" | "epic" | "legendary";
    points: number;
    unlocked_at?: string;
  };
  size?: "sm" | "md" | "lg";
  showTooltip?: boolean;
}

export function AchievementBadge({
  achievement,
  size = "md",
  showTooltip = true,
}: AchievementBadgeProps) {
  const isUnlocked = !!achievement.unlocked_at;

  const badge = (
    <div
      className={cn(
        "relative rounded-full flex items-center justify-center transition-all",
        sizeClasses[size],
        isUnlocked
          ? rarityClasses[achievement.rarity]
          : "bg-muted text-muted-foreground opacity-50 grayscale",
      )}
    >
      <span className={cn("text-center", iconSizeClasses[size])}>
        {achievement.icon}
      </span>

      {/* Rarity glow for epic/legendary */}
      {isUnlocked && ["epic", "legendary"].includes(achievement.rarity) && (
        <div
          className={cn(
            "absolute inset-0 rounded-full animate-pulse",
            achievement.rarity === "epic" && "bg-purple-500/20",
            achievement.rarity === "legendary" && "bg-orange-500/20",
          )}
        />
      )}
    </div>
  );

  if (!showTooltip) return badge;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent className="max-w-xs">
          <div className="space-y-1">
            <div className="font-bold flex items-center gap-2">
              {achievement.name}
              <span
                className={cn(
                  "text-xs px-1.5 rounded",
                  rarityBadgeClasses[achievement.rarity],
                )}
              >
                {achievement.rarity}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              {achievement.description}
            </p>
            <p className="text-xs text-muted-foreground">
              {achievement.points} points
            </p>
            {achievement.unlocked_at && (
              <p className="text-xs text-green-500">
                Unlocked {formatDate(achievement.unlocked_at)}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

const sizeClasses = {
  sm: "w-8 h-8",
  md: "w-12 h-12",
  lg: "w-16 h-16",
};

const iconSizeClasses = {
  sm: "text-lg",
  md: "text-2xl",
  lg: "text-3xl",
};

const rarityClasses = {
  common: "bg-slate-700 text-slate-200 ring-1 ring-slate-600",
  uncommon: "bg-green-900 text-green-200 ring-1 ring-green-600",
  rare: "bg-blue-900 text-blue-200 ring-1 ring-blue-500",
  epic: "bg-purple-900 text-purple-200 ring-2 ring-purple-500",
  legendary:
    "bg-gradient-to-br from-orange-600 to-yellow-500 text-white ring-2 ring-orange-400",
};

const rarityBadgeClasses = {
  common: "bg-slate-600 text-slate-200",
  uncommon: "bg-green-600 text-green-100",
  rare: "bg-blue-600 text-blue-100",
  epic: "bg-purple-600 text-purple-100",
  legendary: "bg-gradient-to-r from-orange-500 to-yellow-500 text-white",
};
```

### Achievement Grid

```tsx
// ui/agent-dashboard/src/components/Gamification/AchievementGrid.tsx

import { useQuery } from "@tanstack/react-query";
import { AchievementBadge } from "./AchievementBadge";
import { Progress } from "@/components/ui/progress";
import { achievementsApi } from "@/api/achievements";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function AchievementGrid() {
  const { data, isLoading } = useQuery({
    queryKey: ["user-achievements"],
    queryFn: achievementsApi.getUserAchievements,
  });

  const { data: allAchievements } = useQuery({
    queryKey: ["all-achievements"],
    queryFn: achievementsApi.getAllAchievements,
  });

  if (isLoading) return <AchievementGridSkeleton />;

  const unlockedIds = new Set(
    data?.unlocked.map((a) => a.achievement_id) || [],
  );
  const totalPoints = data?.total_points || 0;

  // Group by category
  const categories = ["trading", "engagement", "social", "provider", "special"];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Achievements</h2>
        <div className="text-sm text-muted-foreground">
          Total Points:{" "}
          <span className="font-bold text-foreground">{totalPoints}</span>
        </div>
      </div>

      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="unlocked">
            Unlocked ({data?.unlocked.length || 0})
          </TabsTrigger>
          <TabsTrigger value="progress">In Progress</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-4">
          {categories.map((category) => (
            <div key={category} className="mb-6">
              <h3 className="text-sm font-medium text-muted-foreground uppercase mb-3">
                {category}
              </h3>
              <div className="flex flex-wrap gap-3">
                {allAchievements
                  ?.filter((a) => a.category === category)
                  .map((achievement) => (
                    <AchievementBadge
                      key={achievement.id}
                      achievement={{
                        ...achievement,
                        unlocked_at: data?.unlocked.find(
                          (u) => u.achievement_id === achievement.id,
                        )?.unlocked_at,
                      }}
                    />
                  ))}
              </div>
            </div>
          ))}
        </TabsContent>

        <TabsContent value="unlocked" className="mt-4">
          <div className="flex flex-wrap gap-3">
            {data?.unlocked.map((unlock) => {
              const achievement = allAchievements?.find(
                (a) => a.id === unlock.achievement_id,
              );
              if (!achievement) return null;
              return (
                <AchievementBadge
                  key={unlock.achievement_id}
                  achievement={{
                    ...achievement,
                    unlocked_at: unlock.unlocked_at,
                  }}
                  size="lg"
                />
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="progress" className="mt-4">
          <div className="space-y-4">
            {data?.next_achievements.map((next) => (
              <div key={next.id} className="flex items-center gap-4">
                <AchievementBadge
                  achievement={{ ...next, unlocked_at: undefined }}
                  showTooltip={false}
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{next.name}</span>
                    <span className="text-sm text-muted-foreground">
                      {next.progress}/{next.target}
                    </span>
                  </div>
                  <Progress value={(next.progress / next.target) * 100} />
                </div>
              </div>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

## Leaderboards

### Leaderboard Types

| Type          | Metric          | Period   | Update    |
| ------------- | --------------- | -------- | --------- |
| Top Followers | Total followers | All-time | Hourly    |
| Win Rate      | Win percentage  | All-time | Hourly    |
| Monthly ROI   | Average return  | Monthly  | Daily     |
| Streak Kings  | Current streak  | Current  | Real-time |
| Rising Stars  | Follower growth | Weekly   | Daily     |

### Leaderboard Component

```tsx
// ui/agent-dashboard/src/components/Gamification/Leaderboard.tsx

import { useQuery } from "@tanstack/react-query";
import { Trophy, TrendingUp, Flame, Star, Rocket } from "lucide-react";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card } from "@/components/ui/card";
import { leaderboardsApi } from "@/api/leaderboards";
import { cn } from "@/lib/utils";

type LeaderboardType =
  | "followers"
  | "win_rate"
  | "return"
  | "streak"
  | "rising";

export function Leaderboard() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold flex items-center gap-2">
        <Trophy className="h-5 w-5 text-yellow-500" />
        Leaderboards
      </h2>

      <Tabs defaultValue="followers">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="followers" className="gap-1">
            <Trophy className="h-4 w-4" />
            <span className="hidden sm:inline">Followers</span>
          </TabsTrigger>
          <TabsTrigger value="win_rate" className="gap-1">
            <TrendingUp className="h-4 w-4" />
            <span className="hidden sm:inline">Win Rate</span>
          </TabsTrigger>
          <TabsTrigger value="return" className="gap-1">
            <Star className="h-4 w-4" />
            <span className="hidden sm:inline">ROI</span>
          </TabsTrigger>
          <TabsTrigger value="streak" className="gap-1">
            <Flame className="h-4 w-4" />
            <span className="hidden sm:inline">Streak</span>
          </TabsTrigger>
          <TabsTrigger value="rising" className="gap-1">
            <Rocket className="h-4 w-4" />
            <span className="hidden sm:inline">Rising</span>
          </TabsTrigger>
        </TabsList>

        {(
          [
            "followers",
            "win_rate",
            "return",
            "streak",
            "rising",
          ] as LeaderboardType[]
        ).map((type) => (
          <TabsContent key={type} value={type}>
            <LeaderboardList type={type} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

function LeaderboardList({ type }: { type: LeaderboardType }) {
  const { data, isLoading } = useQuery({
    queryKey: ["leaderboard", type],
    queryFn: () => leaderboardsApi.getLeaderboard(type),
  });

  if (isLoading) return <LeaderboardSkeleton />;

  return (
    <Card className="divide-y">
      {data?.entries.map((entry, index) => (
        <div
          key={entry.provider.user_id}
          className={cn(
            "flex items-center gap-4 p-4",
            index < 3 && "bg-gradient-to-r from-yellow-500/5 to-transparent",
          )}
        >
          {/* Rank */}
          <div
            className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center font-bold",
              index === 0 && "bg-yellow-500 text-yellow-950",
              index === 1 && "bg-slate-400 text-slate-950",
              index === 2 && "bg-orange-600 text-orange-950",
              index > 2 && "bg-muted text-muted-foreground",
            )}
          >
            {entry.rank}
          </div>

          {/* Provider */}
          <Avatar className="h-10 w-10">
            <AvatarImage src={entry.provider.avatar_url} />
            <AvatarFallback>{entry.provider.display_name[0]}</AvatarFallback>
          </Avatar>

          <div className="flex-1">
            <div className="font-medium flex items-center gap-2">
              {entry.provider.display_name}
              {entry.provider.is_verified && (
                <span className="text-blue-500">✓</span>
              )}
            </div>
          </div>

          {/* Value */}
          <div className="text-right">
            <div className="font-bold">{formatValue(type, entry.value)}</div>
            {entry.change !== 0 && (
              <div
                className={cn(
                  "text-xs",
                  entry.change > 0 ? "text-green-500" : "text-red-500",
                )}
              >
                {entry.change > 0 ? "+" : ""}
                {formatChange(type, entry.change)}
              </div>
            )}
          </div>
        </div>
      ))}
    </Card>
  );
}

function formatValue(type: LeaderboardType, value: number): string {
  switch (type) {
    case "followers":
      return value >= 1000 ? `${(value / 1000).toFixed(1)}K` : value.toString();
    case "win_rate":
      return `${(value * 100).toFixed(1)}%`;
    case "return":
      return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
    case "streak":
      return `${value} days`;
    case "rising":
      return `+${value}`;
  }
}

function formatChange(type: LeaderboardType, change: number): string {
  if (type === "followers" || type === "rising") {
    return change.toString();
  }
  return `${(change * 100).toFixed(1)}%`;
}
```

## Referral Program

### Referral Tiers

| Tier   | Referrals | Referrer Reward | Referee Reward | Bonus                     |
| ------ | --------- | --------------- | -------------- | ------------------------- |
| Bronze | 1-4       | $25 credit      | $25 credit     | -                         |
| Silver | 5-9       | $50 credit      | $25 credit     | -                         |
| Gold   | 10+       | $75 credit      | $50 credit     | 5% lifetime revenue share |

### Referral Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  REFERRAL PROGRAM                                      🥈 Silver │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  YOUR REFERRAL LINK                                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ https://tradestream.io/join/KING42         [Copy] [Share]   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  STATS                                                          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ Total        │ Qualified    │ Pending      │ Earned       │  │
│  │ Referrals    │ Referrals    │ Referrals    │ Total        │  │
│  │    7         │    5         │    2         │   $250       │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                  │
│  NEXT TIER: 🥇 Gold (3 more referrals)                          │
│  ████████████████████████████████████░░░░░░░░░░  70%            │
│                                                                  │
│  RECENT REFERRALS                                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Trader*** │ Qualified │ +$50 │ Jan 21, 2025                ││
│  │ Crypto*** │ Pending   │ --   │ Jan 28, 2025                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### ReferralDashboard Component

```tsx
// ui/agent-dashboard/src/components/Gamification/ReferralDashboard.tsx

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Copy, Check, Share2, Gift, Users, DollarSign } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { referralsApi } from "@/api/referrals";
import { cn } from "@/lib/utils";

export function ReferralDashboard() {
  const [copied, setCopied] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["referral-dashboard"],
    queryFn: referralsApi.getDashboard,
  });

  if (isLoading) return <ReferralDashboardSkeleton />;

  const referralUrl = data?.referral_url || "";

  const copyLink = async () => {
    await navigator.clipboard.writeText(referralUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const share = async () => {
    if (navigator.share) {
      await navigator.share({
        title: "Join TradeStream",
        text: "Get AI-powered trading signals",
        url: referralUrl,
      });
    }
  };

  const tierProgress = data?.next_tier
    ? (data.stats.total_referrals /
        (data.stats.total_referrals + data.next_tier.referrals_needed)) *
      100
    : 100;

  return (
    <div className="space-y-6">
      {/* Header with tier */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Gift className="h-5 w-5 text-primary" />
          Referral Program
        </h2>
        <TierBadge tier={data?.tier} />
      </div>

      {/* Referral link */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Your Referral Link</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input value={referralUrl} readOnly className="font-mono text-sm" />
            <Button variant="outline" onClick={copyLink}>
              {copied ? (
                <Check className="h-4 w-4" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
            <Button variant="outline" onClick={share}>
              <Share2 className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          icon={Users}
          label="Total Referrals"
          value={data?.stats.total_referrals || 0}
        />
        <StatCard
          icon={Check}
          label="Qualified"
          value={data?.stats.qualified_referrals || 0}
          color="text-green-500"
        />
        <StatCard
          icon={Users}
          label="Pending"
          value={data?.stats.pending_referrals || 0}
          color="text-yellow-500"
        />
        <StatCard
          icon={DollarSign}
          label="Total Earned"
          value={`$${data?.stats.total_earned || 0}`}
          color="text-primary"
        />
      </div>

      {/* Next tier progress */}
      {data?.next_tier && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">
                Next: {data.next_tier.icon} {data.next_tier.name}
              </span>
              <span className="text-sm">
                {data.next_tier.referrals_needed} more referrals
              </span>
            </div>
            <Progress value={tierProgress} />
            <p className="text-xs text-muted-foreground mt-2">
              Earn ${data.next_tier.referrer_reward} per referral at{" "}
              {data.next_tier.name} tier
            </p>
          </CardContent>
        </Card>
      )}

      {/* Recent referrals */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent Referrals</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {data?.referrals.map((referral) => (
              <div
                key={referral.referee_name}
                className="flex items-center justify-between py-2 border-b last:border-0"
              >
                <div className="flex items-center gap-3">
                  <div className="font-medium">{referral.referee_name}</div>
                  <StatusBadge status={referral.status} />
                </div>
                <div className="text-right">
                  {referral.reward_amount ? (
                    <span className="text-green-500">
                      +${referral.reward_amount}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">--</span>
                  )}
                </div>
              </div>
            ))}

            {data?.referrals.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                No referrals yet. Share your link to get started!
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Rewards explanation */}
      <Card className="bg-muted/50">
        <CardContent className="pt-6">
          <h3 className="font-medium mb-3">How It Works</h3>
          <ol className="space-y-2 text-sm text-muted-foreground">
            <li>1. Share your unique referral link with friends</li>
            <li>2. They sign up and follow their first signal</li>
            <li>3. Both of you earn rewards!</li>
            <li>4. Reach higher tiers for bigger rewards</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}

function TierBadge({
  tier,
}: {
  tier?: { id: string; name: string; icon: string };
}) {
  if (!tier) return null;

  const tierColors = {
    bronze: "bg-orange-600/20 text-orange-500 border-orange-500/50",
    silver: "bg-slate-500/20 text-slate-300 border-slate-400/50",
    gold: "bg-yellow-500/20 text-yellow-500 border-yellow-500/50",
  };

  return (
    <div
      className={cn(
        "px-3 py-1 rounded-full border text-sm font-medium",
        tierColors[tier.id as keyof typeof tierColors],
      )}
    >
      {tier.icon} {tier.name}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const statusStyles = {
    pending: "bg-yellow-500/20 text-yellow-500",
    qualified: "bg-green-500/20 text-green-500",
    rewarded: "bg-blue-500/20 text-blue-500",
  };

  return (
    <span
      className={cn(
        "px-2 py-0.5 rounded text-xs",
        statusStyles[status as keyof typeof statusStyles],
      )}
    >
      {status}
    </span>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <Icon
          className={cn("h-5 w-5 mb-2", color || "text-muted-foreground")}
        />
        <div className={cn("text-2xl font-bold", color)}>{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}
```

## Notification Triggers

### Streak Notifications

| Trigger           | Message                                              | Timing      |
| ----------------- | ---------------------------------------------------- | ----------- |
| Streak at risk    | "Don't lose your 14-day streak! Open the app today." | 6 PM local  |
| Streak lost       | "Your 14-day streak ended. Start a new one today!"   | Next login  |
| Milestone reached | "You reached a 30-day streak! 🔥"                    | Immediately |

### Achievement Notifications

| Trigger              | Message                                           | Channel      |
| -------------------- | ------------------------------------------------- | ------------ |
| Achievement unlocked | "Achievement unlocked: First Win 🏆"              | Push, in-app |
| New badge available  | "You're 3 wins away from Consistent Winner!"      | Push         |
| Leaderboard movement | "You moved up to #5 on the Win Rate leaderboard!" | In-app       |

## Constraints

- Streaks reset at midnight in user's timezone
- Achievements are permanent once unlocked
- Leaderboard requires minimum 10 signals to qualify
- Referral rewards require referee to complete first signal
- Maximum 500 referrals per user (prevent abuse)

## Acceptance Criteria

- [ ] Login streak increments on daily visit
- [ ] Streak displays correctly with progress to next milestone
- [ ] Streak at-risk notification sent at 6 PM local time
- [ ] Streak history recorded when streak breaks
- [ ] Achievement unlocks trigger notification
- [ ] Achievement badge displays with correct rarity styling
- [ ] Progress toward next achievement shown accurately
- [ ] Leaderboard shows top 50 by each metric
- [ ] Leaderboard updates hourly via materialized view
- [ ] User's rank shown if in top 100
- [ ] Referral code auto-generated for new users
- [ ] Referral link copies to clipboard
- [ ] Referral tracking captures signup and qualification
- [ ] Tier upgrade triggers when threshold reached
- [ ] Rewards credited correctly based on tier
- [ ] Referral dashboard shows accurate stats

## Notes

### Streak Timezone Handling

```python
# Use user's timezone for streak calculations
from datetime import date
import pytz

def get_user_today(user_timezone: str) -> date:
    tz = pytz.timezone(user_timezone)
    return datetime.now(tz).date()
```

### Leaderboard Materialized View Refresh

```sql
-- Scheduled via K8s CronJob every hour
REFRESH MATERIALIZED VIEW CONCURRENTLY leaderboard_top_providers;
```

### Anti-Gaming Measures

- Minimum 24 hours between login streak increments
- Referral abuse detection (same IP, similar emails)
- Achievement progress validated server-side
- Rate limiting on achievement check endpoints
