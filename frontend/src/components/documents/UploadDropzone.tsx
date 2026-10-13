import React, { useState, useRef, DragEvent, ChangeEvent } from "react";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
} from "lucide-react";

interface UploadDropzoneProps {
  onUpload: (file: File) => Promise<unknown>;
  isUploading: boolean;
  uploadProgress: number;
  uploadError: string | null;
  uploadSuccess: string | null;
  onClearStatus: () => void;
}

const MAX_FILE_SIZE_MB = 50;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

export const UploadDropzone: React.FC<UploadDropzoneProps> = ({
  onUpload,
  isUploading,
  uploadProgress,
  uploadError,
  uploadSuccess,
  onClearStatus,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndUpload = async (file: File) => {
    setClientError(null);
    onClearStatus();

    // Check extension
    const fileName = file.name.toLowerCase();
    const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => fileName.endsWith(ext));
    if (!hasValidExt) {
      setClientError("Unsupported format. Cogniva accepts PDF (.pdf) and Word (.docx) documents only.");
      return;
    }

    // Check empty file
    if (file.size === 0) {
      setClientError("Uploaded document is empty (0 bytes). Please choose a valid document.");
      return;
    }

    // Check max size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setClientError(`Document size exceeds the maximum limit of ${MAX_FILE_SIZE_MB}MB.`);
      return;
    }

    await onUpload(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isUploading) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (isUploading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      await validateAndUpload(droppedFile);
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      await validateAndUpload(selectedFile);
    }
  };

  const handleClickArea = () => {
    if (!isUploading && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const activeError = clientError || uploadError;

  return (
    <div className="space-y-3">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Main Drag-and-Drop Area */}
      <div
        onClick={handleClickArea}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-6 sm:p-8 text-center transition-colors cursor-pointer select-none ${
          isDragOver
            ? "border-accent bg-panel/70"
            : "border-border hover:border-secondary bg-surface"
        } ${isUploading ? "opacity-75 cursor-not-allowed" : ""}`}
      >
        <div className="w-10 h-10 mx-auto rounded-lg bg-panel border border-border flex items-center justify-center text-secondary mb-3">
          {isUploading ? (
            <Loader2 className="w-5 h-5 animate-spin text-accent" />
          ) : (
            <UploadCloud className="w-5 h-5 text-accent" />
          )}
        </div>

        <h4 className="text-xs sm:text-sm font-semibold text-primary mb-1">
          {isUploading ? "Uploading knowledge asset to Cogniva..." : "Drop PDF or DOCX file here, or browse files"}
        </h4>
        <p className="text-xs text-secondary max-w-md mx-auto mb-4">
          Upload enterprise documentation, research reports, policies, or contracts up to 50MB.
        </p>

        {/* Progress Bar when uploading */}
        {isUploading && (
          <div className="max-w-xs mx-auto mb-3">
            <div className="w-full bg-panel rounded-full h-1.5 overflow-hidden border border-border">
              <div
                className="bg-accent h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress > 0 ? uploadProgress : 15}%` }}
              />
            </div>
            <p className="text-[11px] text-accent font-medium mt-1">
              {uploadProgress > 0 ? `Uploading: ${uploadProgress}%` : "Transferring to storage..."}
            </p>
          </div>
        )}

        {/* File Format Tags */}
        <div className="flex items-center justify-center gap-3 text-[11px] text-secondary">
          <span className="flex items-center gap-1 font-mono">
            <FileText className="w-3 h-3 text-secondary" /> PDF (.pdf)
          </span>
          <span>•</span>
          <span className="flex items-center gap-1 font-mono">
            <FileText className="w-3 h-3 text-secondary" /> Word (.docx)
          </span>
          <span>•</span>
          <span>Max {MAX_FILE_SIZE_MB}MB</span>
        </div>
      </div>

      {/* Success Notification */}
      {uploadSuccess && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="font-medium">{uploadSuccess}</span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClearStatus();
            }}
            className="text-emerald-700 hover:text-emerald-900 dark:text-emerald-300 p-1 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Error Notification */}
      {activeError && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span className="font-medium">{activeError}</span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setClientError(null);
              onClearStatus();
            }}
            className="text-rose-700 hover:text-rose-900 dark:text-rose-300 p-1 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default UploadDropzone;
