"""A read-only permission registry — not a permission-editing engine.

This codebase has exactly one authorization primitive anywhere: `deps.py`'s `require_role(*role_
names)`, checked against `current_user.role.name`. There is no permissions table, no decorator
system, no middleware-based authorization (confirmed by grepping every reference to
`current_user.role` in the codebase — the only hit is inside `require_role` itself). "Permission
management" for this module therefore means *displaying* which roles can already do what, not
introducing a second, database-editable authorization system that would have to be kept in sync
with — or worse, silently diverge from — the `require_role(...)` calls that actually enforce
access in every router. Every row below is hand-transcribed from those real calls, not invented;
where no endpoint exists for an action the brief's own module/action grid implies (e.g. Wells has
no delete endpoint), that gap is recorded via `note` rather than fabricated.

`NON_VIEWER_ROLES` is imported from `alerts.py`, where it was first defined and is already
independently re-declared in 3 other routers (`ai_insights.py`, `reports.py`, `what_if.py`) —
importing it here rather than adding a 5th copy.
"""

from dataclasses import dataclass

from app.routers.alerts import NON_VIEWER_ROLES

ALL_AUTHENTICATED = (
    "Administrator",
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
    "Viewer",
)

ADMINISTRATOR_ONLY = ("Administrator",)


@dataclass(frozen=True)
class PermissionEntry:
    module: str
    action: str
    roles: tuple[str, ...]
    note: str | None = None


PERMISSION_MATRIX: list[PermissionEntry] = [
    # ----- Wells -----
    PermissionEntry("Wells", "View", ALL_AUTHENTICATED),
    PermissionEntry("Wells", "Create", ("Administrator", "Production Engineer")),
    PermissionEntry("Wells", "Edit", ("Administrator", "Production Engineer")),
    PermissionEntry("Wells", "Delete", (), note="Not implemented — no delete endpoint exists for wells."),

    # ----- Production -----
    PermissionEntry("Production", "View", ALL_AUTHENTICATED),
    PermissionEntry("Production", "Create", ("Administrator", "Production Engineer")),
    PermissionEntry("Production", "Edit", ("Administrator", "Production Engineer")),
    PermissionEntry("Production", "Delete", ("Administrator", "Production Engineer")),

    # ----- Equipment -----
    PermissionEntry("Equipment", "View", ALL_AUTHENTICATED),
    PermissionEntry("Equipment", "Create", ("Administrator", "Maintenance Engineer")),
    PermissionEntry("Equipment", "Edit", ("Administrator", "Maintenance Engineer")),
    PermissionEntry("Equipment", "Delete", ("Administrator", "Maintenance Engineer")),

    # ----- Maintenance -----
    PermissionEntry("Maintenance", "View", ALL_AUTHENTICATED),
    PermissionEntry("Maintenance", "Create", ("Administrator", "Maintenance Engineer")),
    PermissionEntry("Maintenance", "Edit", ("Administrator", "Maintenance Engineer")),
    PermissionEntry("Maintenance", "Delete", ("Administrator", "Maintenance Engineer")),

    # ----- Production Loss -----
    PermissionEntry("Production Loss", "View", ALL_AUTHENTICATED),
    PermissionEntry("Production Loss", "Create", ("Administrator", "Production Engineer")),
    PermissionEntry("Production Loss", "Edit", ("Administrator", "Production Engineer")),
    PermissionEntry("Production Loss", "Delete", ("Administrator", "Production Engineer")),

    # ----- Cost & Revenue -----
    # cost_revenue.py itself is read-only analytics — zero write endpoints. Create/Edit/Delete
    # live on the separate Operating Costs router; documented here under the brief's own naming.
    PermissionEntry("Cost & Revenue", "View", ALL_AUTHENTICATED),
    PermissionEntry(
        "Cost & Revenue", "Create", ("Administrator", "Management"),
        note="Operating Costs endpoint — Cost & Revenue's own endpoints are read-only analytics.",
    ),
    PermissionEntry(
        "Cost & Revenue", "Edit", ("Administrator", "Management"),
        note="Operating Costs endpoint.",
    ),
    PermissionEntry(
        "Cost & Revenue", "Delete", ("Administrator", "Management"),
        note="Operating Costs endpoint.",
    ),

    # ----- Alerts -----
    PermissionEntry("Alerts", "View", ALL_AUTHENTICATED),
    PermissionEntry("Alerts", "Acknowledge", NON_VIEWER_ROLES),
    PermissionEntry("Alerts", "Investigate", NON_VIEWER_ROLES),
    PermissionEntry("Alerts", "Resolve", NON_VIEWER_ROLES),
    PermissionEntry("Alerts", "Dismiss", NON_VIEWER_ROLES),
    PermissionEntry("Alerts", "Add Note", NON_VIEWER_ROLES),
    PermissionEntry("Alerts", "Create (manual)", ("Administrator", "Management")),
    PermissionEntry("Alerts", "Edit (manual)", ("Administrator", "Management")),
    PermissionEntry("Alerts", "Run Rules", ADMINISTRATOR_ONLY),

    # ----- AI Insights -----
    PermissionEntry("AI Insights", "View", ALL_AUTHENTICATED),
    PermissionEntry("AI Insights", "Generate", ADMINISTRATOR_ONLY, note="Bulk insight-engine run (POST /ai-insights/run)."),
    PermissionEntry("AI Insights", "Ask Assistant", NON_VIEWER_ROLES),
    PermissionEntry("AI Insights", "Feedback / Status / Interpret", NON_VIEWER_ROLES),

    # ----- What-If Simulator -----
    PermissionEntry("What-If", "View", ALL_AUTHENTICATED, note="Includes preview/compare/sensitivity — nothing persisted by these."),
    PermissionEntry("What-If", "Create / Save", NON_VIEWER_ROLES),
    PermissionEntry("What-If", "Rerun", NON_VIEWER_ROLES),
    PermissionEntry("What-If", "Delete", NON_VIEWER_ROLES),

    # ----- Reports -----
    PermissionEntry("Reports", "View", ALL_AUTHENTICATED, note="Includes preview — nothing persisted."),
    PermissionEntry("Reports", "Generate", NON_VIEWER_ROLES, note="Save/update/delete/regenerate."),
    PermissionEntry(
        "Reports", "Export", ALL_AUTHENTICATED,
        note="Any authenticated user — export streams an already-saved report's stored results, nothing is created.",
    ),

    # ----- Administration -----
    # Deliberately Administrator-only end to end, including reads — unlike every other module,
    # this one exposes user PII, system configuration, and the full audit trail.
    PermissionEntry("Administration", "View", ADMINISTRATOR_ONLY),
    PermissionEntry("Administration", "Manage Users", ADMINISTRATOR_ONLY),
    PermissionEntry("Administration", "Manage Roles", ADMINISTRATOR_ONLY, note="Role assignment only — roles themselves are fixed, not creatable through the UI (see docs)."),
    PermissionEntry("Administration", "Manage Settings", ADMINISTRATOR_ONLY),
    PermissionEntry("Administration", "View Audit Logs", ADMINISTRATOR_ONLY),
]
