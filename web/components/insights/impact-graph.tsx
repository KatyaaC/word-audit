"use client";

import { useMemo, useState } from "react";
import { Background, Controls, MarkerType, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, ErrorNote } from "@/components/ui/primitives";
import type { ImpactEdge, ImpactNode } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

const COLUMN: Record<ImpactNode["kind"], number> = { fact: 0, content: 340, passport: 680 };

const STYLE: Record<ImpactNode["status"], React.CSSProperties> = {
  ok: { background: "#ffffff", border: "1px solid #a8a29e" },
  expired: { background: "#fee2e2", border: "2px solid #dc2626" },
  flagged: { background: "#ffedd5", border: "2px solid #ea580c" },
};

/** Everything downstream of a node (fact -> content -> passport). */
function downstream(start: string, edges: ImpactEdge[]): Set<string> {
  const seen = new Set<string>([start]);
  const queue = [start];
  while (queue.length) {
    const cur = queue.shift()!;
    for (const e of edges) if (e.source === cur && !seen.has(e.target)) (seen.add(e.target), queue.push(e.target));
  }
  return seen;
}

/**
 * Impact propagation graph. Selecting a fact highlights everything that depends on it;
 * "Expire this fact" asks the backend to propagate, then the graph reloads with flags.
 */
export function ImpactGraph({
  nodes,
  edges,
  onExpire,
}: {
  nodes: ImpactNode[];
  edges: ImpactEdge[];
  onExpire: (factId: string) => Promise<string>;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reach = useMemo(() => (selected ? downstream(selected, edges) : new Set<string>()), [selected, edges]);

  const flowNodes: Node[] = useMemo(() => {
    const rows: Record<string, number> = { fact: 0, content: 0, passport: 0 };
    return nodes.map((n) => {
      const y = rows[n.kind]++ * 90;
      const hl = reach.has(n.id);
      return {
        id: n.id,
        position: { x: COLUMN[n.kind], y },
        data: { label: n.label },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: {
          ...STYLE[n.status],
          width: 250,
          fontSize: 12,
          borderRadius: 8,
          boxShadow: hl ? "0 0 0 3px #1c1917" : undefined,
          opacity: selected && !hl ? 0.4 : 1,
        },
      };
    });
  }, [nodes, reach, selected]);

  const flowEdges: Edge[] = useMemo(
    () =>
      edges.map((e) => {
        const hl = reach.has(e.source) && reach.has(e.target);
        return {
          id: `${e.source}->${e.target}`,
          source: e.source,
          target: e.target,
          animated: hl,
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: hl ? "#dc2626" : "#a8a29e", strokeWidth: hl ? 2 : 1 },
        };
      }),
    [edges, reach],
  );

  const selectedNode = nodes.find((n) => n.id === selected);

  return (
    <Card>
      <CardHeader>
        <CardTitle>What depends on each fact</CardTitle>
        <CardDescription>Facts on the left, the content that uses them in the middle, Passports on the right. Click a fact to follow it.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="h-[380px] rounded-md border border-stone-200 bg-stone-50">
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            fitView
            nodesDraggable
            onNodeClick={(_, n) => {
              setSelected(n.id === selected ? null : n.id);
              setNote(null);
            }}
            onPaneClick={() => setSelected(null)}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={16} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {selectedNode ? (
            <>
              <span>
                <strong>{selectedNode.id}</strong> affects {reach.size - 1} item{reach.size === 2 ? "" : "s"}.
              </span>
              {selectedNode.kind === "fact" && selectedNode.status !== "expired" && (
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    setError(null);
                    try {
                      setNote(await onExpire(selectedNode.id));
                    } catch (e) {
                      setError(errorMessage(e));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  What if this fact expires?
                </Button>
              )}
            </>
          ) : (
            <span className="text-stone-500">Click any box to see what it's connected to.</span>
          )}
          <span className="ml-auto flex gap-3 text-xs text-stone-500">
            <span className="flex items-center gap-1"><i className="h-3 w-3 rounded-sm border-2 border-red-600 bg-red-100" />expired</span>
            <span className="flex items-center gap-1"><i className="h-3 w-3 rounded-sm border-2 border-orange-600 bg-orange-100" />needs another look</span>
          </span>
        </div>
        {note && <p className="rounded-md bg-orange-50 p-2 text-sm text-orange-900">{note}</p>}
        <ErrorNote message={error} />
      </CardContent>
    </Card>
  );
}
