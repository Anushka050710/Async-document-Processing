import clsx from "clsx";

interface Props {
  progress: number;
  status: string;
  stage?: string | null;
}

export default function ProgressBar({ progress, status, stage }: Props) {
  const color =
    status === "failed"
      ? "bg-red-500"
      : status === "completed" || status === "finalized"
      ? "bg-green-500"
      : "bg-blue-500";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{stage ? stage.replace(/_/g, " ") : "Waiting…"}</span>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={clsx("h-2 rounded-full transition-all duration-500", color)}
          style={{ width: `${Math.min(100, progress)}%` }}
        />
      </div>
    </div>
  );
}
