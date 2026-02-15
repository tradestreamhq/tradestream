# Social Features Specification

## Goal

Enable viral growth through social features: provider profiles with verified stats, one-click follow system, social feed, reactions, comments, and shareable win cards.

## Target Behavior

Social features transform passive signal consumers into an engaged community where providers build audiences and users share their wins, creating organic growth loops.

## Feature Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOCIAL FEATURE ECOSYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  Provider   │───▶│   Signals   │───▶│   Social Feed      │  │
│  │  Profiles   │    │  + Comments │    │   (Following)       │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│         │                  │                     │              │
│         │                  │                     │              │
│         ▼                  ▼                     ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  Follow     │    │  Reactions  │    │   Win Cards        │  │
│  │  System     │    │  (Likes)    │    │   (Shareable)      │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Profiles

### Profile Display

```
┌─────────────────────────────────────────────────────────────────┐
│  [Banner Image]                                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────┐                                                       │
│  │Avatar│  @CryptoKing_42              ✅ Verified Pro          │
│  └──────┘  Trading since 2017. Focus on momentum strategies.    │
│                                                                  │
│            🌐 cryptoking.io  𝕏 @cryptoking42                    │
│                                                                  │
│            [Follow] [Notify] [Share Profile]                    │
├─────────────────────────────────────────────────────────────────┤
│  PERFORMANCE STATS                                              │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │ Win Rate     │ Avg Return   │ Total Return │ Followers    │  │
│  │   67.3%      │   +4.2%      │   +245%      │   12.4K      │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                  │
│  Current Streak: 🔥 14 days │ Longest: 28 days                  │
│  Sharpe Ratio: 1.82 │ Max Drawdown: 15%                         │
│                                                                  │
│  Risk Level: ⚡ Aggressive                                       │
│  Specialties: #crypto #momentum #scalping                       │
├─────────────────────────────────────────────────────────────────┤
│  STRATEGY DESCRIPTION                                           │
│  I focus on RSI reversals and MACD crossovers on 4H timeframe.  │
│  Primarily trade BTC, ETH, and SOL during high-volume periods.  │
├─────────────────────────────────────────────────────────────────┤
│  RECENT SIGNALS                                                 │
│  [Signal cards from this provider]                              │
└─────────────────────────────────────────────────────────────────┘
```

### Provider Stats Calculation

Stats are calculated by a background job and cached in the `providers` table:

