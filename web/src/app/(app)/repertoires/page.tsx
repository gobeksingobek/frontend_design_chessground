"use client";

import { DragEvent, useMemo, useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
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
    <PageContainer title="Repertoire" description="Import repertoire files, monitor job progress, and validate incoming opening lines.">
      <PageSection>
        <SectionHeader title="Repertoire import" description={acceptedLabel} />
        <div onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}><Card className={cn("border border-dashed text-center transition-[border-color,background-color]", isDragging ? "border-primary bg-primary/10" : "border-border/55 bg-elevated")} aria-busy={isUploading}>
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-primary/20 bg-primary/10 font-mono font-semibold text-primary">PGN</div>
          <div className="grid gap-1"><p className="font-medium text-foreground">Drop a repertoire export here</p><p className="text-sm text-muted-foreground">or choose a file from this device</p></div>
          <Input type="file" accept=".zip,.pgn" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
          <p className="font-mono text-sm text-muted-foreground">{selectedFile ? `Selected: ${selectedFile.name}` : "No file selected"}</p>
          <div className="flex flex-wrap justify-center gap-2"><Button type="button" variant="primary" onClick={onImport} disabled={isUploading || !selectedFile}>{isUploading ? "Importing…" : "Import repertoire"}</Button><Button type="button" onClick={onRefreshJob} disabled={!jobId}>Refresh job status</Button></div>
        </Card></div>
        {statusText ? <p className="rounded-control border border-success/25 bg-success/10 px-4 py-3 text-sm text-success">{statusText}</p> : null}
        {errorText ? <p className="rounded-control border border-danger/25 bg-danger/10 px-4 py-3 text-sm text-danger">{errorText}</p> : null}
        {jobId ? <p className="font-mono text-sm text-muted-foreground">Latest import job: {jobId}</p> : null}
      </PageSection>
    </PageContainer>
  );
}
