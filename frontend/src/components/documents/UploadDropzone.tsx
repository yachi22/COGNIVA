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
      setClientError("Unsupported format. Cogniva accepts PDF (.pdf) and Word (.docx) files only.");
      return;
    }

    // Check empty file
    if (file.size === 0) {
      setClientError("Uploaded file is empty (0 bytes). Please choose a valid document.");
      return;
    }

    // Check max size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setClientError(`File size exceeds maximum limit of ${MAX_FILE_SIZE_MB}MB.`);
      return;
    }

    await onUpload(file);
    // Reset file input value so re-uploading the same filename works
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
        className={`relative border-2 border-dashed rounded-2xl p-6 sm:p-8 text-center transition-all cursor-pointer ${
          isDragOver
            ? "border-indigo-500 bg-indigo-50/60 scale-[1.005]"
            : "border-slate-200 hover:border-indigo-300 bg-white/80 hover:bg-white"
        } ${isUploading ? "opacity-75 cursor-not-allowed" : ""}`}
      >
        <div className="w-12 h-12 mx-auto rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-3 shadow-xs">
          {isUploading ? (
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
          ) : (
            <UploadCloud className="w-6 h-6" />
          )}
        </div>

        <h4 className="text-sm font-semibold text-slate-800 mb-1">
          {isUploading ? "Uploading document to Cogniva..." : "Drop PDF or DOCX here, or browse files"}
        </h4>
        <p className="text-xs text-slate-500 max-w-md mx-auto mb-4">
          Upload enterprise documentation, research reports, policies, or contracts up to 50MB.
        </p>

        {/* Progress Bar when uploading */}
        {isUploading && (
          <div className="max-w-xs mx-auto mb-3">
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-indigo-600 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress > 0 ? uploadProgress : 15}%` }}
              />
            </div>
            <p className="text-[11px] text-indigo-600 font-medium mt-1">
              {uploadProgress > 0 ? `Uploading: ${uploadProgress}%` : "Processing file..."}
            </p>
          </div>
        )}

        {/* File Format Tags */}
        <div className="flex items-center justify-center gap-4 text-[11px] text-slate-400">
          <span className="flex items-center gap-1">
            <FileText className="w-3 h-3 text-indigo-500" /> PDF (.pdf)
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <FileText className="w-3 h-3 text-blue-500" /> Word (.docx)
          </span>
          <span>•</span>
          <span>Max {MAX_FILE_SIZE_MB}MB</span>
        </div>
      </div>

      {/* Success Notification */}
      {uploadSuccess && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-medium">{uploadSuccess}</span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClearStatus();
            }}
            className="text-emerald-700 hover:text-emerald-900 p-1"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Error Notification */}
      {activeError && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-medium">{activeError}</span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setClientError(null);
              onClearStatus();
            }}
            className="text-rose-700 hover:text-rose-900 p-1"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default UploadDropzone;