```python
# services/gateway/services/provider_stats.py

from datetime import datetime, timedelta
from typing import Optional
import asyncpg


class ProviderStatsService:
    def __init__(self, db: asyncpg.Pool):
        self.db = db

    async def calculate_provider_stats(self, provider_id: str) -> dict:
        """Calculate all stats for a provider."""

        # Get all signals from this provider
        signals = await self.db.fetch(
            """
            SELECT
                ps.outcome,
                ps.actual_return,
                ps.created_at
            FROM provider_signals ps
            WHERE ps.provider_id = $1
              AND ps.outcome IS NOT NULL
            ORDER BY ps.created_at DESC
            """,
            provider_id,
        )

        if not signals:
            return self._empty_stats()

        # Calculate stats
        total_signals = len(signals)
        wins = [s for s in signals if s["outcome"] == "PROFIT"]
        losses = [s for s in signals if s["outcome"] == "LOSS"]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / total_signals if total_signals > 0 else 0

        returns = [s["actual_return"] for s in signals if s["actual_return"]]
        avg_return = sum(returns) / len(returns) if returns else 0
        total_return = sum(returns) if returns else 0

        # Calculate streak
        current_streak = self._calculate_current_streak(signals)
        longest_streak = await self._get_longest_streak(provider_id)

        # Calculate Sharpe ratio (simplified)
        sharpe = self._calculate_sharpe(returns)

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(returns)

        return {
            "total_signals": total_signals,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "total_return": total_return,
            "current_streak": current_streak,
            "longest_streak": max(longest_streak, current_streak),
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
        }

    def _calculate_current_streak(self, signals: list) -> int:
        """Calculate current winning streak."""
        streak = 0
        for s in signals:
            if s["outcome"] == "PROFIT":
                streak += 1
            else:
                break
        return streak

    def _calculate_sharpe(self, returns: list, risk_free_rate: float = 0.0) -> float:
        """Calculate simplified Sharpe ratio."""
        if len(returns) < 2:
            return 0.0

        import statistics
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        if std_return == 0:
            return 0.0

        return (mean_return - risk_free_rate) / std_return

    def _calculate_max_drawdown(self, returns: list) -> float:
        """Calculate maximum drawdown."""
        if not returns:
            return 0.0

        cumulative = 0
        peak = 0
        max_dd = 0

        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            drawdown = (peak - cumulative) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

        return max_dd

    def _empty_stats(self) -> dict:
        return {
            "total_signals": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
            "current_streak": 0,
            "longest_streak": 0,
            "sharpe_ratio": None,
            "max_drawdown": None,
        }


async def update_all_provider_stats(db: asyncpg.Pool):
    """Background job to update all provider stats."""
    service = ProviderStatsService(db)

    providers = await db.fetch("SELECT user_id FROM providers")

    for provider in providers:
        stats = await service.calculate_provider_stats(provider["user_id"])

        await db.execute(
            """
            UPDATE providers SET
                total_signals = $2,
                win_count = $3,
                loss_count = $4,
                win_rate = $5,
                avg_return = $6,
                total_return = $7,
                current_streak = $8,
                longest_streak = $9,
                sharpe_ratio = $10,
                max_drawdown = $11,
                updated_at = NOW()
            WHERE user_id = $1
            """,
            provider["user_id"],
            stats["total_signals"],
            stats["win_count"],
            stats["loss_count"],
            stats["win_rate"],
            stats["avg_return"],
            stats["total_return"],
            stats["current_streak"],
            stats["longest_streak"],
            stats["sharpe_ratio"],
            stats["max_drawdown"],
        )
```

### Verification Levels

| Level | Badge | Requirements |
|-------|-------|--------------|
| None | - | New provider |
| Basic | ✓ | 10+ signals, email verified |
| Pro | ✅ | 50+ signals, 60%+ win rate, 30+ followers |
| Elite | 👑 | 200+ signals, 65%+ win rate, 500+ followers |

## Follow System

### Follow Button Component

```tsx
// ui/agent-dashboard/src/components/Social/FollowButton.tsx

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Bell, BellOff, UserPlus, UserMinus } from 'lucide-react';
import { useFollow } from '@/hooks/useFollow';

interface FollowButtonProps {
  providerId: string;
  isFollowing: boolean;
  notifyOnSignal: boolean;
  followerCount: number;
}

export function FollowButton({
  providerId,
  isFollowing: initialFollowing,
  notifyOnSignal: initialNotify,
  followerCount: initialCount,
}: FollowButtonProps) {
  const [isFollowing, setIsFollowing] = useState(initialFollowing);
  const [notifyOnSignal, setNotifyOnSignal] = useState(initialNotify);
  const [followerCount, setFollowerCount] = useState(initialCount);
  const { follow, unfollow, toggleNotify, isLoading } = useFollow();

  const handleFollow = async () => {
    if (isFollowing) {
      await unfollow(providerId);
      setIsFollowing(false);
      setFollowerCount((c) => c - 1);
    } else {
      await follow(providerId, true);
      setIsFollowing(true);
      setNotifyOnSignal(true);
      setFollowerCount((c) => c + 1);
    }
  };

  const handleToggleNotify = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isFollowing) return;

    await toggleNotify(providerId, !notifyOnSignal);
    setNotifyOnSignal(!notifyOnSignal);
  };

  return (
    <div className="flex items-center gap-2">
      <Button
        variant={isFollowing ? 'outline' : 'default'}
        size="sm"
        onClick={handleFollow}
        disabled={isLoading}
        className="min-w-[100px]"
      >
        {isFollowing ? (
          <>
            <UserMinus className="mr-2 h-4 w-4" />
            Following
          </>
        ) : (
          <>
            <UserPlus className="mr-2 h-4 w-4" />
            Follow
          </>
        )}
      </Button>

      {isFollowing && (
        <Button
          variant="ghost"
          size="icon"
          onClick={handleToggleNotify}
          className={notifyOnSignal ? 'text-primary' : 'text-muted-foreground'}
          title={notifyOnSignal ? 'Notifications on' : 'Notifications off'}
        >
          {notifyOnSignal ? (
            <Bell className="h-4 w-4" />
          ) : (
            <BellOff className="h-4 w-4" />
          )}
        </Button>
      )}

      <span className="text-sm text-muted-foreground">
        {formatCount(followerCount)} followers
      </span>
    </div>
  );
}

function formatCount(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toString();
}
```

