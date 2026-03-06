"use client";

import { DragEvent, useMemo, useState } from "react";

import { getRepertoireImportJob, importRepertoire } from "@/lib/api-client";

export default function RepertoiresPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [jobId, setJobId] = useState<string>("");
  const [statusText, setStatusText] = useState<string>("");
  const [errorText, setErrorText] = useState<string>("");

  const acceptedLabel = useMemo(() => "Accepted formats: .zip archive of PGN files or a single .pgn file", []);

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(true);
  }

  function onDragLeave() {
    setIsDragging(false);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0] ?? null;
    setSelectedFile(file);
    setErrorText("");
  }

  async function onImport() {
    if (!selectedFile) {
      setErrorText("Choose a .zip or .pgn file before importing.");
      return;
    }

    setIsUploading(true);
    setStatusText("Uploading...");
    setErrorText("");
    try {
      const result = await importRepertoire(selectedFile);
      setJobId(result.job_id);
      setStatusText(result.detail);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "Import failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function onRefreshJob() {
    if (!jobId) {
      return;
    }
    try {
      const result = await getRepertoireImportJob(jobId);
      const inserted = Number(result.progress.inserted_lines ?? 0);
      const duplicates = Number(result.progress.duplicate_lines ?? 0);
      const total = Number(result.progress.total ?? 0);
      setStatusText(`Job ${result.id}: imported ${inserted}/${total}, duplicates ${duplicates}.`);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "Could not refresh job status.");
    }
  }

  return (
    <div className="stack">
      <h2>Repertoire import</h2>
      <p>{acceptedLabel}</p>
      <div
        className="card"
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        style={{ border: isDragging ? "2px dashed #4da3ff" : "2px dashed #666" }}
      >
        <p>Drag and drop a repertoire export here, or pick a file below.</p>
        <input
          type="file"
          accept=".zip,.pgn"
          onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
        />
        <p>{selectedFile ? `Selected: ${selectedFile.name}` : "No file selected"}</p>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" onClick={onImport} disabled={isUploading || !selectedFile}>
            {isUploading ? "Importing..." : "Import repertoire"}
          </button>
          <button type="button" onClick={onRefreshJob} disabled={!jobId}>
            Refresh job status
          </button>
        </div>
      </div>
      {statusText ? <p>{statusText}</p> : null}
      {errorText ? <p style={{ color: "#ff8080" }}>{errorText}</p> : null}
      {jobId ? <p>Latest import job ID: {jobId}</p> : null}
    </div>
  );
}
