#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXE PD 패킷 생성기 v6.8.5 (rebuild3 FIXED)

Fix 목표:
- 'module datetime has no attribute dt' 완전 종결
- 'unsupported operand type(s) for /: str and str' 재발 방지(Path 통일)
- math import 누락/ dt.datetime 사용 오류 수정
- 기존 PD 계산 파이프라인(정밀 PD 루프) 유지
"""

from __future__ import annotations

import re, os, json, zipfile, hashlib, sys
import math
import datetime as dt  # 표준 datetime 모듈을 dt로 사용 (정석)
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

try:
    import swisseph as swe  # pyswisseph
except Exception:
    swe = None

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

TZ_DEFAULT = "Asia/Seoul"
STEP_MINUTES = 2
# 후보 생성: 2분 그리드 + 1분 오프셋 합집합(B 방식) 활성화
ENABLE_OFFSET1 = True


# ---------- util ----------
def sanitize_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r'[\\/:*?"<>|]', "", s)
    return s or "UNKNOWN"

def yymmdd_now() -> str:
    # ✅ 올바른 호출: dt.datetime.now()
    return dt.datetime.now().strftime("%y%m%d")

def unique_outpath(folder: Path, base_name: str) -> Path:
    folder = Path(folder)
    p = folder / base_name
    if not p.exists():
        return p
    stem, suf = p.stem, p.suffix
    i = 2
    while True:
        cand = folder / f"{stem}_v{i}{suf}"
        if not cand.exists():
            return cand
        i += 1

def parse_pasted_rows(raw: str) -> List[List[str]]:
    """
    Excel TSV 복붙(멀티라인/따옴표) 정석 파싱: csv.reader
    """
    import csv, io
    s = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    s = s.strip("\n")
    if not s.strip():
        return []

    f = io.StringIO(s)
    reader = csv.reader(f, delimiter="\t", quotechar='"', doublequote=True)

    rows: List[List[str]] = []
    for row in reader:
        if not row or all((c or "").strip() == "" for c in row):
            continue
        # drop leading empty cells (숨김 A열 등)
        while row and (row[0] or "").strip() == "":
            row = row[1:]
        rows.append(row)
    return rows

def hhmm_to_min(hhmm: str) -> int:
    hh, mm = map(int, hhmm.split(":"))
    return hh*60 + mm

def min_to_hhmm(m: int) -> str:
    m = max(0, min(1439, int(m)))
    return f"{m//60:02d}:{m%60:02d}"

def clamp_minute(m: int) -> int:
    return max(0, min(1439, int(m)))

def add_months(yyyy_mm: str, delta: int) -> str:
    y, m = map(int, yyyy_mm.split("-"))
    m2 = m + delta
    y += (m2-1)//12
    m2 = (m2-1)%12 + 1
    return f"{y:04d}-{m2:02d}"

def parse_birth_date(text: str) -> Optional[str]:
    """YYYY.MM.DD / YYYY-MM-DD / YYYY/MM/DD만 허용 (월/일 뒤집기 금지)"""
    s = (text or "").strip()
    m = re.search(r"(?P<y>\d{4})[.\-/](?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})", s)
    if not m:
        return None
    y = int(m.group("y"))
    mo = int(m.group("m"))
    d = int(m.group("d"))
    try:
        return dt.date(y, mo, d).isoformat()
    except Exception:
        return None


# ---------- birth time parsing ----------
def normalize_birth_time(expr: str) -> Dict[str, Any]:
    s0 = "" if expr is None else str(expr)
    s = s0.strip()
    if not s:
        return {"confidence":"UNKNOWN", "raw":s0}

    s = (s.replace("오전","AM ").replace("오후","PM ").replace("새벽","DAWN ").replace("밤","NIGHT "))
    s = re.sub(r"\s+"," ", s).strip()

    def to_24(pref: str, h: int) -> int:
        if pref == "PM" and h < 12: return h+12
        if pref == "AM" and h == 12: return 0
        if pref == "NIGHT" and h < 12: return h+12
        return h

    # RANGE: "07~08시경" 등 → ±10
    if "~" in s or re.search(r"\d+\s*-\s*\d+", s) or "에서" in s:
        parts = re.split(r"~|에서|까지|\s*-\s*", s)
        parts = [p for p in parts if p.strip()]
        if len(parts) >= 2:
            def parse_hm(p: str) -> Optional[int]:
                p = p.strip()
                pref_m = re.search(r"\b(AM|PM|DAWN|NIGHT)\b", p)
                pref = pref_m.group(1) if pref_m else ""
                hm = re.search(r"(\d{1,2})\s*(?::|시)\s*(\d{1,2})\s*분?", p)
                if hm:
                    h = to_24(pref, int(hm.group(1))); mi = int(hm.group(2))
                    return h*60+mi
                h_only = re.search(r"(\d{1,2})\s*시?", p)
                if h_only:
                    h = to_24(pref, int(h_only.group(1)))
                    return h*60
                return None

            start = parse_hm(parts[0])
            end = parse_hm(parts[1])
            if start is not None and end is not None:
                ex_s = clamp_minute(start-10); ex_e = clamp_minute(end+10)
                return {"confidence":"RANGE", "raw":s0,
                        "core_start": min_to_hhmm(start), "core_end": min_to_hhmm(end),
                        "expanded_start": min_to_hhmm(ex_s), "expanded_end": min_to_hhmm(ex_e)}

    # EXACT minute → ±10
    m = re.search(r"(?:\b(AM|PM|DAWN|NIGHT)\b\s*)?(\d{1,2})\s*[:시]\s*(\d{1,2})\s*분?", s)
    if m:
        pref = m.group(1) or ""
        h = to_24(pref, int(m.group(2))); mi = int(m.group(3))
        center = h*60+mi
        ex_s = clamp_minute(center-10); ex_e = clamp_minute(center+10)
        return {"confidence":"EXACT","raw":s0,"expanded_start":min_to_hhmm(ex_s),"expanded_end":min_to_hhmm(ex_e)}

    # AROUND (경/전후/반경) → ±20 (당신 규칙)
    if re.search(r"(경|전후|반경)", s):
        m_half = re.search(r"(?:\b(AM|PM|DAWN|NIGHT)\b\s*)?(\d{1,2})\s*시\s*반", s)
        if m_half:
            pref = m_half.group(1) or ""
            h = to_24(pref, int(m_half.group(2)))
            center = h*60+30
            ex_s = clamp_minute(center-20); ex_e = clamp_minute(center+20)
            return {"confidence":"AROUND","raw":s0,"expanded_start":min_to_hhmm(ex_s),"expanded_end":min_to_hhmm(ex_e)}
        m_h = re.search(r"(?:\b(AM|PM|DAWN|NIGHT)\b\s*)?(\d{1,2})\s*시", s)
        if m_h:
            pref = m_h.group(1) or ""
            h = to_24(pref, int(m_h.group(2)))
            center = h*60
            ex_s = clamp_minute(center-20); ex_e = clamp_minute(center+20)
            return {"confidence":"AROUND","raw":s0,"expanded_start":min_to_hhmm(ex_s),"expanded_end":min_to_hhmm(ex_e)}

    return {"confidence":"UNKNOWN","raw":s0}


# ---------- event time parsing ----------
SEASON_MONTHS = {"봄": ("02","06"), "여름": ("05","09"), "가을": ("09","11"), "겨울": ("11","02")}

def parse_event_time(raw: str) -> Dict[str, Any]:
    s = (raw or "").strip()
    if not s:
        return {"parse_ok": False, "granularity":"UNKNOWN", "note":"빈 문자열", "start":None, "end":None}

    # 1) year range like 2007-8년 / 2007~2008년
    yr = re.search(r"(?P<y1>19\d{2}|20\d{2})\s*[-~]\s*(?P<y2>\d{1,4})\s*년", s)
    if yr:
        y1 = int(yr.group("y1"))
        y2s = yr.group("y2")
        y2 = int(y2s) if len(y2s) == 4 else int(str(y1)[:2] + y2s.zfill(2))
        rest = s[yr.end():]
        for k,(m1,m2) in SEASON_MONTHS.items():
            if k in rest:
                if k != "겨울":
                    return {"parse_ok": True, "granularity":"SEASON", "note":"", "start":f"{y1:04d}-{m1}", "end":f"{y1:04d}-{m2}"}
                return {"parse_ok": True, "granularity":"SEASON", "note":"", "start":f"{y1:04d}-11", "end":f"{y2:04d}-02"}
        return {"parse_ok": True, "granularity":"RANGE", "note":"", "start":f"{y1:04d}-01", "end":f"{y2:04d}-12"}

    # 2) explicit date or year-month: YYYY[.-/]MM([.-/]DD)?
    # NOTE: alternation order matters. If we put 0?[1-9] first,
    # it can match only the first digit of "11" (=> month becomes 1).
    # So we match 10~12 first.
    m = re.search(r"(?P<y>19\d{2}|20\d{2})[.\-/](?P<m>1[0-2]|0?[1-9])(?:[.\-/](?P<d>3[01]|[12]\d|0?[1-9]))?", s)
    if m:
        year = int(m.group("y"))
        mo = int(m.group("m"))
        return {"parse_ok": True, "granularity":"MONTH", "note":"", "start":f"{year:04d}-{mo:02d}", "end":f"{year:04d}-{mo:02d}"}

    # 3) year token
    y = re.search(r"(19\d{2}|20\d{2})", s)
    if not y:
        return {"parse_ok": False, "granularity":"UNKNOWN", "note":"연도 없음", "start":None, "end":None}
    year = int(y.group(1))
    rest = s[y.end():]

    if "상반기" in rest:
        return {"parse_ok": True, "granularity":"RANGE", "note":"", "start":f"{year:04d}-01", "end":f"{year:04d}-06"}
    if "하반기" in rest:
        return {"parse_ok": True, "granularity":"RANGE", "note":"", "start":f"{year:04d}-07", "end":f"{year:04d}-12"}

    for k,(m1,m2) in SEASON_MONTHS.items():
        if k in rest:
            if k != "겨울":
                return {"parse_ok": True, "granularity":"SEASON", "note":"", "start":f"{year:04d}-{m1}", "end":f"{year:04d}-{m2}"}
            return {"parse_ok": True, "granularity":"SEASON", "note":"", "start":f"{year:04d}-11", "end":f"{year+1:04d}-02"}

    mr = re.search(r"\b(0?[1-9]|1[0-2])\s*[-~]\s*(0?[1-9]|1[0-2])\b", rest)
    if mr:
        a = int(mr.group(1)); b = int(mr.group(2))
        return {"parse_ok": True, "granularity":"RANGE", "note":"", "start":f"{year:04d}-{min(a,b):02d}", "end":f"{year:04d}-{max(a,b):02d}"}

    m1 = re.search(r"(0?[1-9]|1[0-2])\s*월", rest) or re.search(r"\b(0?[1-9]|1[0-2])\b", rest)
    if m1:
        mo = int(m1.group(1))
        mm = f"{year:04d}-{mo:02d}"
        return {"parse_ok": True, "granularity":"MONTH", "note":"", "start":mm, "end":mm}

    return {"parse_ok": False, "granularity":"UNKNOWN", "note":"월/계절 정보 없음", "start":None, "end":None}

def window_for_event(parsed: Dict[str, Any], raw: str = "") -> Optional[Tuple[str,str]]:
    """Return (start_month, end_month) window for an event.

    Default: for MONTH granularity, use ±2 months. (프로토콜: 모든 사건 윈도우 기본 ±2개월)
    Exception: University admission events (대학/대학교 + 입학/진학/합격 ...) occurring in March
    should be searched from previous December through March (합격~입학 윈도우).
    """
    if not parsed.get("parse_ok"):
        return None

    raw_s = (raw or "").strip()

    if parsed["granularity"] == "MONTH":
        # --- Exception: 대학 입학/진학/합격 (3월 기준: 전년도 12월 ~ 당해 3월) ---
        try:
            y = int(parsed["start"][:4])
            m = int(parsed["start"][5:7])
        except Exception:
            y, m = None, None


        # --- Exception: 대학 편입 (합격 5~6월경 + 편입 시기 8~10월 가중) ---
        # 사용자 규칙: 편입 사건은 5월~10월 윈도우로 탐색 (우선순위는 8~10월)
        if y is not None and re.search(r"(대학|대학교|대학원)", raw_s) and re.search(r"(편입|편입학)", raw_s):
            return (f"{y}-05", f"{y}-10")

        if y is not None and m == 3:
            # broad keyword coverage requested by user
            # Examples: '대학 입학', '대학진학', '대학 합격', '대학교 입학', '대학원 진학/합격'
            if re.search(r"(대학|대학교|대학원)", raw_s) and re.search(r"(입학|진학|합격|편입|입시|전형|수시|정시)", raw_s):
                return (f"{y-1}-12", f"{y}-03")

        # default MONTH window (±2 months)
        return (add_months(parsed["start"], -2), add_months(parsed["end"], +2))

    # RANGE/SEASON 등도 기본 ±2개월 확장
    return (add_months(parsed["start"], -2), add_months(parsed["end"], +2))


# ---------- placeDB ----------
def load_place_db(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # placeDB 컬럼명 호환(기본은 place, lat, lon)
    if "place" not in df.columns:
        # 첫 컬럼을 place로 간주
        df = df.rename(columns={df.columns[0]: "place"})
    df["place"] = df["place"].astype(str)
    return df

def normalize_place_token(s: str) -> str:
    s = (s or "").strip().strip('"').strip("'")
    s = re.sub(r"\s+", " ", s)
    for suf in ["특별자치시","특별시","광역시","자치시","시","군","구"]:
        if s.endswith(suf) and len(s) > len(suf):
            s = s[:-len(suf)]
            break
    return s.strip()

def find_place_in_row(df: pd.DataFrame, row_cells: List[str]) -> Tuple[Optional[str], Optional[Dict[str,float]]]:
    tokens = []
    for c in row_cells:
        c0 = str(c or "").strip()
        if not c0:
            continue
        parts = re.split(r"[,\|/·\u00B7;:\(\)\[\]\{\}\s]+", c0)
        for p in parts:
            p = normalize_place_token(p)
            if p:
                tokens.append(p)

    place_list = df["place"].astype(str).tolist()
    place_set = set(place_list)

    # exact
    for t in tokens:
        if t in place_set:
            hit = df[df["place"] == t].iloc[0]
            return t, {"lat": float(hit["lat"]), "lon": float(hit["lon"])}

    # contains
    for t in tokens:
        hit = df[df["place"].astype(str).str.contains(re.escape(t), na=False)]
        if not hit.empty:
            r = hit.iloc[0]
            return t, {"lat": float(r["lat"]), "lon": float(r["lon"])}

    return None, None


# ---------- PD compute (정밀 루프 유지) ----------
def compute_pd_hits_for_candidate(
    cand: pd.DataFrame,
    event_recs: List[Dict[str,Any]],
    birth_date: str,
    geo: Dict[str,float],
    tz_name: str = "Asia/Seoul",
) -> pd.DataFrame:
    cols = [
        "candidate_id","candidate_time_hhmm","event_id","window_start_month","window_end_month",
        "hit_date","mode","promissor","significator","aspect","direction","arc_deg","notes"
    ]
    if swe is None or cand is None or cand.empty:
        return pd.DataFrame(columns=cols)

    DEG_PER_YEAR = 0.985647      # Naibod
    DAYS_PER_YEAR = 365.242189

    def norm360(x: float) -> float:
        x = x % 360.0
        if x < 0: x += 360.0
        return x

    def antiscia(lon: float) -> float:
        lon = norm360(lon)
        if lon < 180.0:
            return norm360(180.0 - lon)
        return norm360(540.0 - lon)

    def contra_antiscia(lon: float) -> float:
        return norm360(antiscia(lon) + 180.0)

    def lon_to_ra(lon_deg: float, eps_deg: float) -> float:
        lon = math.radians(norm360(lon_deg))
        eps = math.radians(eps_deg)
        x = math.cos(lon)
        y = math.sin(lon) * math.cos(eps)
        ra = math.degrees(math.atan2(y, x))
        return norm360(ra)

    def get_eps(jd_ut: float) -> float:
        try:
            v, _ = swe.calc_ut(jd_ut, swe.ECL_NUT)
            return float(v[0])
        except Exception:
            return 23.4392911

    def planet_lon(jd_ut: float, pid: int) -> float:
        v, _ = swe.calc_ut(jd_ut, pid)
        return float(v[0])

    def add_days(d0: dt.date, days: float) -> dt.date:
        return (dt.datetime.combine(d0, dt.time()) + dt.timedelta(days=float(days))).date()

    def ym_int(ym: str) -> int:
        y,m = ym.split("-")
        return int(y)*100+int(m)

    def date_ym_int(d: dt.date) -> int:
        return d.year*100 + d.month

    # event windows
    windows=[]
    for ev in event_recs:
        w = ev.get("window")
        if w and w.get("start_month") and w.get("end_month"):
            ws = w["start_month"]; we = w["end_month"]
            windows.append((ev["event_id"], ym_int(ws), ym_int(we), ws, we))

    if not windows:
        return pd.DataFrame(columns=cols)

    lat = float(geo.get("lat", 0.0)) if geo else 0.0
    lon = float(geo.get("lon", 0.0)) if geo else 0.0

    bdate = dt.date.fromisoformat(str(birth_date).replace(".","-"))

    aspects = [("Conj",0.0),("Sextil",60.0),("Quadrat",90.0),("Trigon",120.0),("Oppositio",180.0)]
    planets = [("Sun",swe.SUN),("Moon",swe.MOON),("Mercury",swe.MERCURY),("Venus",swe.VENUS),
               ("Mars",swe.MARS),("Jupiter",swe.JUPITER),("Saturn",swe.SATURN)]

    out=[]
    for _, row in cand.iterrows():
        cid=row["candidate_id"]; hhmm=row["candidate_time_hhmm"]
        hh,mm = map(int, hhmm.split(":"))
        dt_local = dt.datetime.combine(bdate, dt.time(hour=hh, minute=mm))

        # Asia/Seoul +9 고정(엔진 규칙 유지)
        jd_ut = swe.julday(dt_local.year, dt_local.month, dt_local.day,
                           dt_local.hour + dt_local.minute/60.0 - 9.0)

        eps = get_eps(jd_ut)

        # angles (Placidus)
        try:
            h = swe.houses_ex(jd_ut, lat, lon, b'P')
            ascmc = h[1]
            asc = float(ascmc[0]); mc = float(ascmc[1])
        except Exception:
            asc = 0.0; mc = 0.0

        sun = planet_lon(jd_ut, swe.SUN)
        moon = planet_lon(jd_ut, swe.MOON)
        is_day = (norm360(sun - asc) < 180.0)
        lof = norm360(asc + (moon - sun) if is_day else asc + (sun - moon))

        # Angles (include opposites: Dsc/IC) — required for matching reference PD logs
        dsc = norm360(asc + 180.0)
        ic  = norm360(mc  + 180.0)

        sigs=[(nm, planet_lon(jd_ut,pid)) for nm,pid in planets] + [("Asc",asc),("MC",mc),("LoF",lof),("Dsc",dsc),("IC",ic)]
        proms=[(nm, planet_lon(jd_ut,pid), "") for nm,pid in planets] + [("Asc",asc,""),("MC",mc,""),("LoF",lof,""),("Dsc",dsc,""),("IC",ic,"")]

        # antiscia expansions
        proms2=[]
        sigs2=[]
        for nm,lon0,tag in proms:
            proms2.append((nm,lon0,tag))
            proms2.append((nm+"_Ant", antiscia(lon0),"Ant"))
            proms2.append((nm+"_CAn", contra_antiscia(lon0),"CAn"))
        for nm,lon0 in sigs:
            sigs2.append((nm,lon0))
            sigs2.append((nm+"_Ant", antiscia(lon0)))
            sigs2.append((nm+"_CAn", contra_antiscia(lon0)))
        proms=proms2; sigs=sigs2

        for prom_nm, prom_lon, prom_tag in proms:
            ra_prom = lon_to_ra(prom_lon, eps)
            for sig_nm, sig_lon in sigs:
                for asp_nm, asp_deg in aspects:
                    for sign in (1,-1) if asp_deg not in (0.0,180.0) else (1,):
                        tgt_lon = norm360(sig_lon + sign*asp_deg)
                        ra_tgt = lon_to_ra(tgt_lon, eps)

                        sig_ra = lon_to_ra(sig_lon, eps)
                        ra_tgt_z = ra_tgt

                        for mode in ("Z","M"):
                            # Z: zodiacal (aspect on longitude -> RA)
                            # M: equatorial-style (aspect on RA) to separate arcs from Z
                            ra_tgt_mode = ra_tgt_z if mode=="Z" else norm360(sig_ra + sign*asp_deg)

                            arc_d = norm360(ra_tgt_mode - ra_prom)
                            arc_c = norm360(ra_prom - ra_tgt_mode)

                            for direction, arc in (("D",arc_d),("C",arc_c)):
                                years = arc / DEG_PER_YEAR
                                hit_date = add_days(bdate, years * DAYS_PER_YEAR)
                                hit_ym = date_ym_int(hit_date)

                                for eid, ws_i, we_i, ws_s, we_s in windows:
                                    if ws_i <= hit_ym <= we_i:
                                        out.append({
                                            "candidate_id": cid,
                                            "candidate_time_hhmm": hhmm,
                                            "event_id": eid,
                                            "window_start_month": ws_s,
                                            "window_end_month": we_s,
                                            "hit_date": hit_date.isoformat(),
                                            "mode": mode,
                                            "promissor": prom_nm,
                                            "significator": sig_nm,
                                            "aspect": asp_nm,
                                            "direction": direction,
                                            "arc_deg": arc,
                                            "notes": prom_tag
                                        })


    df=pd.DataFrame(out)
    if df.empty:
        return pd.DataFrame(columns=cols)
    return df.sort_values(["candidate_id","event_id","hit_date","mode","direction","promissor","significator"])


# ---------- packet build ----------
def assets_root() -> Path:
    """Return absolute path to bundled assets.
    - In PyInstaller onefile mode, resources are extracted to sys._MEIPASS.
    - In source mode, assets live next to this .py file.
    """
    base = None
    if hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        base = Path(__file__).resolve().parent
    return base / "assets"

def build_packet(row_cells: List[str], keyevents_text: str, out_folder: Path) -> Path:
    birth_time_raw = row_cells[0].strip() if len(row_cells) > 0 else ""
    client_name = row_cells[1].strip() if len(row_cells) > 1 else "UNKNOWN"
    sex_raw = row_cells[2].strip() if len(row_cells) > 2 else ""

    row_raw = "\t".join(row_cells)
    birth_date = parse_birth_date(row_raw)

    bt = normalize_birth_time(birth_time_raw)
    exp_start = bt.get("expanded_start"); exp_end = bt.get("expanded_end")
    if not birth_date or not exp_start or not exp_end:
        raise ValueError("출생일/생시 범위 파싱 실패. (birth_date 또는 expanded_start/end 없음)")

    start_min = hhmm_to_min(exp_start); end_min = hhmm_to_min(exp_end)
    if end_min < start_min:
        raise ValueError("생시 범위가 자정을 넘는 형태는 현재 지원하지 않습니다.")

        # 후보 분 단위 그리드 생성
    # 기본: 2분 간격
    base = list(range(start_min, end_min+1, STEP_MINUTES))
    if ENABLE_OFFSET1:
        # B 방식: 2분 그리드 + 1분 오프셋(홀수분) 합집합 → 1분 단위 전체(범위 내)
        off = list(range(start_min+1, end_min+1, STEP_MINUTES))
        mins = sorted(set(base) | set(off))
        step_effective = 1
    else:
        mins = base
        step_effective = STEP_MINUTES
    cand = pd.DataFrame({
        "candidate_id":[f"T{i+1:04d}" for i in range(len(mins))],
        "candidate_time_hhmm":[min_to_hhmm(m) for m in mins],
    })
    cand["range_bucket"] = "EXPANDED"
    if bt.get("confidence") == "RANGE" and bt.get("core_start") and bt.get("core_end"):
        cs = hhmm_to_min(bt["core_start"]); ce = hhmm_to_min(bt["core_end"])
        cand.loc[(cand["candidate_time_hhmm"].apply(hhmm_to_min) >= cs) & (cand["candidate_time_hhmm"].apply(hhmm_to_min) <= ce),
                 "range_bucket"] = "CORE"
    cand["birth_datetime_local"] = [f"{birth_date} {t}" for t in cand["candidate_time_hhmm"]]

    # events parse: 남은 모든 셀에서 가능한 만큼 분해
    events_raw: List[str] = []
    for c in row_cells[3:]:
        if not str(c).strip():
            continue
        parts = re.split(r"\n|;|•|·|／|/|\u2022|\u00B7", str(c).replace("\r",""))
        for p in parts:
            p = p.strip()
            if p:
                events_raw.append(p)

    key_lines = [l.strip() for l in (keyevents_text or "").replace("\r","").split("\n") if l.strip()]
    use_jupiter = True if key_lines else False

    event_recs = []
    for i, ev in enumerate(events_raw, start=1):
        parsed = parse_event_time(ev)
        win = window_for_event(parsed, ev)
        event_recs.append({
            "event_id": f"E{i:03d}",
            "raw": ev,
            "parsed": {
                "start_month": parsed["start"],
                "end_month": parsed["end"],
                "granularity": parsed["granularity"],
                "parse_ok": bool(parsed.get("parse_ok")),
                "note": parsed.get("note","")
            },
            "window": None if win is None else {"start_month": win[0], "end_month": win[1]}
        })

    aroot = assets_root()
    pdb_path = aroot / "placeDB.csv"
    if not pdb_path.exists():
        raise ValueError(f"assets/placeDB.csv 없음: {pdb_path}")
    pdb = load_place_db(pdb_path)

    place_raw, geo = find_place_in_row(pdb, row_cells)
    if geo is None:
        raise ValueError("placeDB에서 도시를 찾지 못했습니다. (입력 행에 도시명이 포함되어야 함)")

    packet = {
        "version": "EXE_PD_PACKET_v6.8.6_MZFIX2",
        "engine_tag": "v6.8.6_MZFIX2 (M/Z split + PyInstaller assets_root)",
        "engine_exe": os.path.basename(sys.argv[0]),
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "timezone": TZ_DEFAULT,
        "client_name": client_name,
        "source_row_raw": row_raw,
        "birth": {"date": birth_date, "place_raw": place_raw, "place_geocode": geo, "sex_raw": sex_raw},
        "birth_time_input": {
            "raw": birth_time_raw,
            "confidence": bt.get("confidence","UNKNOWN"),
            "core": None if bt.get("confidence")!="RANGE" else {"start_hhmm": bt.get("core_start"), "end_hhmm": bt.get("core_end")},
            "expanded": {"start_hhmm": exp_start, "end_hhmm": exp_end},
            "step_minutes": step_effective
        },
        "jupiter_ingress": {"use": use_jupiter, "keyevents_count": len(key_lines)}
    }

    out_folder = Path(out_folder).expanduser()
    out_folder.mkdir(parents=True, exist_ok=True)

    out_name = f"{yymmdd_now()}_{sanitize_filename(client_name)}_PD.zip"
    out_path = unique_outpath(out_folder, out_name)

    tmp = out_folder / f".__tmp_packet_{hashlib.md5(row_raw.encode('utf-8','ignore')).hexdigest()[:8]}"
    tmp.mkdir(exist_ok=True)

    (tmp/"packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    with (tmp/"events.jsonl").open("w", encoding="utf-8") as f:
        for r in event_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    cand.to_csv(tmp/"candidates.csv", index=False, encoding="utf-8")

    if swe is not None:
        ephe_path = str(aroot/"ephe")
        if os.path.isdir(ephe_path):
            swe.set_ephe_path(ephe_path)

    pd_hits = compute_pd_hits_for_candidate(cand, event_recs, birth_date, geo, TZ_DEFAULT)
    pd_hits.to_csv(tmp/"pd_hits.csv", index=False, encoding="utf-8")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for fn in ["packet.json","events.jsonl","candidates.csv","pd_hits.csv"]:
            z.write(tmp/fn, arcname=fn)

    # cleanup
    try:
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()
    except Exception:
        pass

    return out_path


# ---------- UI ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EXE PD 패킷 생성기 v6.8.5")
        self.geometry("980x720")
        self._build()

    def _build(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="입력 (A행 복붙: 고객 1행 전체)", font=("Malgun Gothic", 11, "bold")).pack(anchor="w")
        self.txt_a = tk.Text(frm, height=10, wrap="none")
        self.txt_a.pack(fill="x", pady=(6, 16))

        ttk.Label(frm, text="(선택) 목성 잉그레스 대표 사건 입력(통 입력)", font=("Malgun Gothic", 11, "bold")).pack(anchor="w")
        self.txt_k = tk.Text(frm, height=6, wrap="word")
        self.txt_k.pack(fill="x", pady=(6, 10))

        outfrm = ttk.Frame(frm)
        outfrm.pack(fill="x", pady=(12, 6))
        ttk.Label(outfrm, text="출력 폴더").pack(side="left")
        self.out_var = tk.StringVar(value=str(Path.home()/"Desktop"))
        ttk.Entry(outfrm, textvariable=self.out_var, width=60).pack(side="left", padx=8)
        ttk.Button(outfrm, text="찾기", command=self.pick_folder).pack(side="left")

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(12, 8))
        ttk.Button(btns, text="PD ZIP 생성", command=self.on_run).pack(side="left")
        ttk.Button(btns, text="입력 지우기", command=self.on_clear).pack(side="left", padx=8)

        self.lbl = ttk.Label(frm, text="", foreground="#222")
        self.lbl.pack(anchor="w", pady=(10, 0))

        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass

    def pick_folder(self):
        p = filedialog.askdirectory(title="출력 폴더 선택")
        if p:
            self.out_var.set(p)

    def on_clear(self):
        self.txt_a.delete("1.0","end")
        self.txt_k.delete("1.0","end")
        self.lbl.config(text="")

    def on_run(self):
        raw = self.txt_a.get("1.0","end").strip("\n")
        key = self.txt_k.get("1.0","end").strip("\n")
        rows = parse_pasted_rows(raw)
        if not rows:
            messagebox.showerror("오류","A행 복붙 입력이 비어 있습니다.")
            return

        if swe is None:
            messagebox.showerror("오류","pyswisseph(swisseph) 모듈이 없습니다. 빌드/설치를 확인해주세요.")
            return

        out_folder = Path(self.out_var.get()).expanduser()

        try:
            out = build_packet(rows[0], key, out_folder)
        except Exception as e:
            messagebox.showerror("생성 실패", str(e))
            return

        msg = f"생성 완료:\n{out}"
        self.lbl.config(text=msg)
        messagebox.showinfo("완료", msg)


def main():
    App().mainloop()

if __name__ == "__main__":
    main()
