"use client";
import { useEffect, useState, useRef } from "react";
import ProgressBar from "./ProgressBar";
import type { ProgressEvent } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  documentId: string;
  initialProgress: number;
  initialStage: string | null;
  initialStatus: string;
  onComplete?: (event: ProgressEvent) => void;
}

export default function LiveProgress({
  documentId,
  initialProgress,
  initialStage,
  initialStatus,
  onComplete,
}: Props) {
  const [progress, setProgress] = useState(initialProgress);
  const [stage, setStage] = useState(initialStage);
  const [status, setStatus] = useState(initialStatus);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (initialStatus === "completed" || initialStatus === "finalized" || initialStatus === "failed") {
      return;
    }

    const es = new EventSource(`${API_URL}/api/progress/${documentId}/stream`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data: ProgressEvent = JSON.parse(e.data);
        setProgress(data.progress);
        setStage(data.event);
        setStatus(data.status);
        setEvents((prev) => [...prev.slice(-19), data]);

        if (data.event === "job_completed" || data.event === "job_failed") {
          es.close();
          onComplete?.(data);
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [documentId, initialStatus, onComplete]);

  return (
    <div className="space-y-3">
      <ProgressBar progress={progress} status={status} stage={stage} />
      {events.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-3 max-h-40 overflow-y-auto space-y-1">
          {events.map((ev, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="text-gray-400 shrink-0">
                {new Date(ev.timestamp).toLocaleTimeString()}
              </span>
              <span className="font-mono text-gray-600">{ev.event}</span>
              <span className="text-gray-500">{ev.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
