"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Search, RefreshCw, Upload, Filter, ArrowUpDown } from "lucide-react";
import toast from "react-hot-toast";
import {
  listDocuments,
  retryDocument,
  deleteDocument,
  formatFileSize,
  type Document,
  type DocumentListResponse,
} from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import ProgressBar from "@/components/ProgressBar";
import { formatDistanceToNow } from "date-fns";

const STATUS_OPTIONS = ["", "queued", "processing", "completed", "failed", "finalized"];
const SORT_OPTIONS = [
  { value: "created_at", label: "Date Created" },
  { value: "updated_at", label: "Last Updated" },
  { value: "original_filename", label: "Filename" },
  { value: "file_size", label: "File Size" },
  { value: "status", label: "Status" },
];

export default function DashboardPage() {
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  // Track if any docs are active — stored in ref so interval doesn't cause re-renders
  const hasActiveDocsRef = useRef(false);

  // silent = true means background refresh (no loading spinner, no table flicker)
  const fetchDocs = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const result = await listDocuments({
        page,
        page_size: 15,
        search: search || undefined,
        status: status || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setData(result);
      // Update ref — does NOT trigger re-render
      hasActiveDocsRef.current = result.items.some(
        (d) => d.status === "queued" || d.status === "processing"
      );
    } catch {
      toast.error("Failed to load documents");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [page, search, status, sortBy, sortOrder]);

  // Initial load + reload when filters/page change
  useEffect(() => {
    fetchDocs(false);
  }, [fetchDocs]);

  // Auto-refresh interval — completely separate, uses ref to check active docs
  useEffect(() => {
    const interval = setInterval(() => {
      if (hasActiveDocsRef.current) {
        fetchDocs(true); // silent refresh — no spinner, no blink
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchDocs]);

  const handleRetry = async (doc: Document) => {
    try {
      await retryDocument(doc.id);
      toast.success("Job re-queued");
      fetchDocs(true);
    } catch {
      toast.error("Retry failed");
    }
  };

  const handleDelete = async (doc: Document) => {
    if (!confirm(`Delete "${doc.original_filename}"?`)) return;
    try {
      await deleteDocument(doc.id);
      toast.success("Document deleted");
      fetchDocs(false);
    } catch {
      toast.error("Delete failed");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
          <p className="text-sm text-gray-500 mt-1">
            {data ? `${data.total} document${data.total !== 1 ? "s" : ""}` : "Loading…"}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => fetchDocs(false)} className="btn-secondary">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <Link href="/upload" className="btn-primary">
            <Upload className="w-4 h-4" />
            Upload
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            className="input pl-9"
            placeholder="Search by filename…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            className="input w-auto"
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s ? s.charAt(0).toUpperCase() + s.slice(1) : "All Statuses"}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <ArrowUpDown className="w-4 h-4 text-gray-400" />
          <select className="input w-auto" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <select
            className="input w-auto"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}
          >
            <option value="desc">Newest first</option>
            <option value="asc">Oldest first</option>
          </select>
        </div>
      </div>

      {/* Table — show stale data while silently refreshing, no flicker */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-400">Loading…</div>
        ) : !data?.items.length ? (
          <div className="p-12 text-center">
            <p className="text-gray-500 mb-4">No documents found</p>
            <Link href="/upload" className="btn-primary">
              Upload your first document
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Filename</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Size</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Progress</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Created</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.items.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      href={`/documents/${doc.id}`}
                      className="font-medium text-blue-600 hover:underline truncate max-w-xs block"
                    >
                      {doc.original_filename}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500 uppercase text-xs">{doc.file_type}</td>
                  <td className="px-4 py-3 text-gray-500">{formatFileSize(doc.file_size)}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="px-4 py-3 w-40">
                    <ProgressBar progress={doc.progress} status={doc.status} stage={doc.current_stage} />
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {formatDistanceToNow(new Date(doc.created_at), { addSuffix: true })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/documents/${doc.id}`}
                        className="btn-secondary text-xs py-1 px-2"
                      >
                        View
                      </Link>
                      {doc.status === "failed" && (
                        <button
                          onClick={() => handleRetry(doc)}
                          className="btn text-xs py-1 px-2 bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100"
                        >
                          Retry
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(doc)}
                        className="btn text-xs py-1 px-2 bg-red-50 text-red-700 border border-red-200 hover:bg-red-100"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">
            Page {data.page} of {data.total_pages}
          </span>
          <div className="flex gap-2">
            <button
              className="btn-secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <button
              className="btn-secondary"
              disabled={page >= data.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