### useFollow Hook

```tsx
// ui/agent-dashboard/src/hooks/useFollow.ts

import { useState } from 'react';
import { socialApi } from '@/api/social';

export function useFollow() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const follow = async (providerId: string, notifyOnSignal: boolean = true) => {
    setIsLoading(true);
    setError(null);
    try {
      await socialApi.follow(providerId, { notifyOnSignal });
    } catch (e) {
      setError(e as Error);
      throw e;
    } finally {
      setIsLoading(false);
    }
  };

  const unfollow = async (providerId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await socialApi.unfollow(providerId);
    } catch (e) {
      setError(e as Error);
      throw e;
    } finally {
      setIsLoading(false);
    }
  };

  const toggleNotify = async (providerId: string, notify: boolean) => {
    setIsLoading(true);
    setError(null);
    try {
      await socialApi.updateFollow(providerId, { notifyOnSignal: notify });
    } catch (e) {
      setError(e as Error);
      throw e;
    } finally {
      setIsLoading(false);
    }
  };

  return { follow, unfollow, toggleNotify, isLoading, error };
}
```

## Social Feed

### Feed Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR FEED                               [All] [BUY] [SELL]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ┌──────┐  @CryptoKing_42 ✅ · 2m ago                       ││
│  │ │Avatar│                                                    ││
│  │ └──────┘  🟢 BUY ETH/USD                                   ││
│  │           Score: 87 │ Confidence: 82%                       ││
│  │                                                             ││
│  │  "Strong RSI reversal setup. Expecting 3-4% move."          ││
│  │                                                             ││
│  │  ❤️ 42    🔥 15    🚀 8    💬 12    📤 Share               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ┌──────┐  @BTCWhale_Pro ✅ · 15m ago                       ││
│  │ │Avatar│                                                    ││
│  │ └──────┘  🔴 SELL BTC/USD                                  ││
│  │           Score: 74 │ Confidence: 71%                       ││
│  │                                                             ││
│  │  ❤️ 28    🔥 5     🚀 2    💬 8     📤 Share               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### SocialFeed Component

```tsx
// ui/agent-dashboard/src/components/Social/SocialFeed.tsx

import { useInfiniteQuery } from '@tanstack/react-query';
import { useInView } from 'react-intersection-observer';
import { useEffect } from 'react';
import { FeedSignalCard } from './FeedSignalCard';
import { socialApi } from '@/api/social';
import { Skeleton } from '@/components/ui/skeleton';

export function SocialFeed() {
  const { ref, inView } = useInView();

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteQuery({
    queryKey: ['social-feed'],
    queryFn: ({ pageParam = 0 }) => socialApi.getFeed({ offset: pageParam }),
    getNextPageParam: (lastPage) => {
      if (lastPage.offset + lastPage.limit >= lastPage.total) {
        return undefined;
      }
      return lastPage.offset + lastPage.limit;
    },
  });

  useEffect(() => {
    if (inView && hasNextPage) {
      fetchNextPage();
    }
  }, [inView, hasNextPage, fetchNextPage]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-48 w-full" />
        ))}
      </div>
    );
  }

  const signals = data?.pages.flatMap((page) => page.signals) ?? [];

  if (signals.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          No signals yet. Follow providers to see their signals here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {signals.map((signal) => (
        <FeedSignalCard key={signal.signal_id} signal={signal} />
      ))}

      <div ref={ref} className="h-10">
        {isFetchingNextPage && (
          <div className="flex justify-center">
            <Skeleton className="h-8 w-8 rounded-full" />
          </div>
        )}
      </div>
    </div>
  );
}
```

## Reactions

### Reaction Types

