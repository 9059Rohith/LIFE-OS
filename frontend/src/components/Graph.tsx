import { useLayoutEffect, useRef, useState } from "react";
import {
  Plane,
  CalendarDays,
  ArrowUpRight,
  GitBranch,
  Network,
  List,
  ScanLine,
} from "lucide-react";
import type { Action, LifeEvent } from "../types";
import { AppIcon, appNames, Status } from "./Common";
export function Graph({
  event,
  onSelect,
}: {
  event: LifeEvent | null;
  onSelect: (action: Action) => void;
}) {
  const [view, setView] = useState<"graph" | "list">("graph");
  const canvas = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState<
    { key: string; path: string; dependency: boolean }[]
  >([]);
  const actions = event?.actions || [];
  useLayoutEffect(() => {
    const element = canvas.current;
    if (!element || !event || view !== "graph") return;
    function measure() {
      if (!element || !event) return;
      const bounds = element.getBoundingClientRect();
      const nodes = new Map(
        Array.from(element.querySelectorAll<HTMLElement>("[data-node]")).map(
          (node) => [node.dataset.node!, node.getBoundingClientRect()],
        ),
      );
      const result: { key: string; path: string; dependency: boolean }[] = [];
      for (const action of event.actions) {
        const target = nodes.get(action.id);
        if (!target) continue;
        const parents = action.dependencies.length
          ? action.dependencies
          : ["root"];
        for (const parent of parents) {
          const source = nodes.get(parent);
          if (!source) continue;
          const upward = source.top > target.top;
          const x1 = source.left + source.width / 2 - bounds.left;
          const y1 = (upward ? source.top : source.bottom) - bounds.top;
          const x2 = target.left + target.width / 2 - bounds.left;
          const y2 = (upward ? target.bottom : target.top) - bounds.top;
          const bend = upward ? -18 : 18;
          const path =
            source.top === target.top
              ? `M ${source.right - bounds.left} ${source.top + source.height / 2 - bounds.top} C ${source.right - bounds.left + 15} ${source.bottom - bounds.top + 25}, ${target.left - bounds.left - 15} ${target.bottom - bounds.top + 25}, ${target.left - bounds.left} ${target.top + target.height / 2 - bounds.top}`
              : `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}`;
          result.push({
            key: parent + "-" + action.id,
            path,
            dependency: parent !== "root",
          });
        }
      }
      setEdges(result);
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [event, view]);
  const primary = actions.filter(
    (a) => a.application !== "drive",
  );
  const support = actions.filter((a) =>
    a.application === "drive",
  );
  return (
    <section className="panel graph-panel" aria-label="Consequence graph">
      <div className="panel-heading">
        <div>
          <h2>Consequence graph</h2>
          <p>One change. The whole picture.</p>
        </div>
        <div className="segmented">
          <button
            aria-label="Graph view"
            aria-pressed={view === "graph"}
            onClick={() => setView("graph")}
          >
            <Network size={14} />
            Graph
          </button>
          <button
            aria-label="List view"
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <List size={14} />
            List
          </button>
        </div>
      </div>
      {!event ? (
        <div className="graph-empty">
          <div className="empty-orbit">
            <GitBranch size={35} />
          </div>
          <h3>See the signal flow.</h3>
          <p>
            Tell LIFEOS what changed. Discover the connections before deciding
            what happens next.
          </p>
          <span>
            <ScanLine size={14} /> Every action starts with your approval
          </span>
        </div>
      ) : view === "list" ? (
        <div className="graph-list">
          {actions.map((a) => (
            <button key={a.id} onClick={() => onSelect(a)}>
              <AppIcon name={a.application} />
              <span>
                <strong>{a.title}</strong>
                <small>{a.reason}</small>
              </span>
              <Status value={a.status} />
              <ArrowUpRight size={15} />
            </button>
          ))}
        </div>
      ) : (
        <div className="graph-canvas" ref={canvas}>
          <svg className="graph-edges" aria-label="Action dependencies">
            <defs>
              <marker
                id="dependency-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="4"
                markerHeight="4"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#6e9776" />
              </marker>
            </defs>
            {edges.map((edge) => (
              <g key={edge.key} className={`workflow-edge-group ${edge.dependency ? "dependency" : "signal"}`}>
                <path
                  className="workflow-edge"
                  d={edge.path}
                  fill="none"
                  stroke={edge.dependency ? "#6e9776" : "#aebda0"}
                  strokeWidth="1"
                  strokeDasharray={edge.dependency ? undefined : "3 3"}
                  markerEnd="url(#dependency-arrow)"
                />
                <path
                  className="workflow-edge-trace"
                  d={edge.path}
                  fill="none"
                  stroke={edge.dependency ? "#75f2bd" : "#7fcbff"}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  pathLength="1"
                />
              </g>
            ))}
          </svg>
          <div className="root-node" data-node="root">
            <div className="root-icon">
              {event.event_type.includes("flight") ? (
                <Plane size={24} />
              ) : (
                <CalendarDays size={24} />
              )}
            </div>
            <div>
              <small>THE CHANGE</small>
              <strong>{event.title}</strong>
              <span>
                {event.simulation
                  ? "What-if analysis"
                  : event.entities.new_time
                    ? `${event.entities.old_time || "New time"} → ${event.entities.new_time}`
                    : "Source: " + event.source}
              </span>
            </div>
            <i />
          </div>
          <div className="branch-stem" />
          <div
            className="graph-branches"
            style={
              { "--nodes": Math.max(primary.length, 1) } as React.CSSProperties
            }
          >
            {primary.map((a) => (
              <button
                className={`graph-node ${["executing", "verifying", "planning", "running"].includes(a.status) ? "is-executing" : ""} ${["verified", "completed", "approved", "resolved"].includes(a.status) ? "is-complete" : ""}`}
                data-node={a.id}
                key={a.id}
                onClick={() => onSelect(a)}
              >
                <i />
                <span className={`app-mark ${a.application}`}>
                  <AppIcon name={a.application} />
                </span>
                <strong>{appNames[a.application]}</strong>
                <span className="node-title">{a.title}</span>
                <Status value={a.status} />
              </button>
            ))}
          </div>
          {support.length > 0 && (
            <div className="support-nodes">
              {support.map((a) => (
                <button
                  className={`graph-node support-node ${["executing", "verifying", "planning", "running"].includes(a.status) ? "is-executing" : ""} ${["verified", "completed", "approved", "resolved"].includes(a.status) ? "is-complete" : ""}`}
                  data-node={a.id}
                  key={a.id}
                  onClick={() => onSelect(a)}
                >
                  <i />
                  <div className={`app-mark ${a.application}`}>
                    <AppIcon name={a.application} />
                  </div>
                  <strong>{appNames[a.application]}</strong>
                  <span className="node-title">{a.title}</span>
                  <Status value={a.status} />
                </button>
              ))}
            </div>
          )}
          <div className="graph-key">
            <span>
              <i /> Arrow = prerequisite
            </span>
            <span>{actions.length} proposed actions</span>
          </div>
        </div>
      )}
    </section>
  );
}
