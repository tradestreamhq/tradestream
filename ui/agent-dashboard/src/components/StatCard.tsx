import React from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  color?: "green" | "red" | "blue" | "yellow";
}

export function StatCard({ label, value, color }: StatCardProps) {
  return (
    <div className="stat-card" role="status" aria-label={`${label}: ${value}`}>
      <div className="label">{label}</div>
      <div className={`value ${color ?? ""}`}>{value}</div>
    </div>
  );
}