| Reaction | Emoji | Meaning |
|----------|-------|---------|
| like | ❤️ | General approval |
| fire | 🔥 | Hot take |
| rocket | 🚀 | Bullish sentiment |
| sad | 😢 | Missed opportunity |

### ReactionBar Component

```tsx
// ui/agent-dashboard/src/components/Social/ReactionBar.tsx

import { useState } from 'react';
import { Heart, Flame, Rocket, Frown, MessageCircle, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useReaction } from '@/hooks/useReaction';

interface ReactionBarProps {
  signalId: string;
  reactions: {
    like: number;
    fire: number;
    rocket: number;
    sad: number;
  };
  userReactions: string[];  // Reactions user has made
  commentCount: number;
  onComment: () => void;
  onShare: () => void;
}

export function ReactionBar({
  signalId,
  reactions,
  userReactions,
  commentCount,
  onComment,
  onShare,
}: ReactionBarProps) {
  const { addReaction, removeReaction, isLoading } = useReaction(signalId);
  const [localReactions, setLocalReactions] = useState(reactions);
  const [localUserReactions, setLocalUserReactions] = useState(userReactions);

  const handleReaction = async (type: string) => {
    const hasReaction = localUserReactions.includes(type);

    if (hasReaction) {
      await removeReaction(type);
      setLocalUserReactions((r) => r.filter((t) => t !== type));
      setLocalReactions((r) => ({ ...r, [type]: r[type as keyof typeof r] - 1 }));
    } else {
      await addReaction(type);
      setLocalUserReactions((r) => [...r, type]);
      setLocalReactions((r) => ({ ...r, [type]: r[type as keyof typeof r] + 1 }));
    }
  };

  return (
    <div className="flex items-center gap-1 text-sm">
      <ReactionButton
        icon={Heart}
        count={localReactions.like}
        active={localUserReactions.includes('like')}
        activeColor="text-red-500"
        onClick={() => handleReaction('like')}
        disabled={isLoading}
      />
      <ReactionButton
        icon={Flame}
        count={localReactions.fire}
        active={localUserReactions.includes('fire')}
        activeColor="text-orange-500"
        onClick={() => handleReaction('fire')}
        disabled={isLoading}
      />
      <ReactionButton
        icon={Rocket}
        count={localReactions.rocket}
        active={localUserReactions.includes('rocket')}
        activeColor="text-blue-500"
        onClick={() => handleReaction('rocket')}
        disabled={isLoading}
      />
      <ReactionButton
        icon={Frown}
        count={localReactions.sad}
        active={localUserReactions.includes('sad')}
        activeColor="text-yellow-500"
        onClick={() => handleReaction('sad')}
        disabled={isLoading}
      />

      <div className="mx-2 h-4 w-px bg-border" />

      <Button
        variant="ghost"
        size="sm"
        onClick={onComment}
        className="gap-1"
      >
        <MessageCircle className="h-4 w-4" />
        {commentCount}
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={onShare}
        className="gap-1"
      >
        <Share2 className="h-4 w-4" />
        Share
      </Button>
    </div>
  );
}

function ReactionButton({
  icon: Icon,
  count,
  active,
  activeColor,
  onClick,
  disabled,
}: {
  icon: React.ComponentType<{ className?: string }>;
  count: number;
  active: boolean;
  activeColor: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      disabled={disabled}
      className={cn('gap-1 px-2', active && activeColor)}
    >
      <Icon className={cn('h-4 w-4', active && 'fill-current')} />
      {count > 0 && count}
    </Button>
  );
}
```

## Comments

### Comment Thread

