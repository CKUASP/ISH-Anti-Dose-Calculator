import streamlit as st

st.set_page_config(
    page_title="Anti Dose Calculator",
    page_icon="512.png",  # GitHub 저장소에 함께 올린 PNG 파일명
    layout="wide"
)

import math
import os
import re
import pandas as pd

# ==========================================
# 1. 신기능 및 체중별 metrics 계산 함수
# ==========================================
def calculate_metrics(age, gender, height, weight, scr, cysc=0.8, use_cysc="N"):
    is_male = gender == "M"

    # --- [체중 관련 계산] ---
    bsa = math.sqrt((height * weight) / 3600)

    height_inch = height / 2.54
    base_ibw = 50.0 if is_male else 45.5
    ibw = base_ibw + 2.3 * (height_inch - 60)

    adjbw = ibw + 0.4 * (weight - ibw)
    bmi = weight / ((height / 100) ** 2)
    weight_ratio = (weight / ibw) * 100

    # --- [Cockcroft-Gault CrCl 계산] ---
    crcl_abw = ((140 - age) * weight) / (72 * scr)
    if not is_male:
        crcl_abw *= 0.85

    crcl_ibw = ((140 - age) * ibw) / (72 * scr)
    if not is_male:
        crcl_ibw *= 0.85

    crcl_adjbw = ((140 - age) * adjbw) / (72 * scr)
    if not is_male:
        crcl_adjbw *= 0.85

    # --- [CKD-EPI Scr (2009 & 2021) 계산] ---
    kappa_09 = 0.9 if is_male else 0.7
    alpha_09 = -0.411 if is_male else -0.329
    min_scr_09 = min(scr / kappa_09, 1.0)
    max_scr_09 = max(scr / kappa_09, 1.0)
    gender_factor_09 = 1.0 if is_male else 1.018

    ckd_epi_2009 = (
        141
        * (min_scr_09**alpha_09)
        * (max_scr_09**-1.209)
        * (0.993**age)
        * gender_factor_09
    )

    kappa_21 = 0.9 if is_male else 0.7
    alpha_21 = -0.302 if is_male else -0.241
    min_scr_21 = min(scr / kappa_21, 1.0)
    max_scr_21 = max(scr / kappa_21, 1.0)
    gender_factor_21 = 1.0 if is_male else 1.012

    ckd_epi_2021 = (
        142
        * (min_scr_21**alpha_21)
        * (max_scr_21**-1.200)
        * (0.9938**age)
        * gender_factor_21
    )

    ckd_epi_2021_bsa = ckd_epi_2021 * (bsa / 1.73)

    # --- [CKD-EPI Cystatin C 2021 계산] ---
    ckd_epi_cys = 0.0
    ckd_epi_cys_bsa = 0.0
    if use_cysc == "Y" and cysc > 0:
        cys_alpha = -0.323 if is_male else -0.499
        cys_gender_factor = 1.000 if is_male else 0.932

        # 📌 [수정] Cystatin C Cutoff (0.8 mg/L) 연산 수정
        min_cysc = min(cysc / 0.8, 1.0)
        max_cysc = max(cysc / 0.8, 1.0)

        ckd_epi_cys = (
            133
            * (min_cysc**cys_alpha)
            * (max_cysc**-1.328)
            * (0.996**age)
            * cys_gender_factor
        )
        ckd_epi_cys_bsa = ckd_epi_cys * (bsa / 1.73)

    # 체중별 권장 CrCl 설정
    if bmi > 25:
        recommended_crcl = "AdjBW"
        rec_crcl_val = crcl_adjbw
    elif bmi < 18.5:
        recommended_crcl = "ABW"
        rec_crcl_val = crcl_abw
    else:
        recommended_crcl = "IBW"
        rec_crcl_val = crcl_ibw

    results = {
        "act_wt": weight,  # 📌 [추가] 용량 계산용 환자 체중
        "bsa": bsa,
        "bmi": bmi,
        "ibw": ibw,
        "adjbw": adjbw,
        "weight_ratio": weight_ratio,
        "crcl_abw": crcl_abw,
        "crcl_ibw": crcl_ibw,
        "crcl_adjbw": crcl_adjbw,
        "ckd_09": ckd_epi_2009,
        "ckd_21": ckd_epi_2021,
        "ckd_21_bsa": ckd_epi_2021_bsa,
        "ckd_cys": ckd_epi_cys,
        "ckd_cys_bsa": ckd_epi_cys_bsa,
        "recommended_crcl": recommended_crcl,
        "rec_crcl_val": rec_crcl_val,
    }
    return results


