"use client";

import { useQuery } from "@tanstack/react-query";

import { Card } from "@/components/ui/card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/table";
import { listSidelines } from "@/lib/api-client";

export function SidelineTable() {
  const { data, isLoading, error } = useQuery({ queryKey: ["sidelines", 20], queryFn: () => listSidelines(20) });
  if (isLoading) return <p className="text-sm text-text-muted">Loading sideline jobs...</p>;
  if (error) return <p className="text-sm text-danger">Failed to load sidelines: {(error as Error).message}</p>;

  return (
    <Card>
      <Table>
        <TableHead>
          <tr><Th>ID</Th><Th>Game</Th><Th>Ply</Th><Th>Status</Th><Th>Attempts</Th></tr>
        </TableHead>
        <TableBody>
          {data?.map((row) => (
            <tr key={row.id} className="hover:bg-panel-muted/70">
              <Td>{row.id.slice(0, 8)}…</Td><Td>{row.game_id}</Td><Td>{row.move_ply}</Td><Td>{row.status}</Td><Td>{row.attempts}</Td>
            </tr>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
