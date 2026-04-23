"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { FormField } from "@/components/ui/form-field";
import { DenseControlRow, DetailPane, EmptyState, FilterPanel } from "@/components/ui/page-patterns";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { cn } from "@/lib/cn";
import type { StatsRow } from "@/lib/types";
import { normalizeStatsRows, resolveColumns, resolveSelectedRowIndex, summarizePivot, type StatsPayload } from "./stats-table-helpers";

type PivotOption = { value: string; label: string };

export function StatsTable({
  title,
  description,
  queryKey,
  queryFn,
  drilldownLabel = "Selected row",
  pivotOptions,
  pivotValue,
  onPivotChange,
  columnModelsByPivot,
  rowIdField,
  detailQueryKey,
  historyQueryKey,
  fetchDetail,
  fetchHistory,
}: {
  title: string;
  description: string;
  queryKey: string[];
  queryFn: () => Promise<StatsPayload>;
  drilldownLabel?: string;
  pivotOptions?: PivotOption[];
  pivotValue?: string;
  onPivotChange?: (pivot: string) => void;
  columnModelsByPivot?: Record<string, string[]>;
  rowIdField?: string;
  detailQueryKey?: string;
  historyQueryKey?: string;
  fetchDetail?: (rowId: string) => Promise<StatsRow>;
  fetchHistory?: (rowId: string) => Promise<{ line_id: string; buckets: StatsRow[]; totals: Record<string, number> }>;
}) {
  const { data, isLoading, error } = useQuery({ queryKey, queryFn });
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [pivotColumn, setPivotColumn] = useState<string>("");
  const rows = useMemo<StatsRow[]>(() => normalizeStatsRows(data), [data]);
  const columns = useMemo(
    () => resolveColumns(rows, pivotValue && columnModelsByPivot ? columnModelsByPivot[pivotValue] : undefined),
    [rows, pivotValue, columnModelsByPivot],
  );
  const selected = useMemo(() => {
    if (rows.length === 0) return null;
    const rowIndex = resolveSelectedRowIndex(selectedIndex, rows.length);
    return rows[rowIndex] ?? null;
  }, [rows, selectedIndex]);
  const selectedRowId = useMemo(() => {
    if (!selected || !rowIdField) return null;
    const candidate = selected[rowIdField];
    if (candidate == null) return null;
    return String(candidate);
  }, [selected, rowIdField]);
  const pivot = useMemo(() => (!pivotColumn || !columns.includes(pivotColumn) ? [] : summarizePivot(rows, pivotColumn)), [rows, pivotColumn, columns]);
  const canShowHistory = Boolean(fetchHistory && selectedRowId);

  useEffect(() => {
    setSelectedIndex((current) => resolveSelectedRowIndex(current, rows.length));
  }, [rows.length]);

  const detailQuery = useQuery<StatsRow>({
    queryKey: [detailQueryKey ?? "stats-row-detail", selectedRowId ?? "none"],
    queryFn: () => fetchDetail?.(selectedRowId ?? "") ?? Promise.resolve({} as StatsRow),
    enabled: Boolean(fetchDetail && selectedRowId),
  });

  const historyQuery = useQuery({
    queryKey: [historyQueryKey ?? "stats-row-history", selectedRowId ?? "none"],
    queryFn: () => fetchHistory?.(selectedRowId ?? "") ?? Promise.resolve({ line_id: selectedRowId ?? "", buckets: [], totals: {} }),
    enabled: canShowHistory,
  });

  return (
    <div className="grid gap-section-gap">
      {isLoading ? <StatsTableLoading /> : null}
      {error ? <p className="text-sm text-danger">{String(error)}</p> : null}
      {!isLoading && !error && rows.length === 0 ? <EmptyState title={`No ${title.toLowerCase()} data yet`} description={description} /> : null}
      {!isLoading && !error && rows.length > 0 ? (
        <>
          <FilterPanel title={`${title} filters`} description="Adjust the pivot column to compare related clusters without losing access to the active row detail.">
            <DenseControlRow>
              {pivotOptions && pivotValue && onPivotChange ? (
                <FormField label="Pivot" helpText="Switch report pivots for side-by-side comparison." className="min-w-[220px]">
                  <Select aria-label="Pivot" value={pivotValue} onChange={(e) => onPivotChange(e.target.value)}>
                    {pivotOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </Select>
                </FormField>
              ) : null}
              <FormField label="Pivot column" helpText="Summarize the dataset by any visible table column." className="min-w-[220px]">
                <Select aria-label="Pivot column" value={pivotColumn} onChange={(e) => setPivotColumn(e.target.value)}>
                  <option value="">None</option>
                  {columns.map((column) => <option key={column} value={column}>{column}</option>)}
                </Select>
              </FormField>
            </DenseControlRow>
          </FilterPanel>
          <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,1.65fr)_minmax(20rem,1fr)] xl:items-start">
            <TableContainer className="xl:h-full">
              <Table>
                <TableHead><tr>{columns.map((column) => <Th key={column}>{column}</Th>)}</tr></TableHead>
                <TableBody>
                  {rows.map((row, index) => (
                    <TableRow
                      key={index}
                      className={cn("cursor-pointer hover:bg-hover", selectedIndex === index && "bg-selection text-selection-foreground")}
                      onClick={() => {
                        setSelectedIndex(index);
                      }}
                    >
                      {columns.map((column) => <Td key={column} className={selectedIndex === index ? "text-selection-foreground" : undefined}>{String(row[column] ?? "")}</Td>)}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <div className="grid gap-grid-gap">
              <DetailPane title={drilldownLabel} description="Inspect the selected row without losing the table context.">
                {!selected ? <p className="text-sm text-muted-foreground">No row selected.</p> : null}
                {selected ? (
                  <Tabs
                    key={selectedRowId ?? "detail-pane"}
                    defaultValue="detail"
                    items={[
                      {
                        id: "detail",
                        label: "Detail",
                        content: (
                          <div className="grid gap-control-gap">
                            {detailQuery.isLoading ? <p className="text-sm text-muted-foreground">Loading details…</p> : null}
                            {detailQuery.error ? <p className="text-sm text-danger">Failed to load detail.</p> : null}
                            {detailQuery.data ? (
                              <ul className="grid gap-control-gap text-sm text-foreground">{Object.keys(detailQuery.data).map((column) => <li key={column}><strong>{column}:</strong> {String(detailQuery.data?.[column] ?? "")}</li>)}</ul>
                            ) : (
                              <ul className="grid gap-control-gap text-sm text-foreground">{columns.map((column) => <li key={column}><strong>{column}:</strong> {String(selected[column] ?? "")}</li>)}</ul>
                            )}
                          </div>
                        ),
                      },
                      ...(canShowHistory
                        ? [{
                            id: "history",
                            label: "History",
                            content: (
                              <div className="grid gap-control-gap text-sm">
                                {historyQuery.isLoading ? <p className="text-muted-foreground">Loading history…</p> : null}
                                {historyQuery.error ? <p className="text-danger">Failed to load history.</p> : null}
                                {!historyQuery.isLoading && !historyQuery.error ? (
                                  <>
                                    <p className="text-muted-foreground">Months: {String(historyQuery.data?.totals?.months ?? 0)} · Total games: {String(historyQuery.data?.totals?.total_games ?? 0)}</p>
                                    <ul className="grid gap-2">
                                      {(historyQuery.data?.buckets ?? []).map((bucket, index) => (
                                        <li key={`${String(bucket.bucket ?? "bucket")}-${index}`} className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-card px-3 py-2">
                                          <span>{String(bucket.bucket ?? "Unknown")}</span>
                                          <span className="font-medium">{String(bucket.total_games ?? 0)}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  </>
                                ) : null}
                              </div>
                            ),
                          }]
                        : []),
                    ]}
                    className="gap-3"
                  />
                ) : null}
              </DetailPane>
              {pivotColumn ? <DetailPane title={`Pivot summary by ${pivotColumn}`} description="Most frequent values in the current result set."><ul className="grid gap-control-gap text-sm text-muted-foreground">{pivot.slice(0, 10).map((entry) => <li key={entry.key} className="flex items-center justify-between gap-4 rounded-lg border border-border/60 bg-card px-3 py-2"><span className="truncate">{entry.key}</span><span className="font-medium text-foreground">{entry.count}</span></li>)}</ul></DetailPane> : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function StatsTableLoading() {
  return <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,1.65fr)_minmax(20rem,1fr)]"><Skeleton className="min-h-[24rem] w-full rounded-xl" /><Skeleton className="min-h-[24rem] w-full rounded-xl" /></div>;
}
