import clsx from "clsx";
import type { JobStatus } from "@/lib/api";

const config: Record<JobStatus, { label: string; classes: string }> = {
  queued:     { label: "Queued",     classes: "bg-yellow-100 text-yellow-800" },
  processing: { label: "Processing", classes: "bg-blue-100 text-blue-800 animate-pulse" },
  completed:  { label: "Completed",  classes: "bg-green-100 text-green-800" },
  failed:     { label: "Failed",     classes: "bg-red-100 text-red-800" },
  finalized:  { label: "Finalized",  classes: "bg-purple-100 text-purple-800" },
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  const { label, classes } = config[status] ?? { label: status, classes: "bg-gray-100 text-gray-800" };
  return <span className={clsx("badge", classes)}>{label}</span>;
}
