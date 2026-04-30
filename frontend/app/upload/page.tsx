"use client";
import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Upload, X, FileText, AlertCircle, CheckCircle } from "lucide-react";
import toast from "react-hot-toast";
import { uploadDocuments, formatFileSize } from "@/lib/api";
import clsx from "clsx";

const ACCEPTED = ".pdf,.docx,.txt,.md,.csv,.json,.xml,.html";
const MAX_SIZE = 50 * 1024 * 1024;

interface FileEntry {
  file: File;
  id: string;
  error?: string;
}

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const arr = Array.from(incoming);
    const entries: FileEntry[] = arr.map((f) => ({
      file: f,
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      error: f.size > MAX_SIZE ? "File exceeds 50 MB limit" : undefined,
    }));
    setFiles((prev) => {
      const names = new Set(prev.map((e) => e.file.name));
      return [...prev, ...entries.filter((e) => !names.has(e.file.name))];
    });
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id));

  const handleUpload = async () => {
    const valid = files.filter((f) => !f.error);
    if (!valid.length) return;
    setUploading(true);
    try {
      const result = await uploadDocuments(valid.map((f) => f.file));
      if (result.uploaded.length) {
        toast.success(`${result.uploaded.length} document(s) uploaded and queued`);
      }
      if (result.failed.length) {
        result.failed.forEach((f) => toast.error(`${f.filename}: ${f.error}`));
      }
      router.push("/");
    } catch {
      toast.error("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const validCount = files.filter((f) => !f.error).length;

  return (
    <div className="max-w-2xl mx-auto px-4 py-12 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Documents</h1>
        <p className="text-sm text-gray-500 mt-1">
          Supported: PDF, DOCX, TXT, MD, CSV, JSON, XML, HTML — up to 50 MB each
        </p>
      </div>

      {/* Drop zone */}
      <div
        className={clsx(
          "border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors",
          dragOver ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"
        )}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
        <p className="text-gray-600 font-medium">Drop files here or click to browse</p>
        <p className="text-sm text-gray-400 mt-1">Multiple files supported</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="card divide-y divide-gray-100">
          {files.map((entry) => (
            <div key={entry.id} className="flex items-center gap-3 px-4 py-3">
              <FileText className={clsx("w-5 h-5 shrink-0", entry.error ? "text-red-400" : "text-blue-400")} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{entry.file.name}</p>
                <p className="text-xs text-gray-400">{formatFileSize(entry.file.size)}</p>
                {entry.error && (
                  <p className="text-xs text-red-500 flex items-center gap-1 mt-0.5">
                    <AlertCircle className="w-3 h-3" /> {entry.error}
                  </p>
                )}
              </div>
              {!entry.error && <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />}
              <button
                onClick={(e) => { e.stopPropagation(); removeFile(entry.id); }}
                className="text-gray-400 hover:text-red-500 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <button className="btn-secondary" onClick={() => setFiles([])}>
          Clear all
        </button>
        <button
          className="btn-primary"
          disabled={validCount === 0 || uploading}
          onClick={handleUpload}
        >
          {uploading ? (
            <>
              <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              Uploading…
            </>
          ) : (
            <>
              <Upload className="w-4 h-4" />
              Upload {validCount > 0 ? `${validCount} file${validCount > 1 ? "s" : ""}` : ""}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
