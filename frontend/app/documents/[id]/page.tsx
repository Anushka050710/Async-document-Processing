"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, Download, CheckCircle, RefreshCw,
  Edit3, Save, X, FileText, Clock, AlertCircle
} from "lucide-react";
import toast from "react-hot-toast";
import {
  getDocument,
  updateReview,
  finalizeDocument,
  retryDocument,
  getExportUrl,
  formatFileSize,
  type Document,
  type ProgressEvent,
} from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import LiveProgress from "@/components/LiveProgress";
import { formatDistanceToNow, format } from "date-fns";

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [doc, setDoc] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [finalizing, setFinalizing] = useState(false);

  const fetchDoc = useCallback(async () => {
    try {
      const d = await getDocument(id);
      setDoc(d);
      if (!editing) {
        setEditValue(JSON.stringify(d.reviewed_data ?? d.extracted_data ?? {}, null, 2));
      }
    } catch {
      toast.error("Document not found");
      router.push("/");
    } finally {
      setLoading(false);
    }
  }, [id, editing, router]);

  useEffect(() => { fetchDoc(); }, [fetchDoc]);

  const handleProgressComplete = (event: ProgressEvent) => {
    if (event.event === "job_completed") {
      fetchDoc();
      toast.success("Processing complete!");
    } else if (event.event === "job_failed") {
      fetchDoc();
      toast.error("Processing failed");
    }
  };

  const handleSaveReview = async () => {
    setSaving(true);
    try {
      const parsed = JSON.parse(editValue);
      const updated = await updateReview(id, parsed);
      setDoc(updated);
      setEditing(false);
      toast.success("Review saved");
    } catch (e) {
      if (e instanceof SyntaxError) {
        toast.error("Invalid JSON — please fix before saving");
      } else {
        toast.error("Save failed");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleFinalize = async () => {
    if (!confirm("Finalize this document? This locks the reviewed data.")) return;
    setFinalizing(true);
    try {
      let parsed: unknown = undefined;
      if (editing) {
        try { parsed = JSON.parse(editValue); } catch { /* use existing */ }
      }
      const updated = await finalizeDocument(id, parsed);
      setDoc(updated);
      setEditing(false);
      toast.success("Document finalized!");
    } catch {
      toast.error("Finalization failed");
    } finally {
      setFinalizing(false);
    }
  };

  const handleRetry = async () => {
    try {
      const updated = await retryDocument(id);
      setDoc(updated);
      toast.success("Job re-queued");
    } catch {
      toast.error("Retry failed");
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center text-gray-400">
        Loading document…
      </div>
    );
  }

  if (!doc) return null;

  const canEdit = doc.status === "completed" || doc.status === "finalized";
  const canFinalize = doc.status === "completed";
  const isFinalized = doc.is_finalized;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Back */}
      <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </Link>

      {/* Header */}
      <div className="card p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <FileText className="w-8 h-8 text-blue-500 shrink-0 mt-0.5" />
            <div>
              <h1 className="text-xl font-bold text-gray-900 break-all">{doc.original_filename}</h1>
              <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-gray-500">
                <span className="uppercase font-medium">{doc.file_type}</span>
                <span>·</span>
                <span>{formatFileSize(doc.file_size)}</span>
                <span>·</span>
                <span>Uploaded {formatDistanceToNow(new Date(doc.created_at), { addSuffix: true })}</span>
                {doc.completed_at && (
                  <>
                    <span>·</span>
                    <span>Completed {format(new Date(doc.completed_at), "MMM d, HH:mm")}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <StatusBadge status={doc.status} />
        </div>

        {/* Error */}
        {doc.error_message && (
          <div className="mt-4 flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Processing Error</p>
              <p className="mt-0.5 text-red-600">{doc.error_message}</p>
              {doc.retry_count > 0 && <p className="text-xs mt-1">Retried {doc.retry_count} time(s)</p>}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-2 mt-4">
          {doc.status === "failed" && (
            <button onClick={handleRetry} className="btn-secondary">
              <RefreshCw className="w-4 h-4" /> Retry
            </button>
          )}
          {canFinalize && !isFinalized && (
            <button onClick={handleFinalize} disabled={finalizing} className="btn-success">
              <CheckCircle className="w-4 h-4" />
              {finalizing ? "Finalizing…" : "Finalize"}
            </button>
          )}
          {isFinalized && (
            <>
              <a href={getExportUrl(doc.id, "json")} download className="btn-secondary">
                <Download className="w-4 h-4" /> Export JSON
              </a>
              <a href={getExportUrl(doc.id, "csv")} download className="btn-secondary">
                <Download className="w-4 h-4" /> Export CSV
              </a>
            </>
          )}
        </div>
      </div>

      {/* Progress */}
      {(doc.status === "queued" || doc.status === "processing") && (
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Processing Progress</h2>
          <LiveProgress
            documentId={doc.id}
            initialProgress={doc.progress}
            initialStage={doc.current_stage}
            initialStatus={doc.status}
            onComplete={handleProgressComplete}
          />
        </div>
      )}

      {/* Processing Logs */}
      {doc.processing_logs && doc.processing_logs.length > 0 && (
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Processing Timeline
          </h2>
          <div className="space-y-2">
            {doc.processing_logs.map((log) => (
              <div key={log.id} className="flex items-start gap-3 text-sm">
                <span className="text-gray-400 text-xs shrink-0 mt-0.5 w-20">
                  {format(new Date(log.created_at), "HH:mm:ss")}
                </span>
                <div className="flex-1">
                  <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">
                    {log.event}
                  </span>
                  {log.message && <span className="ml-2 text-gray-600">{log.message}</span>}
                </div>
                <span className="text-xs text-gray-400 shrink-0">{Math.round(log.progress)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Extracted / Reviewed Data */}
      {canEdit && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">
              {isFinalized ? "Finalized Data" : "Extracted Data"}
            </h2>
            {!isFinalized && (
              <div className="flex gap-2">
                {editing ? (
                  <>
                    <button onClick={() => { setEditing(false); setEditValue(JSON.stringify(doc.reviewed_data ?? doc.extracted_data ?? {}, null, 2)); }} className="btn-secondary">
                      <X className="w-4 h-4" /> Cancel
                    </button>
                    <button onClick={handleSaveReview} disabled={saving} className="btn-primary">
                      <Save className="w-4 h-4" />
                      {saving ? "Saving…" : "Save"}
                    </button>
                  </>
                ) : (
                  <button onClick={() => setEditing(true)} className="btn-secondary">
                    <Edit3 className="w-4 h-4" /> Edit
                  </button>
                )}
              </div>
            )}
          </div>

          {editing ? (
            <textarea
              className="input font-mono text-xs h-96 resize-y"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              spellCheck={false}
            />
          ) : (
            <ExtractedDataView data={doc.reviewed_data ?? doc.extracted_data} />
          )}
        </div>
      )}
    </div>
  );
}

function ExtractedDataView({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return <p className="text-gray-400 text-sm">No data extracted yet.</p>;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            {key.replace(/_/g, " ")}
          </p>
          <p className="text-sm text-gray-900 break-words">
            {Array.isArray(value)
              ? value.join(", ") || "—"
              : value === null || value === undefined
              ? "—"
              : String(value)}
          </p>
        </div>
      ))}
    </div>
  );
}
