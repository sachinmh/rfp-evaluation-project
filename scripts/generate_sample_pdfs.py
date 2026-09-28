"""
Generates 4 fictional supplier RFP response PDFs for classroom use.
All company names, people, prices, and figures are synthetic.

Run: python scripts/generate_sample_pdfs.py
Output: data/sample_pdfs/*.pdf
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample_pdfs")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, spaceBefore=12)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(i, BODY)) for i in items],
        bulletType="bullet",
        leftIndent=14,
    )


def price_table(rows, header=("Line item", "Detail", "Cost (USD/yr)")):
    data = [list(header)] + [list(r) for r in rows]
    t = Table(data, colWidths=[1.8 * inch, 3.0 * inch, 1.6 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def build_pdf(filename, title, sections):
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=LETTER, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    flow = [Paragraph(title, H1)]
    for heading, body in sections:
        flow.append(Paragraph(heading, H2))
        if isinstance(body, list):
            for item in body:
                if isinstance(item, (Table,)):
                    flow.append(item)
                    flow.append(Spacer(1, 8))
                elif isinstance(item, dict) and item.get("type") == "bullets":
                    flow.append(bullets(item["items"]))
                else:
                    flow.append(Paragraph(item, BODY))
        else:
            flow.append(Paragraph(body, BODY))
    doc.build(flow)
    print(f"Wrote {path}")


# ---------------------------------------------------------------------------
# Apex Systems: strong technical design and security; higher price; moderate schedule
# ---------------------------------------------------------------------------
apex_sections = [
    ("Executive Summary", [
        "Apex Systems proposes a cloud-native procurement automation platform built on a "
        "microservices architecture with dedicated integration adapters for SAP, Oracle "
        "Financials, and Coupa. We understand the requirement as a need for a scalable, "
        "secure, and auditable RFP evaluation workflow supporting concurrent multi-department use.",
    ]),
    ("Proposed Solution & Implementation Approach", [
        "Our solution is composed of independently deployable services (intake, extraction, "
        "scoring, ranking, reporting) communicating over an internal event bus, allowing each "
        "component to scale horizontally under peak submission load.",
        {"type": "bullets", "items": [
            "Kubernetes-based deployment with autoscaling (tested to 5,000 concurrent evaluation jobs).",
            "API-first design with OpenAPI 3.1 specifications for all integration points.",
            "Multi-region active-active database replication for high availability (99.95% SLA).",
        ]},
    ]),
    ("Timeline, Team Structure, and Milestones", [
        "Total delivery duration: 22 weeks from contract signature.",
        price_table(
            rows=[
                ("Weeks 1-4", "Discovery & architecture sign-off", "Solution Architect, Lead PM"),
                ("Weeks 5-12", "Core platform build & integrations", "6 engineers, 1 QA lead"),
                ("Weeks 13-18", "Security hardening & UAT", "2 security engineers, QA team"),
                ("Weeks 19-22", "Go-live, hypercare, knowledge transfer", "Full delivery team"),
            ],
            header=("Phase", "Milestone", "Staffing"),
        ),
        "A named delivery lead is assigned for the full engagement; team size peaks at 9 FTEs "
        "during the build phase. Key project risk: integration testing with legacy ERP sandboxes "
        "may slip by up to 2 weeks; mitigation plan includes an early sandbox access request in week 1.",
    ]),
    ("Price Table and Assumptions", [
        price_table(
            rows=[
                ("Platform license", "Annual subscription, up to 25 concurrent users", "128,000"),
                ("Implementation", "One-time, fixed fee for described scope", "96,000"),
                ("Integration package", "SAP + Oracle + Coupa adapters", "42,000"),
                ("Premium support", "24/7, 1-hour critical response SLA", "31,000"),
            ]
        ),
        "Assumptions: pricing is in USD and excludes taxes; assumes client provides sandbox "
        "access to source ERP systems by week 2; a 3% annual escalation applies from year 2 onward.",
    ]),
    ("Security, Compliance, and Risk Controls", [
        "Apex Systems maintains ISO 27001 and SOC 2 Type II certification (renewed annually, "
        "audit reports available under NDA). All data is encrypted at rest (AES-256) and in "
        "transit (TLS 1.3). Role-based access control and full audit logging are standard.",
        {"type": "bullets", "items": [
            "Annual third-party penetration testing with remediation SLAs by severity.",
            "GDPR and CCPA-aligned data processing addendum available.",
            "Formal incident response plan with 4-hour client notification commitment.",
        ]},
    ]),
    ("Support Model, Relevant Experience, and References", [
        "24/7 follow-the-sun support model with a dedicated technical account manager. Apex "
        "Systems has delivered similar procurement automation platforms for three enterprise "
        "clients in the last four years, including a global manufacturing client processing "
        "over 1,200 supplier evaluations per quarter.",
        "References available on request: a regional healthcare distributor and a national "
        "logistics provider, both live on the platform for over 18 months.",
    ]),
]

# ---------------------------------------------------------------------------
# BrightPath Tech: lowest price and fastest timeline; weak compliance detail; limited experience
# ---------------------------------------------------------------------------
brightpath_sections = [
    ("Executive Summary", [
        "BrightPath Tech offers a lean, fast-to-deploy RFP scoring tool designed for teams that "
        "want to get up and running quickly without a lengthy implementation cycle. We believe "
        "speed and affordability are the top priorities for this engagement.",
    ]),
    ("Proposed Solution & Implementation Approach", [
        "A single web application with a built-in scoring engine and CSV import/export. The "
        "system is configured rather than integrated: criteria and weights are set through an "
        "admin screen, and supplier documents are uploaded manually by the evaluation team.",
        {"type": "bullets", "items": [
            "Hosted on a shared multi-tenant cloud environment.",
            "Basic REST API for exporting results; no pre-built ERP connectors at this time.",
        ]},
    ]),
    ("Timeline, Team Structure, and Milestones", [
        "Total delivery duration: 6 weeks from contract signature — the fastest option we offer.",
        price_table(
            rows=[
                ("Week 1", "Kickoff & environment setup", "1 implementation consultant"),
                ("Weeks 2-4", "Configuration & admin training", "1 implementation consultant"),
                ("Weeks 5-6", "Pilot run & go-live", "1 implementation consultant, 1 support rep"),
            ],
            header=("Phase", "Milestone", "Staffing"),
        ),
        "The engagement is delivered by a small team of two people. No formal risk register was "
        "prepared for this proposal; the team notes that timelines are aggressive and may shift "
        "if client feedback cycles run long.",
    ]),
    ("Price Table and Assumptions", [
        price_table(
            rows=[
                ("Platform subscription", "Annual, up to 25 users", "38,000"),
                ("Setup & configuration", "One-time fee", "12,000"),
                ("Standard support", "Business hours, email + chat", "6,000"),
            ]
        ),
        "Assumptions: pricing in USD, excludes taxes. Client is responsible for manually "
        "uploading all supplier PDFs; no ERP integration is included in this price.",
    ]),
    ("Security, Compliance, and Risk Controls", [
        "Data is encrypted in transit. We follow general industry best practices for application "
        "security. Formal third-party certification (e.g., SOC 2 or ISO 27001) is currently in "
        "progress and expected within the next 12 months; no audit report is available yet.",
        "Specific access control, audit logging, and incident response details were not "
        "included in this proposal.",
    ]),
    ("Support Model, Relevant Experience, and References", [
        "Support is provided via email and chat during business hours (9am-6pm, client's local "
        "time zone). BrightPath Tech was founded two years ago and has completed one similar "
        "deployment for a small regional retailer. No formal reference contacts were provided "
        "in this submission.",
    ]),
]

# ---------------------------------------------------------------------------
# NexaWorks: balanced; strongest implementation plan and support model
# ---------------------------------------------------------------------------
nexaworks_sections = [
    ("Executive Summary", [
        "NexaWorks proposes a balanced, well-governed rollout of an AI-assisted RFP evaluation "
        "platform, with particular emphasis on a low-risk phased implementation plan and a "
        "support model built around the client's day-to-day procurement operations.",
    ]),
    ("Proposed Solution & Implementation Approach", [
        "A modular platform combining configurable scoring workflows, structured document "
        "extraction, and a dedicated peer-benchmarking module, deployed in three controlled "
        "phases (pilot, limited rollout, full rollout) to minimize disruption.",
        {"type": "bullets", "items": [
            "Standard connectors for two major ERPs, with a documented custom-integration path for others.",
            "Configurable criteria and weighting managed entirely through an admin console.",
            "Built-in change-management toolkit (training materials, sample workflows, office hours).",
        ]},
    ]),
    ("Timeline, Team Structure, and Milestones", [
        "Total delivery duration: 14 weeks from contract signature, with a detailed RAID log "
        "(risks, assumptions, issues, dependencies) reviewed weekly with the client.",
        price_table(
            rows=[
                ("Weeks 1-2", "Discovery, criteria workshop, RAID log baseline", "PM, Solution Consultant"),
                ("Weeks 3-6", "Pilot build with 1 business unit", "4 engineers, 1 PM"),
                ("Weeks 7-10", "Pilot feedback, refinement, limited rollout", "4 engineers, 1 trainer"),
                ("Weeks 11-14", "Full rollout, training, handover", "Full team + 2 trainers"),
            ],
            header=("Phase", "Milestone", "Staffing"),
        ),
        "A named escalation path and weekly steering committee cadence are included by default, "
        "along with a documented rollback plan for each rollout phase.",
    ]),
    ("Price Table and Assumptions", [
        price_table(
            rows=[
                ("Platform license", "Annual subscription, up to 25 users", "84,000"),
                ("Implementation", "Phased delivery, fixed fee", "58,000"),
                ("Change management toolkit", "Training materials, workshops", "9,500"),
                ("Standard support", "Business hours, 4-hour response SLA", "14,000"),
            ]
        ),
        "Assumptions: pricing in USD, excludes taxes; assumes one named business sponsor is "
        "available for weekly check-ins throughout the engagement.",
    ]),
    ("Security, Compliance, and Risk Controls", [
        "NexaWorks holds SOC 2 Type II certification and follows a documented secure SDLC. "
        "Access is role-based with quarterly access reviews. A named data protection officer "
        "is available for compliance questions during the engagement.",
        {"type": "bullets", "items": [
            "Encryption at rest and in transit (industry-standard algorithms).",
            "Quarterly vulnerability scans; annual penetration test summary shared with clients.",
        ]},
    ]),
    ("Support Model, Relevant Experience, and References", [
        "Dedicated customer success manager plus a shared support desk (business hours, "
        "4-hour response SLA, 24/7 for Severity 1 incidents). NexaWorks has delivered five "
        "similar procurement or vendor-evaluation platforms in the past three years across "
        "retail, logistics, and public-sector clients.",
        "Two references available on request, including a public-sector client that cited the "
        "phased rollout plan as a key reason for on-time go-live.",
    ]),
]

# ---------------------------------------------------------------------------
# Orbit Digital: strong experience and references; vague integration plan; medium pricing
# ---------------------------------------------------------------------------
orbit_sections = [
    ("Executive Summary", [
        "Orbit Digital brings over a decade of experience delivering procurement and vendor "
        "management systems for enterprise clients. This proposal outlines our approach to "
        "delivering a supplier evaluation and ranking capability leveraging our existing "
        "platform accelerators.",
    ]),
    ("Proposed Solution & Implementation Approach", [
        "We will adapt our existing vendor-management accelerator to support RFP scoring and "
        "ranking. Integration with the client's environment will be scoped in detail during "
        "the discovery phase; exact connector requirements will be finalized once systems "
        "access is granted.",
        {"type": "bullets", "items": [
            "Reuses proven scoring UI components from our vendor-management product line.",
            "Integration approach to be confirmed after discovery; likely a mix of file-based "
            "exchange and API calls depending on the client's source systems.",
        ]},
    ]),
    ("Timeline, Team Structure, and Milestones", [
        "Estimated delivery duration: 16-20 weeks, with the final schedule confirmed after the "
        "discovery phase clarifies integration scope.",
        price_table(
            rows=[
                ("Weeks 1-3", "Discovery & scoping (integration approach finalized here)", "Engagement Lead"),
                ("Weeks 4-14", "Build & configuration", "5 engineers"),
                ("Weeks 15-20", "Testing, go-live", "5 engineers, 1 QA"),
            ],
            header=("Phase", "Milestone", "Staffing"),
        ),
        "Named engagement lead has 12 years in procurement technology delivery; detailed "
        "milestone dates for the build phase will be issued after discovery.",
    ]),
    ("Price Table and Assumptions", [
        price_table(
            rows=[
                ("Platform license", "Annual subscription, up to 25 users", "70,000"),
                ("Implementation", "Estimated, subject to discovery findings", "65,000 (est.)"),
                ("Support", "Business hours support", "10,000"),
            ]
        ),
        "Assumptions: final implementation cost will be confirmed after discovery; figures "
        "above are a planning-level estimate in USD, excluding taxes.",
    ]),
    ("Security, Compliance, and Risk Controls", [
        "Orbit Digital's platform has passed enterprise security reviews with several Fortune "
        "500 clients. Standard encryption and access control practices are in place. Detailed "
        "certification documentation and audit reports can be shared during due diligence.",
    ]),
    ("Support Model, Relevant Experience, and References", [
        "Orbit Digital has delivered over 20 vendor and procurement management engagements in "
        "the last ten years. Three enterprise references are available immediately, including "
        "a Fortune 500 retail client and a large public university system, both of whom have "
        "used our platform for over three years.",
        "Support is provided during business hours with a dedicated account manager assigned "
        "post-go-live.",
    ]),
]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    build_pdf("apex_systems.pdf", "RFP Response: Apex Systems", apex_sections)
    build_pdf("brightpath_tech.pdf", "RFP Response: BrightPath Tech", brightpath_sections)
    build_pdf("nexaworks.pdf", "RFP Response: NexaWorks", nexaworks_sections)
    build_pdf("orbit_digital.pdf", "RFP Response: Orbit Digital", orbit_sections)


if __name__ == "__main__":
    main()
