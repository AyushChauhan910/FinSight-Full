"""Parse LLM report section text into structured shapes for the API / frontend."""

from __future__ import annotations

import re
from typing import Any


def split_report_by_markdown_headers(report: str) -> dict[str, str]:
    """Split a markdown report on ## headers into known section keys."""
    sections = {
        "executive_summary": "",
        "key_metrics": "",
        "risk_factors": "",
        "yoy_analysis": "",
        "investment_thesis": "",
    }
    if not report or not report.strip():
        return sections

    pattern = re.compile(r"(?m)^##\s+(.+?)\s*$")
    matches = list(pattern.finditer(report))
    if not matches:
        sections["executive_summary"] = report.strip()
        return sections

    for i, m in enumerate(matches):
        title = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(report)
        body = report[start:end].strip()
        if "executive" in title and "summary" in title:
            sections["executive_summary"] = body
        elif "key metric" in title:
            sections["key_metrics"] = body
        elif "risk" in title:
            sections["risk_factors"] = body
        elif "year" in title or "yoy" in title or "year-over" in title:
            sections["yoy_analysis"] = body
        elif "investment" in title and "thesis" in title:
            sections["investment_thesis"] = body

    return sections


def parse_key_metrics(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not text:
        return rows

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|[\s\-:|]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        metric = cells[0].lower()
        if metric in ("metric", "---", "--------"):
            continue
        name = cells[0]
        value = cells[1] if len(cells) > 1 else ""
        change_raw = cells[2] if len(cells) > 2 else ""
        prev = None
        pct: float | None = None
        m = re.search(r"([+-]?\d+\.?\d*)\s*%", change_raw)
        if m:
            try:
                pct = float(m.group(1))
            except ValueError:
                pct = None
        rows.append({
            "name": name,
            "value": value,
            "previous_value": prev if prev and prev not in ("—", "-", "N/A") else None,
            "change_pct": pct,
            "unit": None,
        })
    return rows


def parse_risk_factors(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not text:
        return out

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        body = re.sub(r"^[-*]\s*", "", line)
        m = re.match(r"^\*\*\[(HIGH|MEDIUM|LOW)\]\*\*\s*(.+)$", body, re.I)
        if not m:
            continue
        sev = m.group(1).upper()
        rest = m.group(2).strip()
        title = rest[:80]
        if "." in rest[:120]:
            title = rest.split(".")[0][:120].strip()
        cite = re.sub(r"\[Doc\s*\d+\]", "", rest).strip()
        out.append({
            "title": title or "Risk",
            "description": cite,
            "severity": sev if sev in ("HIGH", "MEDIUM", "LOW") else "MEDIUM",
        })
    return out


def parse_yoy_analysis(text: str) -> list[dict[str, Any]]:
    """Extract simple year labels and any numbers for chart fallbacks."""
    points: list[dict[str, Any]] = []
    if not text:
        return points

    year_pat = re.compile(r"(20\d{2}|FY\s*20\d{2})", re.I)
    money_pat = re.compile(r"\$[\d,.]+\s*[BMK]?|[\d,.]+\s*billion", re.I)

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ym = year_pat.search(line)
        if not ym:
            continue
        year = re.sub(r"FY\s*", "", ym.group(0), flags=re.I).strip()
        nums: list[float] = []
        for m in re.finditer(r"[\d,]+\.?\d*", line.replace(",", "")):
            try:
                v = float(m.group(0).replace(",", ""))
                if v > 1e6:
                    nums.append(v)
            except ValueError:
                pass
        rev = nums[0] if nums else None
        points.append({
            "year": year,
            "revenue": rev,
            "net_income": nums[1] if len(nums) > 1 else None,
            "gross_margin": None,
            "eps": None,
        })
    return points[:12]


def parse_investment_thesis(text: str) -> dict[str, list[str]]:
    bull: list[str] = []
    bear: list[str] = []
    if not text:
        return {"bull_case": bull, "bear_case": bear}

    mode: str | None = None
    for line in text.splitlines():
        raw = line.strip()
        low = raw.lower()
        if "bull" in low and "case" in low:
            mode = "bull"
            continue
        if "bear" in low and "case" in low:
            mode = "bear"
            continue
        if "base" in low and "case" in low:
            mode = None
            continue
        if not raw.startswith(("-", "*")):
            continue
        item = raw.lstrip("-*").strip()
        item = re.sub(r"\[Doc\s*\d+\]", "", item).strip()
        if not item:
            continue
        if mode == "bull":
            bull.append(item)
        elif mode == "bear":
            bear.append(item)

    if not bull and not bear:
        parts = re.split(r"\n{2,}", text)
        for p in parts:
            p = p.strip()
            if p:
                bull.append(p[:500])

    return {"bull_case": bull[:12], "bear_case": bear[:12]}


def build_structured_report(
    report_sections: dict[str, str],
    ticker: str,
    fallback_summary: str,
) -> dict[str, Any]:
    """Build the JSON shape expected by the React ReportViewer."""
    ex = (report_sections.get("executive_summary") or "").strip()
    if not ex:
        ex = (fallback_summary or "")[:1200] or f"No summary available for {ticker}."

    km = parse_key_metrics(report_sections.get("key_metrics") or "")
    rf = parse_risk_factors(report_sections.get("risk_factors") or "")
    yoy = parse_yoy_analysis(report_sections.get("yoy_analysis") or "")
    thesis = parse_investment_thesis(report_sections.get("investment_thesis") or "")

    return {
        "executive_summary": ex,
        "key_metrics": km,
        "risk_factors": rf,
        "yoy_analysis": yoy,
        "investment_thesis": thesis,
    }
