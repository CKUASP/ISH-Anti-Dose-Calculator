import math
import base64
import os
import re
import pandas as pd
import streamlit as st

# ==========================================
# 0. 페이지 설정 (최상단)
# ==========================================
st.set_page_config(
    page_title="Anti Dose Calculator",
    page_icon="512.png",  # GitHub 저장소에 함께 올린 PNG 파일명
    layout="wide",
)


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
        "act_wt": weight,
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

    df = pd.read_excel(file_path)

    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.replace("^", "<br>", regex=False)

    return df


# ==========================================
# 3. Streamlit UI 레이아웃 구성
# ==========================================
def get_image_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    return ""


blue_img_b64 = get_image_base64("blue.png")
pink_img_b64 = get_image_base64("pink.png")

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

    /* 하이라이팅 CSS - 표 내 단일 지표 */
    .highlight-crcl { background-color: #90CAF9 !important; } /* 파랑 */
    .highlight-egfr { background-color: #A5D6A7 !important; } /* 초록 */
    .highlight-cysc { background-color: #CE93D8 !important; } /* 보라 */
    
    /* 하이라이팅 CSS - 2개 조합 */
    .highlight-crcl-egfr { 
        background: linear-gradient(135deg, #90CAF9 50%, #A5D6A7 50%) !important; 
    }
    .highlight-crcl-cysc { 
        background: linear-gradient(135deg, #90CAF9 50%, #CE93D8 50%) !important; 
    }
    .highlight-egfr-cysc { 
        background: linear-gradient(135deg, #A5D6A7 50%, #CE93D8 50%) !important; 
    }
    
    /* 하이라이팅 CSS - 3개 모두 중복 */
    .highlight-all { 
        background: linear-gradient(135deg, #90CAF9 33.3%, #A5D6A7 33.3% 66.6%, #CE93D8 66.6%) !important; 
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
        word-break: keep-all;
        white-space: normal;
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

    .title-box {
        background: #ffffff;
        padding: 16px 20px;
        border-radius: 28px;
        margin-bottom: 16px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.14);
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: center;
        gap: 12px;
    }

    .title-img {
        width: 90px;
        height: 90px;
        object-fit: contain;
    }

    .title-text {
        color: #0c4da2;
        font-size: 50px;
        font-weight: bold;
        text-align: center;
        margin: 0;
    }

    /* 📌 신기능 결과 뭉툭한 네모 박스(카드) 스타일 정의 */
    .metric-card {
        border-radius: 12px;
        padding: 10px 14px;
        margin-bottom: 4px;
        transition: all 0.3s ease;
        border: 1px solid #e9ecef;
        background-color: #f8f9fa;
    }
    
    .metric-card-label {
        font-size: 0.85rem;
        font-weight: bold;
        color: #495057;
        margin-bottom: 2px;
    }
    
    .metric-card-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #212529;
        line-height: 1.2;
    }

    .metric-card-sub {
        font-size: 0.72rem;
        color: #6c757d;
        margin-top: 2px;
    }

    /* CrCl 강조 박스 (파란색 계열) */
    .card-crcl-active {
        background-color: #e3f2fd !important;
        border: 2px solid #2196f3 !important;
        box-shadow: 0 4px 10px rgba(33, 150, 243, 0.18);
    }
    .card-crcl-active .metric-card-label {
        color: #0d47a1 !important;
    }
    .card-crcl-active .metric-card-value {
        color: #1565c0 !important;
    }

    /* eGFR 강조 박스 (초록색 계열) */
    .card-egfr-active {
        background-color: #e8f5e9 !important;
        border: 2px solid #4caf50 !important;
        box-shadow: 0 4px 10px rgba(76, 175, 80, 0.18);
    }
    .card-egfr-active .metric-card-label {
        color: #1b5e20 !important;
    }
    .card-egfr-active .metric-card-value {
        color: #2e7d32 !important;
    }

    /* Cystatin-C 강조 박스 (보라색 계열) */
    .card-cysc-active {
        background-color: #f3e5f5 !important;
        border: 2px solid #ab47bc !important;
        box-shadow: 0 4px 10px rgba(171, 71, 188, 0.18);
    }
    .card-cysc-active .metric-card-label {
        color: #4a148c !important;
    }
    .card-cysc-active .metric-card-value {
        color: #7b1fa2 !important;
    }

    /* 📌 CAPTION 텍스트 스타일 강화 (더 진하고 명확하게) */
    div[data-testid="stCaptionContainer"] {
        margin-top: 6px !important;
        margin-bottom: -12px !important;
        font-weight: 600 !important;   /* 👈 글자 굵기 (500~700 추천) */
        color: #31373d !important;     /* 👈 더 진한 회색/검은색 계열 */
    }

    /* caption 내부 p 태그 및 마크다운 강제 적용 */
    div[data-testid="stCaptionContainer"] p {
        font-weight: 600 !important;
        color: #31373d !important;
    }

    </style>
""",
    unsafe_allow_html=True,
)

title_html = f"""
<div class="title-box">
    <img src="{blue_img_b64}" class="title-img">
    <div class="title-text">
        Antibiotics Dose Calculator
    </div>
    <img src="{pink_img_b64}" class="title-img">
</div>
"""

st.markdown(title_html, unsafe_allow_html=True)

# 제목 박스 출력 후, st.markdown("---") 대신 아래 코드를 넣으세요.

# 이용 안내 박스 우측에 들어갈 로고 이미지 (blue.png 활용)
logo_img_b64 = get_image_base64("logo.png")

st.markdown(
    f"""
    <div style="
        background-color: #f0f7ff;
        border-left: 5px solid #0066cc;
        padding: 16px 20px;
        border-radius: 6px;
        margin-top: 10px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
    ">
        <!-- 왼쪽: 이용 안내 및 참고사항 내용 -->
        <div style="flex: 1;">
            <div style="font-weight: bold; color: #004085; font-size: 1.05rem; margin-bottom: 6px;">
                ℹ️ 이용 안내 및 참고사항
            </div>
            <div style="font-size: 0.88rem; color: #333333; line-height: 1.5;">
                • 신기능에 따른 용량 조절 시에는 <b>원칙적으로 CrCl</b>을 기준으로 하며 필요 시 eGFR을 참고할 수 있습니다.<br>
                • 권고 용량은 <b>본원 항생제 사용 지침서</b>를 기반으로 하며, 용량 결정 시에는 전반적인 임상 상황을 고려하시기 바랍니다.
            </div>
        </div>
        <!-- 오른쪽: 로고 이미지 및 ASP팀 문구 -->
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding-left: 16px;
            border-left: 1px solid #d0e2ff;
            min-width: 300px;
        ">
            <img src="{logo_img_b64}" style="width: 200px; height: 50px; object-fit: contain; margin-bottom: 4px;">
            <span style="font-size: 0.95rem; font-weight: bold; color: #59595b; white-space: nowrap;">ASP 전담팀</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

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

# --- [BMI 조건별 스타일 및 아이콘 설정] ---
    bmi_val = res['bmi']
    if bmi_val < 18.5:
        bmi_label = "BMI <span style='color: #4277bf; font-size: 1.2em;'>▼</span>"
        bmi_color = "#4277bf"  # 파스텔 블루
    elif bmi_val > 25:
        bmi_label = "BMI <span style='color: #e66f61; font-size: 1.2em;'>▲</span>"
        bmi_color = "#e66f61"  # 파스텔 레드
    else:
        bmi_label = "BMI"
        bmi_color = "#212529"  # 기본 다크 그레이

    st.write("")
    st.markdown(
        f"""
        <div style="
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 12px 16px;
            display: flex;
            justify-content: space-around;
            align-items: center;
            text-align: center;
            font-size: 1.2rem;
            margin-bottom: 28px;
        ">
            <div><span style="color: #6c757d; font-weight: 600;">IBW</span><br><b style="font-size: 1.1rem; color: #212529;">{res['ibw']:.1f}</b> <small style="color: #6c757d;">kg</small></div>
            <div style="border-left: 1px solid #dee2e6; height: 28px;"></div>
            <div><span style="color: #6c757d; font-weight: 600;">AdjBW</span><br><b style="font-size: 1.1rem; color: #212529;">{res['adjbw']:.1f}</b> <small style="color: #6c757d;">kg</small></div>
            <div style="border-left: 1px solid #dee2e6; height: 28px;"></div>
            <div><span style="color: #6c757d; font-weight: 600;">{bmi_label}</span><br><b style="font-size: 1.1rem; color: {bmi_color};">{bmi_val:.1f}</b> <small style="color: #6c757d;">kg/m²</small></div>
            <div style="border-left: 1px solid #dee2e6; height: 28px;"></div>
            <div><span style="color: #6c757d; font-weight: 600;">BSA</span><br><b style="font-size: 1.1rem; color: #212529;">{res['bsa']:.2f}</b> <small style="color: #6c757d;">m²</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# 📌 [수정] 뭉툭한 네모 박스 형태(카드)로 제목과 수치를 시각화하는 함수
def render_metric_card(label, value, help_text, is_selected=False, card_type="crcl"):
    card_class = "metric-card"
    if is_selected:
        card_class += f" card-{card_type}-active"

    html = f"""
    <div class="{card_class}" title="{help_text}">
        <div class="metric-card-label">{label}</div>
        <div class="metric-card-value">{value}</div>
        <div class="metric-card-sub">{help_text}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


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

    st.markdown("##### 🔵 CrCl (Creatinine Clearance)")

    c1, c3, c2 = st.columns(3)
    with c1:
        render_metric_card(
            label="🔵 ABW CrCl" if rec == "ABW" else "ABW CrCl",
            value=f"{res['crcl_abw']:.2f}",
            help_text="Actual Body Weight 기준",
            is_selected=(rec == "ABW"),
            card_type="crcl",
        )
    with c3:
        render_metric_card(
            label="🔵 IBW CrCl" if rec == "IBW" else "IBW CrCl",
            value=f"{res['crcl_ibw']:.2f}",
            help_text="Ideal Body Weight 기준",
            is_selected=(rec == "IBW"),
            card_type="crcl",
        )
    with c2:
        render_metric_card(
            label="🔵 AdjBW CrCl" if rec == "AdjBW" else "AdjBW CrCl",
            value=f"{res['crcl_adjbw']:.2f}",
            help_text="Adjusted Body Weight 기준 <br>",
            is_selected=(rec == "AdjBW"),
            card_type="crcl",
        )
    st.markdown("---")

    st.markdown("##### 🟢 CKD-EPI eGFR")
    k3, k2, k1 = st.columns(3)
    with k3:
        # 약물 용량 결정의 주요 기준이 되는 BSA 기반 항목 네모 박스 하이라이트
        render_metric_card(
            label="🟢 BSA 기반 CKD-EPI",
            value=f"{res['ckd_21_bsa']:.2f}",
            help_text="mL/min (용량 결정 기준)",
            is_selected=True,
            card_type="egfr",
        )
    with k2:
        render_metric_card(
            label="CKD-EPI eGFR(2021)",
            value=f"{res['ckd_21']:.2f}",
            help_text="mL/min/1.73m² (신기능)",
            is_selected=False,
            card_type="egfr",
        )
    with k1:
        render_metric_card(
            label="CKD-EPI eGFR(2009)",
            value=f"{res['ckd_09']:.2f}",
            help_text="mL/min/1.73m² (본원 결과)",
            is_selected=False,
            card_type="egfr",
        )

    st.markdown("---")

    if use_cysc == "Y":
        
        st.markdown("##### 🟣 Cystatin-C eGFR")
        cy2, cy1, cy3 = st.columns(3)
        with cy2:
            render_metric_card(
                label="🟣 BSA 기반 Cystatin-C",
                value=f"{res['ckd_cys_bsa']:.2f}",
                help_text="mL/min (용량 결정 기준)",
                is_selected=True,
                card_type="cysc",
            )
        with cy1:
            render_metric_card(
                label="Cystatin-C eGFR",
                value=f"{res['ckd_cys']:.2f}",
                help_text="mL/min/1.73m² (본원 결과)",
                is_selected=False,
                card_type="cysc",
            )

st.markdown("---")


def parse_and_calculate_dose(dose_str, weight_kg):
    if not isinstance(dose_str, str) or "mg/kg" not in dose_str.lower():
        return dose_str

    pattern = r"(\d+(?:\.\d+)?(?:\s*[\~\-]\s*\d+(?:\.\d+)?)?)\s*mg/kg"

    def replace_match(match):
        num_part = match.group(1).strip()

        if "~" in num_part or "-" in num_part:
            sep = "~" if "~" in num_part else "-"
            parts = num_part.split(sep)
            try:
                low_val = float(parts[0].strip()) * weight_kg
                high_val = float(parts[1].strip()) * weight_kg
                return f"{round(low_val, 1):,g}~{round(high_val, 1):,g}mg"
            except ValueError:
                return match.group(0)

        else:
            try:
                val = float(num_part) * weight_kg
                return f"{round(val, 1):,g}mg"
            except ValueError:
                return match.group(0)

    return re.sub(pattern, replace_match, dose_str, flags=re.IGNORECASE)


# ==========================================
# 4. 항생제 용량 선택 및 표 출력
# ==========================================
st.subheader("💉 항생제 용량 선택")

df_dosage = load_dosage_data()

if (
    not df_dosage.empty
    and "성분명" in df_dosage.columns
    and "표기 명칭" in df_dosage.columns
):
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
        f"※ 체중 당 용량이 권고되는 항생제는 입력된 **실제 체중({patient_weight:.1f} kg)** 기준으로 계산되어 표시됩니다. (셀 마우스 오버 시 원본 단위 확인 가능)"
    )

else:
    st.error(
        "엑셀 파일이 존재하지 않거나 '성분명'과 '표기 명칭' 컬럼이 올바르게 포함되어 있지 않습니다."
    )