```tsx
// ui/agent-dashboard/src/components/Social/CommentThread.tsx

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { socialApi } from '@/api/social';
import { formatRelativeTime } from '@/lib/utils';

interface CommentThreadProps {
  signalId: string;
}

export function CommentThread({ signalId }: CommentThreadProps) {
  const [newComment, setNewComment] = useState('');
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: comments, isLoading } = useQuery({
    queryKey: ['comments', signalId],
    queryFn: () => socialApi.getComments(signalId),
  });

  const postComment = useMutation({
    mutationFn: (data: { content: string; parentId?: string }) =>
      socialApi.postComment(signalId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', signalId] });
      setNewComment('');
      setReplyingTo(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    postComment.mutate({
      content: newComment,
      parentId: replyingTo || undefined,
    });
  };

  if (isLoading) {
    return <div className="animate-pulse h-20 bg-muted rounded" />;
  }

  return (
    <div className="space-y-4">
      {/* New comment form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder={replyingTo ? 'Write a reply...' : 'Add a comment...'}
          className="min-h-[60px] resize-none"
        />
        <Button type="submit" disabled={postComment.isPending}>
          {replyingTo ? 'Reply' : 'Post'}
        </Button>
      </form>

      {replyingTo && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setReplyingTo(null)}
        >
          Cancel reply
        </Button>
      )}

      {/* Comments list */}
      <div className="space-y-4">
        {comments?.map((comment) => (
          <Comment
            key={comment.id}
            comment={comment}
            onReply={() => setReplyingTo(comment.id)}
          />
        ))}
      </div>
    </div>
  );
}

function Comment({
  comment,
  onReply,
  depth = 0,
}: {
  comment: CommentData;
  onReply: () => void;
  depth?: number;
}) {
  return (
    <div className={cn('flex gap-3', depth > 0 && 'ml-8')}>
      <Avatar className="h-8 w-8">
        <AvatarImage src={comment.user.avatar_url} />
        <AvatarFallback>{comment.user.display_name[0]}</AvatarFallback>
      </Avatar>

      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">
            {comment.user.display_name}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatRelativeTime(comment.created_at)}
          </span>
          {comment.is_edited && (
            <span className="text-xs text-muted-foreground">(edited)</span>
          )}
        </div>

        <p className="text-sm mt-1">{comment.content}</p>

        <Button
          variant="ghost"
          size="sm"
          onClick={onReply}
          className="text-xs mt-1"
        >
          Reply
        </Button>

        {/* Nested replies */}
        {comment.replies?.map((reply) => (
          <Comment
            key={reply.id}
            comment={reply}
            onReply={onReply}
            depth={depth + 1}
          />
        ))}
      </div>
    </div>
  );
}
```

## Win Cards (Shareable)

### Win Card Design

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    🚀 TradeStream Win 🚀                        │
│                                                                  │
│             ┌─────────────────────────────────┐                 │
│             │                                 │                 │
│             │         ETH/USD                 │                 │
│             │                                 │                 │
│             │       +12.4%                    │                 │
│             │                                 │                 │
│             │    🔥 14 day streak             │                 │
│             │                                 │                 │
│             └─────────────────────────────────┘                 │
│                                                                  │
│             Powered by @CryptoKing_42's signals                 │
│                                                                  │
│             tradestream.io/join/KING42                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### WinCard Component

