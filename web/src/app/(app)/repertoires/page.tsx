"use client";

import { DragEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SectionHeader } from "@/components/ui/section-header";
import { cn } from "@/lib/cn";
import { getRepertoireImportJob, importRepertoire } from "@/lib/api-client";

export default function RepertoiresPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [jobId, setJobId] = useState<string>("");
  const [statusText, setStatusText] = useState<string>("");
  const [errorText, setErrorText] = useState<string>("");
  const acceptedLabel = useMemo(() => "Accepted formats: .zip archive of PGN files or a single .pgn file", []);
  function onDragOver(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setIsDragging(true); }
  function onDragLeave() { setIsDragging(false); }
  function onDrop(event: DragEvent<HTMLDivElement>) { event.preventDefault(); setIsDragging(false); const file = event.dataTransfer.files?.[0] ?? null; setSelectedFile(file); setErrorText(""); }
  async function onImport() { if (!selectedFile) { setErrorText("Choose a .zip or .pgn file before importing."); return; } setIsUploading(true); setStatusText("Uploading..."); setErrorText(""); try { const result = await importRepertoire(selectedFile); setJobId(result.job_id); setStatusText(result.detail); } catch (error) { setErrorText(error instanceof Error ? error.message : "Import failed."); } finally { setIsUploading(false); } }
  async function onRefreshJob() { if (!jobId) return; try { const result = await getRepertoireImportJob(jobId); const inserted = Number(result.progress.inserted_lines ?? 0); const duplicates = Number(result.progress.duplicate_lines ?? 0); const total = Number(result.progress.total ?? 0); setStatusText(`Job ${result.id}: imported ${inserted}/${total}, duplicates ${duplicates}.`); } catch (error) { setErrorText(error instanceof Error ? error.message : "Could not refresh job status."); } }
  return (
    <div className="grid gap-4">
      <SectionHeader title="Repertoire import" description={acceptedLabel} />
      <div onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}><Card className={cn("border-2 border-dashed", isDragging ? "border-accent" : "border-border")}>
        <p>Drag and drop a repertoire export here, or pick a file below.</p>
        <Input type="file" accept=".zip,.pgn" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
        <p className="text-sm text-text-subtle">{selectedFile ? `Selected: ${selectedFile.name}` : "No file selected"}</p>
        <div className="flex flex-wrap gap-2"><Button type="button" variant="primary" onClick={onImport} disabled={isUploading || !selectedFile}>{isUploading ? "Importing..." : "Import repertoire"}</Button><Button type="button" onClick={onRefreshJob} disabled={!jobId}>Refresh job status</Button></div>
      </Card></div>
      {statusText ? <p className="text-sm text-text-subtle">{statusText}</p> : null}
      {errorText ? <p className="text-sm text-danger">{errorText}</p> : null}
      {jobId ? <p className="text-sm text-text-muted">Latest import job ID: {jobId}</p> : null}
    </div>
  );
}
