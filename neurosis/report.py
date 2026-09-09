"""Dependency-free, self-contained HTML views of concluded Lab artifacts."""

from __future__ import annotations

from html import escape
from typing import Any

from neurosis.graph import InteractionGraph


_STYLE = """
body{font:15px/1.5 system-ui,sans-serif;max-width:1120px;margin:2rem auto;padding:0 1rem;color:#18212b}
h1,h2{line-height:1.2}.muted{color:#5f6b76}.cards{display:flex;gap:1rem;flex-wrap:wrap}
.card{border:1px solid #cad2da;border-radius:.5rem;padding:.8rem 1rem;min-width:9rem}
.value{font-size:1.5rem;font-weight:700}table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #cad2da;padding:.45rem;text-align:left;vertical-align:top}th{background:#f3f6f8}
svg{border:1px solid #cad2da;background:#fbfcfd;width:100%;height:auto}.node{fill:white;stroke:#41576b}
.edge{stroke:#8796a5;stroke-width:1.2}.edge-label{font-size:9px;fill:#536271}.node-label{font-size:10px}
code{overflow-wrap:anywhere}.warning{background:#fff5d6;border-left:4px solid #e1a800;padding:.8rem}
"""


def _page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><style>{_STYLE}</style><body>{body}</body></html>\n')


def _format(value: Any) -> str:
    if value is None:
        return 'undefined'
    if isinstance(value, float):
        return f'{value:.4f}'
    return str(value)


def _graph_svg(graph: InteractionGraph) -> str:
    types = ('origin', 'message', 'agent', 'tool', 'claim')
    columns = {name: 75 + index * 205 for index, name in enumerate(types)}
    groups = {name: [node for node in graph.nodes if node.type == name] for name in types}
    positions: dict[str, tuple[int, int]] = {}
    maximum = max((len(items) for items in groups.values()), default=1)
    height = max(360, 75 + maximum * 62)
    for node_type, items in groups.items():
        for index, node in enumerate(items):
            positions[node.id] = (columns[node_type], 55 + index * 62)
    lines = [f'<svg viewBox="0 0 980 {height}" role="img" '
             'aria-label="Recorded provenance and interaction graph">',
             '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" '
             'orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#8796a5"/></marker></defs>']
    for edge in graph.edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        lines.append(f'<line class="edge" x1="{x1 + 70}" y1="{y1}" x2="{x2 - 70}" '
                     f'y2="{y2}" marker-end="url(#arrow)"/>')
        lines.append(f'<text class="edge-label" x="{(x1 + x2) / 2}" '
                     f'y="{(y1 + y2) / 2 - 3}">{escape(edge.relation)}</text>')
    for node_type in types:
        lines.append(f'<text x="{columns[node_type]}" y="20" text-anchor="middle" '
                     f'font-weight="700">{escape(node_type)}</text>')
        for node in groups[node_type]:
            x, y = positions[node.id]
            label = node.entity_id if len(node.entity_id) <= 25 else node.entity_id[:22] + '…'
            lines.append(f'<rect class="node" x="{x - 70}" y="{y - 18}" width="140" '
                         'height="36" rx="6"/>')
            lines.append(f'<text class="node-label" x="{x}" y="{y + 3}" '
                         f'text-anchor="middle">{escape(label)}</text>')
    lines.append('</svg>')
    return ''.join(lines)


def render_trial_report(evaluation: dict[str, Any], graph: InteractionGraph) -> str:
    condition = evaluation['condition']
    cards = ''.join(
        f'<div class="card"><div class="muted">{escape(label)}</div>'
        f'<div class="value">{escape(_format(evaluation.get(key)))}</div></div>'
        for label, key in (
            ('Outcome', 'run_outcome'), ('Final correct', 'final_answer_correct'),
            ('False belief', 'false_belief_adoption'),
            ('Verification calls', 'verification_attempts'),
            ('Known origins', 'known_origin_count'), ('CIR', 'cir'),
            ('Tokens', 'output_tokens'), ('Cost USD', 'cost_usd')))
    rows = ''.join(f'<tr><th>{escape(key)}</th><td>{escape(_format(value))}</td></tr>'
                   for key, value in condition.items())
    notice = ('A fixture-provider report validates the environment and is not a scientific result.'
              if evaluation.get('target_provider') == 'fixture'
              else 'This synthetic controlled trial must be interpreted with the frozen protocol and pilot limitations.')
    body = (
        f'<h1>{escape(str(evaluation["trial_id"]))}</h1>'
        f'<p class="warning">{escape(notice)} Graph edges show recorded evidence, not causal proof.</p>'
        f'<div class="cards">{cards}</div><h2>Condition</h2><table>{rows}</table>'
        f'<h2>Recorded interaction graph</h2>{_graph_svg(graph)}'
        f'<h2>Evidence</h2><p><code>{escape(", ".join(evaluation["evidence_event_ids"]))}</code></p>')
    return _page(f'EXP-001 {evaluation["trial_id"]}', body)


def render_schedule_report(summary: dict[str, Any]) -> str:
    cells = ''.join(
        '<tr>'
        f'<td>{escape(name)}</td><td>{value["scheduled"]}</td><td>{value["valid"]}</td>'
        f'<td>{escape(_format(value["rate"]))}</td>'
        f'<td>{escape(_format(value["wilson_95"]))}</td>'
        f'<td>{value["failed_or_invalid"]}</td></tr>'
        for name, value in sorted(summary['cells'].items()))
    contrasts = ''.join(
        '<tr>'
        f'<td>{escape(name)}</td><td>{value["paired_seeds"]}</td>'
        f'<td>{escape(_format(value["mean_difference"]))}</td>'
        f'<td>{escape(_format(value["bootstrap_percentile_95"]))}</td>'
        f'<td><code>{escape(value["formula"])}</code></td></tr>'
        for name, value in sorted(summary['paired_contrasts'].items()))
    body = (
        '<h1>EXP-001 schedule report</h1>'
        f'<p class="warning">{escape(summary["note"])}</p>'
        '<div class="cards">'
        f'<div class="card"><div class="muted">Mode</div><div class="value">'
        f'{escape(str(summary.get("provider_mode", "unknown")))}</div></div>'
        f'<div class="card"><div class="muted">Scheduled</div><div class="value">'
        f'{summary["scheduled_trials"]}</div></div>'
        f'<div class="card"><div class="muted">Completed</div><div class="value">'
        f'{summary["completed_trials"]}</div></div></div>'
        '<h2>Incorrect-claim cells</h2><table><thead><tr><th>Cell</th><th>Scheduled</th>'
        '<th>Valid</th><th>False-belief rate</th><th>Wilson 95%</th><th>Failed/invalid</th>'
        f'</tr></thead><tbody>{cells}</tbody></table>'
        '<h2>Seed-paired contrasts</h2><table><thead><tr><th>Contrast</th><th>Seeds</th>'
        '<th>Mean difference</th><th>Bootstrap 95%</th><th>Formula</th></tr></thead>'
        f'<tbody>{contrasts}</tbody></table>')
    return _page('EXP-001 schedule report', body)