# ==========================================
# 2. 엑셀 데이터 로드 함수
# ==========================================
@st.cache_data
def load_dosage_data():
    file_path = "용량.xlsx"
    
    if not os.path.exists(file_path):
        return pd.DataFrame()

    # 1. 파일 읽기
    df = pd.read_excel(file_path)

    # 2. 모든 문자열(object) 컬럼의 '^' 기호를 HTML 줄바꿈 '<br>'로 변환
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.replace("^", "<br>", regex=False)

    # 3. 변환이 끝난 후 최종 반환
    return df

# ==========================================
# 3. Streamlit UI 레이아웃 구성
# ==========================================
st.set_page_config(page_title="Anti Dose Calculator", layout="wide")

st.markdown(
    """
    <style>
    /* number_input의 + / - 증감 버튼 숨기기 */
    button[data-testid="stNumberInputStepDown"],
    button[data-testid="stNumberInputStepUp"] {
        display: none !important;
    }

    /* 단위 텍스트 높이 맞춤 */
    .unit-label {
        font-size: 0.95rem;
        font-weight: 500;
        color: #495057;
        padding-top: 8px;
    }

    /* 우측 컬럼 세로/가로 간격 줄이기 */
    div[data-testid="stMetric"] {
        padding: 4px 8px !important;
    }

    div[data-testid="stMetricLabel"] {
        margin-bottom: 0px !important;
    }

    div[data-testid="stMarkdownContainer"] > hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }

    div[data-testid="stMarkdownContainer"] > h3,
    div[data-testid="stMarkdownContainer"] > h5 {
        margin-top: 0.2rem !important;
        margin-bottom: 0.2rem !important;
    }

    div[data-testid="stCaptionContainer"] {
        margin-top: 6px !important;
        margin-bottom: -12px !important;
    }

    /* 하이라이팅 CSS - 단일 지표 */
    .highlight-crcl { background-color: #90CAF9 !important; } /* 파랑 */
    .highlight-egfr { background-color: #A5D6A7 !important; } /* 초록 */
    .highlight-cysc { background-color: #CE93D8 !important; } /* 보라 */
    
    /* 하이라이팅 CSS - 2개 조합 */
    .highlight-crcl-egfr { 
        background: linear-gradient(to right, #90CAF9 50%, #A5D6A7 50%) !important; 
    }
    .highlight-crcl-cysc { 
        background: linear-gradient(to right, #90CAF9 50%, #CE93D8 50%) !important; 
    }
    .highlight-egfr-cysc { 
        background: linear-gradient(to right, #A5D6A7 50%, #CE93D8 50%) !important; 
    }
    
    /* 하이라이팅 CSS - 3개 모두 중복 */
    .highlight-all { 
        background: linear-gradient(to right, #90CAF9 33.3%, #A5D6A7 33.3% 66.6%, #CE93D8 66.6%) !important; 
    }
    
    .dosage-table {
        width: 100%;
        table-layout: fixed;
        border-collapse: collapse;
        margin-top: 10px;
    }

    .dosage-table th, .dosage-table td {
        border: 1px solid #ddd;
        padding: 8px;
        word-break: keep-all;   /* 👈 핵심: 단어 단위 줄바꿈 적용 */
        white-space: normal;  /* 👈 띄어쓰기 기준 자연스러운 줄바꿈 */
        text-align: center;
        font-weight: bold;
    }
    .dosage-table th {
        background-color: #f8f9fa;
        font-weight: bold;
    }
    .header-col {
        font-weight: bold;
        background-color: #f1f3f5;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("💊 Anti Dose Calculator")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 환자 정보 입력")

    left_sub, right_sub = st.columns(2)

    with left_sub:
        st.write("**나이**")
        s_col1, s_col2 = st.columns([3, 1])
        with s_col1:
            age = st.number_input(
                "나이",
                min_value=20,
                max_value=120,
                value=65,
                label_visibility="collapsed",
                placeholder="예: 65",
            )
        with s_col2:
            st.markdown(
                "<div class='unit-label'>세</div>", unsafe_allow_html=True
            )

        st.write("**성별**")
        gender = st.radio(
            "성별",
            options=["M", "F"],
            index=0,
            horizontal=True,
            key="gender_radio",
            label_visibility="collapsed",
        )

        st.write("**투석 여부**")
        dialysis = st.radio(
            "투석 여부",
            options=["해당 없음", "IHD", "CRRT"],
            index=0,
            horizontal=True,
            key="dialysis_radio",
            label_visibility="collapsed",
        )

        st.markdown("---")

        st.write("**Cystatin-C 검사 여부**")
        use_cysc = st.radio(
            "Cystatin-C 검사 여부",
            options=["N", "Y"],
            index=0,
            horizontal=True,
            key="use_cysc_radio",
            label_visibility="collapsed",
        )

    with right_sub:
        st.write("**키**")
        h_col1, h_col2 = st.columns([3, 1])
        with h_col1:
            height = st.number_input(
                "키",
                min_value=30.0,
                max_value=250.0,
                value=170.0,
                label_visibility="collapsed",
                placeholder="예: 170.0",
            )
        with h_col2:
            st.markdown(
                "<div class='unit-label'>cm</div>", unsafe_allow_html=True
            )

        st.write("**체중**")
        w_col1, w_col2 = st.columns([3, 1])
        with w_col1:
            weight = st.number_input(
                "체중",
                min_value=10.0,
                max_value=300.0,
                value=60.0,
                label_visibility="collapsed",
                placeholder="예: 60.0",
            )
        with w_col2:
            st.markdown(
                "<div class='unit-label'>kg</div>", unsafe_allow_html=True
            )

        st.write("**혈청 크레아티닌 (SCr)**")
        s_col1, s_col2 = st.columns([3, 1])
        with s_col1:
            scr = st.number_input(
                "SCr",
                min_value=0.1,
                max_value=20.0,
                value=0.8,
                format="%.2f",
                label_visibility="collapsed",
                placeholder="예: 0.80",
            )
        with s_col2:
            st.markdown(
                "<div class='unit-label'>mg/dL</div>", unsafe_allow_html=True
            )

        st.markdown("---")

        st.write("**Cystatin-C**")
        c_col1, c_col2 = st.columns([3, 1])
        with c_col1:
            cystatin_c = st.number_input(
                "Cystatin-C",
                min_value=0.1,
                max_value=20.0,
                value=0.8,
                format="%.2f",
                disabled=(use_cysc == "N"),
                label_visibility="collapsed",
                placeholder="예: 0.80",
            )
        with c_col2:
            st.markdown(
                "<div class='unit-label'>mg/L</div>", unsafe_allow_html=True
            )

    res = calculate_metrics(
        age, gender, height, weight, scr, cystatin_c, use_cysc
    )

    st.write("")
    st.markdown(
        f"**IBW:** `{res['ibw']:.1f} kg` | "
        f"**AdjBW:** `{res['adjbw']:.1f} kg` | "
        f"**BMI:** `{res['bmi']:.1f} kg/m²` | "
        f"**BSA:** `{res['bsa']:.2f} m²`"
    )


with col2:
    st.subheader("📊 신기능 평가 결과")

    rec = res["recommended_crcl"]
    if rec == "AdjBW":
        st.caption(
            f"💡 **BMI {res['bmi']:.1f} (과체중):** **AdjBW CrCl** 사용이 권장됩니다."
        )
    elif rec == "ABW":
        st.caption(
            f"💡 **BMI {res['bmi']:.1f} (저체중):** **ABW(실제체중) CrCl** 사용이 권장됩니다."
        )
    else:
        st.caption(
            f"💡 **BMI {res['bmi']:.1f} (정상체중):** **IBW CrCl** 사용이 권장됩니다."
        )

    st.markdown("---")

    st.markdown("##### 🔵 Cockcroft-Gault CrCl (체중별)")

    abw_label = (
        "**ABW CrCl (실제체중)** 💡"
        if rec == "ABW"
        else "ABW CrCl (실제체중)"
    )
    adjbw_label = (
        "**AdjBW CrCl (보정체중)** 💡"
        if rec == "AdjBW"
        else "AdjBW CrCl (보정체중)"
    )
    ibw_label = (
        "**IBW CrCl (이상체중)** 💡"
        if rec == "IBW"
        else "IBW CrCl (이상체중)"
    )

    c1, c3, c2 = st.columns(3)
    c1.metric(
        label=abw_label,
        value=f"{res['crcl_abw']:.2f}",
        help="Actual Body Weight 기준",
    )
    c2.metric(
        label=adjbw_label,
        value=f"{res['crcl_adjbw']:.2f}",
        help="Adjusted Body Weight 기준 (과체중 환자 권장)",
    )
    c3.metric(
        label=ibw_label,
        value=f"{res['crcl_ibw']:.2f}",
        help="Ideal Body Weight 기준",
    )

    st.markdown("---")

    st.markdown("##### 🟢 CKD-EPI eGFR")
    k3, k2, k1 = st.columns(3)
    k1.metric(
        label="CKD-EPI (2009)",
        value=f"{res['ckd_09']:.2f}",
        help="mL/min/1.73m² (본원 검사 결과)",
    )
    k2.metric(
        label="CKD-EPI (2021)",
        value=f"{res['ckd_21']:.2f}",
        help="mL/min/1.73m² (환자 신기능 평가 기준)",
    )
    k3.metric(
        label="**BSA 기반 CKD-EPI (2021)**",
        value=f"{res['ckd_21_bsa']:.2f}",
        help="mL/min (환자 BSA 반영한 약물 용량 결정 기준)",
    )

    if use_cysc == "Y":
        st.markdown("---")
        st.markdown("##### 🟣 Cystatin-C eGFR")
        cy2, cy1, cy3 = st.columns(3)
        cy1.metric(
            label="Cystatin-C eGFR",
            value=f"{res['ckd_cys']:.2f}",
            help="mL/min/1.73m² (본원 검사 결과)",
        )
        cy2.metric(
            label="**BSA 기반 Cys-C eGFR**",
            value=f"{res['ckd_cys_bsa']:.2f}",
            help="mL/min (환자 BSA 반영한 약물 용량 결정 기준)",
        )

st.markdown("---")


def parse_and_calculate_dose(dose_str, weight_kg):
    """문자열 내에서 mg/kg 바로 앞에 붙은 숫자(범위 포함)만 추출하여 체중 기반 용량으로 변환합니다.

    셀 내에 여러 개의 mg/kg 패턴이 있어도 모두 변환하며, 앞뒤 텍스트(Load, qHD 등)는 유지합니다.
    """
    if not isinstance(dose_str, str) or "mg/kg" not in dose_str.lower():
        return dose_str

    # mg/kg 바로 앞의 숫자나 범위만 정확하게 매칭 (예: "25", "25.5", "25~30", "25-30")
    pattern = r"(\d+(?:\.\d+)?(?:\s*[\~\-]\s*\d+(?:\.\d+)?)?)\s*mg/kg"

    def replace_match(match):
        num_part = match.group(1).strip()

        # 1. 범위 용량 처리 (예: 25~30mg/kg)
        if "~" in num_part or "-" in num_part:
            sep = "~" if "~" in num_part else "-"
            parts = num_part.split(sep)
            try:
                low_val = float(parts[0].strip()) * weight_kg
                high_val = float(parts[1].strip()) * weight_kg
                return f"{round(low_val, 1):,g}~{round(high_val, 1):,g}mg"
            except ValueError:
                return match.group(0)

        # 2. 단일 용량 처리 (예: 25mg/kg)
        else:
            try:
                val = float(num_part) * weight_kg
                return f"{round(val, 1):,g}mg"
            except ValueError:
                return match.group(0)

    # dose_str 내의 모든 mg/kg 패턴을 검색하여 계산 결과로 치환
    return re.sub(pattern, replace_match, dose_str, flags=re.IGNORECASE)


# ==========================================
# 4. 항생제 용량 선택 및 표 출력
# ==========================================
st.subheader("💉 항생제 용량 선택")

df_dosage = load_dosage_data()

if not df_dosage.empty and "성분명" in df_dosage.columns and "표기 명칭" in df_dosage.columns:
    display_names = sorted(df_dosage["표기 명칭"].dropna().unique())
    selected_display_name = st.selectbox(
        "항생제 성분명을 검색하거나 선택하세요", display_names
    )

    drug_df = df_dosage[df_dosage["표기 명칭"] == selected_display_name]
    ingredient_name = drug_df["성분명"].iloc[0]

    act_wt = res.get("act_wt", weight)
    adj_wt = res.get("adjbw", weight)
    bmi_val = res.get("bmi", 0)
    wt_ratio = res.get("weight_ratio", 0)

    target_drugs = ["amikacin", "gentamicin"]
    is_target_aminoglycoside = any(
        td in ingredient_name.lower() or td in selected_display_name.lower()
        for td in target_drugs
    )

    # 비만 조건: (ABW/IBW > 120%) OR (BMI >= 30)
    is_obese = (wt_ratio > 120) or (bmi_val >= 30)

    if is_target_aminoglycoside and is_obese:
        patient_weight = adj_wt
        wt_calc_label = "AdjBW (보정체중)"
    else:
        patient_weight = act_wt
        wt_calc_label = "Actual BW (실제체중)"


    def is_in_range(val, min_val, max_val, current_dialysis, cell_label):
        if current_dialysis != "해당 없음":
            return current_dialysis == cell_label
        if min_val >= 0:
            if max_val >= 999:
                return val >= min_val
            return min_val <= val <= max_val
        return False

    crcl_val = res["rec_crcl_val"]

    # Ertapenem일 때 BSA 미반영 값 적용 분기
    if (
        "ertapenem" in ingredient_name.lower()
        or "ertapenem" in selected_display_name.lower()
    ):
        egfr_val = res["ckd_21"]
        cysc_val = res["ckd_cys"]
    else:
        egfr_val = res["ckd_21_bsa"]
        cysc_val = res["ckd_cys_bsa"]

    header_html = "<tr><th>성분명</th>"
    dosage_html = f"<tr><td class='header-col'>{ingredient_name}</td>"

    for _, row in drug_df.iterrows():
        range_label = str(row["신기능구간명"])
        raw_dose_text = row["추천용량"]

        dose_text = parse_and_calculate_dose(raw_dose_text, patient_weight)

        min_c = float(row["최소CrCl"])
        max_c = float(row["최대CrCl"])

        match_crcl = is_in_range(
            crcl_val, min_c, max_c, dialysis, range_label
        )
        match_egfr = is_in_range(
            egfr_val, min_c, max_c, dialysis, range_label
        )
        match_cysc = (
            is_in_range(cysc_val, min_c, max_c, dialysis, range_label)
            if use_cysc == "Y"
            else False
        )

        cell_class = ""

        if match_crcl and match_egfr and match_cysc:
            cell_class = "highlight-all"
        elif match_crcl and match_egfr:
            cell_class = "highlight-crcl-egfr"
        elif match_crcl and match_cysc:
            cell_class = "highlight-crcl-cysc"
        elif match_egfr and match_cysc:
            cell_class = "highlight-egfr-cysc"
        elif match_crcl:
            cell_class = "highlight-crcl"
        elif match_egfr:
            cell_class = "highlight-egfr"
        elif match_cysc:
            cell_class = "highlight-cysc"

        header_html += f"<th>{range_label}</th>"
        dosage_html += f"<td class='{cell_class}' title='원본 용량: {raw_dose_text}'>{dose_text}</td>"

    header_html += "</tr>"
    dosage_html += "</tr>"

    table_html = f"""
    <table class='dosage-table'>
        <thead>{header_html}</thead>
        <tbody>{dosage_html}</tbody>
    </table>
    """

    st.markdown(table_html, unsafe_allow_html=True)
    st.write("")

    if use_cysc == "Y":
        st.markdown(
            "<span style='color: #1E88E5;'>🔵</span> **CrCl**: BMI를 고려한 조정 체중 기반 CrCl 기준 용량 | "
            "<span style='color: #43A047;'>🟢</span> **eGFR**: BSA를 고려한 CKD-EPI eGFR 기준 용량 | "
            "<span style='color: #AB47BC;'>🟣</span> **Cys-C**: BSA를 고려한 Cystatin-C eGFR 기준 용량 ",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span style='color: #1E88E5;'>🔵</span> **CrCl 기준**: BMI를 고려한 조정 체중 기반 CrCl 기준 용량 | "
            "<span style='color: #43A047;'>🟢</span> **eGFR 기준**: BSA를 고려한 CKD-EPI eGFR 기준 용량 ",
            unsafe_allow_html=True,
        )


    # CRAB 관련 경고 문구
    crab_keywords = ["CRAB"]
    if any(
        keyword.lower() in ingredient_name.lower()
        or keyword.lower() in selected_display_name.lower()
        for keyword in crab_keywords
    ):
        st.markdown("---")
        st.warning(
            "⚠️ **[CRAB 감염 용량 설정]**\n\n"
            "* **CRAB 감염:** CRAB(카바페넴 내성 Acinetobacter baumannii) 감염 치료 시 권고되는 **High dose Sulbactam** 요법입니다.\n"
            "* 임상의의 판단에 따라 **CrCl 30~90mL/min**의 환자에서 용량을 줄이지 않고 정상 신기능 용량인 **9g q8h(Sulbactam 기준 3g q8h)** 투여를 고려할 수 있습니다."
        )

    vanco_keywords = ["Vancomycin"]
    if any(
        keyword.lower() in ingredient_name.lower()
        or keyword.lower() in selected_display_name.lower()
        for keyword in vanco_keywords
    ):
        st.markdown("---")
        st.warning(
            "⚠️ **[Vancomycin 용량 설정]**\n\n"
            "* **Vancomycin:** IV Vancomycin의 용량은 TDM을 통해 설정하는 것이 권고됩니다.\n"
            "* 1일 총 용량이 3G을 초과하는 경우 AKI risk가 있으므로 감염내과 협진 통하여 용량을 조절하시기 바랍니다."
        )

    amino_keywords = ["Amikacin", "Gentamicin"]
    if any(
        keyword.lower() in ingredient_name.lower()
        or keyword.lower() in selected_display_name.lower()
        for keyword in amino_keywords
    ):
        st.markdown("---")
        st.warning(
            "⚠️ **[Amikacin/Gentamicin 용량 설정]**\n\n"
            "* 비만 환자에서 Aminoglycoside의 용량 계산은 권고사항에 따라 **조정 체중(AdjBW)**으로 계산되었습니다.\n"
        )

    st.caption(
        f"※ `mg/kg` 단위가 포함된 항생제는 입력된 환자 체중({patient_weight:.1f} kg) 기준으로 계산되어 표시됩니다. (셀 마우스 오버 시 원본 단위 확인 가능) "
    )


else:
    st.error(
        "엑셀 파일이 존재하지 않거나 '성분명'과 '표기 명칭' 컬럼이 올바르게 포함되어 있지 않습니다."
    )