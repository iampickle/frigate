import ActivityIndicator from "@/components/indicators/activity-indicator";
import { CameraNameLabel } from "@/components/camera/FriendlyNameLabel";
import Heading from "@/components/ui/heading";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import useSWR from "swr";

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

export type NotificationWeightStats = {
  camera: string;
  current_hour: number;
  active_weights_current_hour: number;
  normalized_weight_current_hour: number;
  total_weights_24h: number;
  total_normalized_weights_24h: number;
  hourly_breakdown: { [hour: string]: number };
  normalized_hourly_breakdown: { [hour: string]: number };
  cooldown: {
    base: number;
    current: number;
    multiplier: number;
  };
  weight_factors: {
    base: number;
    dynamic: number;
    adjustment: number;
  };
  last_notification: {
    timestamp: number | null;
    seconds_ago: number | null;
    formatted: string | null;
  };
  next_notification_allowed_in: number;
};

export type NotificationWeightStatsResponse = {
  [camera: string]: NotificationWeightStats;
};

function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "0s";
  }

  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }

  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }

  return `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
}

type StatProps = {
  label: string;
  value: string;
  className?: string;
};

function Stat({ label, value, className }: StatProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="text-xs text-primary-variant">{label}</div>
      <div className={cn("text-sm text-primary", className)}>{value}</div>
    </div>
  );
}

type CameraWeightDistributionProps = {
  stats: NotificationWeightStats;
};

function CameraWeightDistribution({ stats }: CameraWeightDistributionProps) {
  const { t } = useTranslation(["views/settings"]);

  const hourly = useMemo(
    () =>
      HOURS.map((hour) => ({
        hour,
        normalized: stats.normalized_hourly_breakdown?.[String(hour)] ?? 0,
        raw: stats.hourly_breakdown?.[String(hour)] ?? 0,
      })),
    [stats],
  );

  const maxNormalized = useMemo(
    () => Math.max(...hourly.map((entry) => entry.normalized), 0),
    [hourly],
  );

  return (
    <div className="flex flex-col gap-4 rounded-lg bg-secondary p-5">
      <div className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CameraNameLabel
          className="text-md text-primary smart-capitalize"
          camera={stats.camera}
        />
        <div className="text-sm text-primary-variant">
          {t("notification.weightDistribution.currentWeight", {
            weight: stats.normalized_weight_current_hour.toFixed(2),
            hour: String(stats.current_hour).padStart(2, "0"),
          })}
        </div>
      </div>

      <div className="flex h-28 flex-row items-end gap-0.5">
        {hourly.map((entry) => {
          const height =
            maxNormalized > 0 ? (entry.normalized / maxNormalized) * 100 : 0;
          const isCurrent = entry.hour === stats.current_hour;

          return (
            <div
              key={entry.hour}
              className="flex h-full flex-1 flex-col justify-end"
              title={t("notification.weightDistribution.barTooltip", {
                hour: String(entry.hour).padStart(2, "0"),
                normalized: entry.normalized.toFixed(2),
                notifications: entry.raw,
              })}
            >
              <div
                className={cn(
                  "w-full rounded-t-sm transition-all",
                  entry.normalized > 0 ? "bg-selected" : "bg-muted",
                  isCurrent && "bg-success",
                )}
                style={{ height: `${Math.max(height, 2)}%` }}
              />
            </div>
          );
        })}
      </div>

      <div className="flex flex-row justify-between text-xs text-primary-variant">
        {[0, 6, 12, 18, 23].map((hour) => (
          <span key={hour}>{String(hour).padStart(2, "0")}</span>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Stat
          label={t("notification.weightDistribution.baseCooldown")}
          value={formatSeconds(stats.cooldown.base)}
        />
        <Stat
          label={t("notification.weightDistribution.currentCooldown")}
          value={formatSeconds(stats.cooldown.current)}
          className={cn(stats.cooldown.multiplier > 1 && "text-danger")}
        />
        <Stat
          label={t("notification.weightDistribution.multiplier")}
          value={`${stats.cooldown.multiplier.toFixed(2)}x`}
        />
        <Stat
          label={t("notification.weightDistribution.weightFactor")}
          value={`${stats.weight_factors.base.toFixed(2)} → ${stats.weight_factors.dynamic.toFixed(2)}`}
        />
        <Stat
          label={t("notification.weightDistribution.total24h")}
          value={`${stats.total_weights_24h} (${stats.total_normalized_weights_24h.toFixed(2)})`}
        />
        <Stat
          label={t("notification.weightDistribution.lastNotification")}
          value={
            stats.last_notification.formatted ??
            t("notification.weightDistribution.never")
          }
        />
        <Stat
          label={t("notification.weightDistribution.nextAllowedIn")}
          value={formatSeconds(stats.next_notification_allowed_in)}
          className={cn(
            stats.next_notification_allowed_in > 0
              ? "text-danger"
              : "text-success",
          )}
        />
      </div>
    </div>
  );
}

export default function NotificationWeightDistribution() {
  const { t } = useTranslation(["views/settings"]);

  const { data: weightStats, isLoading } = useSWR<NotificationWeightStatsResponse>(
    "notifications/weight-stats",
    { refreshInterval: 30000, revalidateOnFocus: true },
  );

  const cameras = useMemo(
    () =>
      Object.entries(weightStats ?? {})
        .filter(([, stats]) => stats?.normalized_hourly_breakdown != undefined)
        .map(([camera]) => camera)
        .sort(),
    [weightStats],
  );

  return (
    <div className="mt-4 gap-2 space-y-6">
      <div className="space-y-3">
        <Separator className="my-2 flex bg-secondary" />
        <Heading as="h4" className="my-2">
          {t("notification.weightDistribution.title")}
        </Heading>
        <div className="max-w-xl">
          <div className="mb-5 mt-2 flex flex-col gap-2 text-sm text-primary-variant">
            <p>{t("notification.weightDistribution.desc")}</p>
          </div>
        </div>

        <div className="flex max-w-2xl flex-col gap-2.5">
          {isLoading && !weightStats ? (
            <ActivityIndicator />
          ) : cameras.length == 0 ? (
            <div className="rounded-lg bg-secondary p-5 text-sm text-primary-variant">
              {t("notification.weightDistribution.noData")}
            </div>
          ) : (
            cameras.map((camera) => (
              <CameraWeightDistribution
                key={camera}
                stats={weightStats![camera]}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