```tsx
// ui/agent-dashboard/src/components/Social/WinCard.tsx

import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Download, Twitter, Copy, Check } from 'lucide-react';
import html2canvas from 'html2canvas';

interface WinCardProps {
  signal: {
    symbol: string;
    action: string;
    return_percentage: number;
    provider: {
      display_name: string;
      referral_code: string;
    };
  };
  userStreak?: number;
}

export function WinCard({ signal, userStreak }: WinCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  const referralUrl = `tradestream.io/join/${signal.provider.referral_code}`;

  const downloadImage = async () => {
    if (!cardRef.current) return;

    const canvas = await html2canvas(cardRef.current, {
      backgroundColor: '#0f172a',
      scale: 2,
    });

    const link = document.createElement('a');
    link.download = `tradestream-win-${signal.symbol.replace('/', '-')}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const shareToTwitter = async () => {
    const text = encodeURIComponent(
      `Just made +${signal.return_percentage.toFixed(1)}% on ${signal.symbol} with @TradeStreamIO! 🚀\n\n` +
      `Powered by ${signal.provider.display_name}'s signals.\n\n` +
      `Join: ${referralUrl}`
    );
    window.open(`https://twitter.com/intent/tweet?text=${text}`, '_blank');
  };

  const copyLink = async () => {
    await navigator.clipboard.writeText(`https://${referralUrl}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Shareable card */}
      <div
        ref={cardRef}
        className="w-[400px] h-[500px] bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-8 flex flex-col items-center justify-center text-white"
      >
        <div className="text-2xl mb-6">🚀 TradeStream Win 🚀</div>

        <div className="bg-slate-700/50 rounded-xl p-6 w-full text-center">
          <div className="text-lg text-slate-400 mb-2">{signal.symbol}</div>
          <div
            className={cn(
              'text-5xl font-bold mb-4',
              signal.return_percentage > 0 ? 'text-green-400' : 'text-red-400'
            )}
          >
            {signal.return_percentage > 0 ? '+' : ''}
            {signal.return_percentage.toFixed(1)}%
          </div>
          {userStreak && userStreak >= 3 && (
            <div className="text-xl">🔥 {userStreak} day streak</div>
          )}
        </div>

        <div className="mt-8 text-slate-400">
          Powered by @{signal.provider.display_name}'s signals
        </div>

        <div className="mt-4 text-sm text-slate-500">{referralUrl}</div>
      </div>

      {/* Share buttons */}
      <div className="flex gap-2">
        <Button onClick={downloadImage} variant="outline">
          <Download className="mr-2 h-4 w-4" />
          Download
        </Button>
        <Button onClick={shareToTwitter} variant="outline">
          <Twitter className="mr-2 h-4 w-4" />
          Tweet
        </Button>
        <Button onClick={copyLink} variant="outline">
          {copied ? (
            <>
              <Check className="mr-2 h-4 w-4" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="mr-2 h-4 w-4" />
              Copy Link
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
```

## API Integration

### social.ts (API Client)

```tsx
// ui/agent-dashboard/src/api/social.ts

import { api } from './client';

export const socialApi = {
  // Follow
  follow: (providerId: string, options: { notifyOnSignal: boolean }) =>
    api.post(`/api/social/follow/${providerId}`, options),

  unfollow: (providerId: string) =>
    api.delete(`/api/social/follow/${providerId}`),

  updateFollow: (providerId: string, options: { notifyOnSignal: boolean }) =>
    api.patch(`/api/social/follow/${providerId}`, options),

  getFollowing: () =>
    api.get('/api/social/following'),

  // Feed
  getFeed: (params: { offset?: number; limit?: number }) =>
    api.get('/api/social/feed', { params }),

  // Reactions
  addReaction: (signalId: string, reactionType: string) =>
    api.post(`/api/social/signals/${signalId}/react`, { reaction_type: reactionType }),

  removeReaction: (signalId: string, reactionType: string) =>
    api.delete(`/api/social/signals/${signalId}/react/${reactionType}`),

  // Comments
  getComments: (signalId: string) =>
    api.get(`/api/social/signals/${signalId}/comments`),

  postComment: (signalId: string, data: { content: string; parentId?: string }) =>
    api.post(`/api/social/signals/${signalId}/comments`, data),
};
```

## Constraints

- Follow limit: 500 providers per user
- Comment length: 500 characters max
- Reaction types: Fixed set (like, fire, rocket, sad)
- Win cards: Generated client-side for privacy
- Feed pagination: 20 items per page

## Acceptance Criteria

- [ ] Provider profile shows all stats accurately
- [ ] Verification badges display correctly by level
- [ ] Follow button updates follower count in real-time
- [ ] Notification toggle works for followed providers
- [ ] Social feed shows signals from followed providers
- [ ] Feed updates when following/unfollowing
- [ ] Reactions can be added and removed
- [ ] Reaction counts update optimistically
- [ ] Comments can be posted and displayed
- [ ] Reply threading works (1 level deep)
- [ ] Win card generates with correct data
- [ ] Win card can be downloaded as image
- [ ] Share to Twitter includes referral link
- [ ] Copy link works with referral code
- [ ] Provider stats update via background job
- [ ] Leaderboard materialized view refreshes hourly

## Notes

### Feed Algorithm (Future)

Current: Chronological feed from followed providers.

Future enhancements:
- Trending signals (engagement velocity)
- Similar providers suggestions
- Discovery feed for new users
- Personalized ranking based on preferences

### Anti-Abuse Measures

- Rate limit reactions: 100/hour per user
- Rate limit comments: 20/hour per user
- Duplicate comment detection
- Spam detection on comments
- Report functionality (future)
