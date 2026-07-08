import { Skeleton } from "@/components/ui/skeleton";

function CardSkeleton() {
  return <Skeleton variant="card" />;
}

function ChartSkeleton({ className }: { className?: string }) {
  return <Skeleton variant="chart" className={className} />;
}

function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} variant="row" />
      ))}
    </div>
  );
}

function StatsGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} variant="card" />
      ))}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4 p-6">
      <Skeleton variant="text" className="h-8 w-48" />
      <StatsGridSkeleton />
      <Skeleton variant="chart" className="h-96" />
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} variant="row" />
        ))}
      </div>
    </div>
  );
}

export { DashboardSkeleton, StatsGridSkeleton, TableSkeleton, ChartSkeleton, CardSkeleton };
