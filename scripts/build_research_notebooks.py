"""연구용 Jupyter Notebook 다섯 개를 재현 가능하게 구성한다."""

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"


def md(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip())


def code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip())


def write(name: str, cells: list):
    notebook = nbf.v4.new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.13"},
        },
    )
    nbf.write(notebook, NOTEBOOKS / name)


common_setup = r'''
# 프로젝트 루트를 찾아 상대경로와 로컬 모듈 import를 일관되게 사용한다.
from pathlib import Path
import sys

def find_project_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / "src").is_dir() and (candidate / "notebooks").is_dir():
            return candidate
    raise RuntimeError("프로젝트 루트를 찾을 수 없습니다. 저장소 안에서 노트북을 실행하세요.")

PROJECT_ROOT = find_project_root(Path.cwd())
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SEED = 20260826
PROJECT_ROOT
'''


write("01_distribution_design.ipynb", [
    md(r'''
    # 01. 합성 시뮬레이션 분포 설계

    이 노트북은 다품종 조달 5PL 합성 인스턴스의 변수, 생성규칙, 보정 근거를 명시한다.
    ComprasNet은 **입력분포와 공급자–품목 구조를 보정하는 자료**로만 사용한다. WTP, WTA,
    실제 공급용량, 배송비, 인센티브 반응계수와 All-or-Nothing 여부는 관측되지 않으므로
    시나리오 또는 문헌·가정으로 분리한다. 여기서는 원본 대용량 CSV를 읽지 않는다.
    '''),
    code(common_setup),
    code(r'''
    # 설계변수와 생성규칙, 근거 유형을 한 표에 정리한다.
    import pandas as pd

    design_rows = [
        ("num_buyers", "초기 구매자 수", "고정 또는 규모 시나리오(30/50/100); smoke는 8", "민감도 분석"),
        ("num_sellers", "초기 공급자 수", "고정 또는 규모 시나리오(20/30/50); smoke는 10", "민감도 분석"),
        ("num_skus", "분석 품목군 수", "보정 대상 품목군을 선정한 뒤 고정; smoke는 5", "민감도 분석"),
        ("buyer_sku_count", "구매자별 주문 품목 수", "조달 건별 임시 품목군 수의 경험분포 또는 범주분포", "ComprasNet 보정"),
        ("buyer_sku_set", "구매자 주문 품목 조합", "품목 빈도·동시출현 가중 비복원 추출; 묶음은 AON 증거가 아님", "ComprasNet 보정"),
        ("min_qty", "주문 성립 최소수량", "max_qty의 비율 alpha; alpha는 실험수준으로 둠", "문헌·가정"),
        ("max_qty", "품목별 최대 주문수량", "동질 품목군의 양수 수량 경험분포/후보분포", "ComprasNet 보정"),
        ("seller_sku_set", "공급자별 취급 품목", "관측 참여 이분 네트워크를 재표본화; 최소 1품목 보정", "ComprasNet 보정"),
        ("seller_coverage", "공급자 품목 커버리지", "공급자별 고유 임시 품목군 수 또는 Low/Medium/High", "ComprasNet 보정"),
        ("capacity", "공급 가능 수량", "Gamma 원시값 후 품목별 목표 공급/수요비로 스케일링", "문헌·가정"),
        ("wtp", "구매자 단위 WTP", "기준가격 × (1 + 구매자 프리미엄); 관측값으로 해석 금지", "문헌·가정"),
        ("wta", "공급자 단위 WTA", "기준가격 × (1 + 공급자 가격편차); 낙찰단가와 동일하지 않음", "문헌·가정"),
        ("reference_price", "품목군 기준가격", "동질 상품 품목군의 양수 단가 중앙값/절사평균", "ComprasNet 보정"),
        ("delivery_cost", "허브→구매자 배송비", "지역 Near/Medium/Far 고정비; 자료에서 관측 불가", "문헌·가정"),
        ("region", "구매자·공급자 지역", "관측 UF 빈도 또는 통제된 지역 시나리오", "ComprasNet 보정"),
        ("supply_ratio", "최대수요 대비 공급량", "부족 0.7 / 균형 1.0 / 풍부 1.3", "민감도 분석"),
        ("price_dispersion", "공급자 가격분산", "기준가격 대비 ±5% / ±10% / ±20%", "민감도 분석"),
        ("initial_history", "초기 참여·낙찰이력", "관측 과거 참여/낙찰 횟수의 정규화값 또는 Beta 초기값", "ComprasNet 보정"),
        ("retention_parameter", "재참여·인센티브 반응계수", "모형 파라미터로 두고 범위별 민감도 분석", "민감도 분석"),
        ("all_or_nothing", "주문 전체 수락 조건", "데이터에서 추론하지 않고 실험 처리로 명시", "문헌·가정"),
        ("seed", "실험 난수 시드", "설정 파일에 고정하고 모든 난수생성기에 전달", "민감도 분석"),
    ]
    design = pd.DataFrame(design_rows, columns=["변수", "변수 의미", "설정 또는 생성 방법", "근거 유형"])
    design
    '''),
    md(r'''
    ## 생성 순서와 구조 보정

    1. 기간별 구매자 주문은 외생적으로 생성한다.
    2. 구매자별 품목 수와 품목 조합을 뽑고 `min_qty ≤ max_qty`가 되게 수량을 생성한다.
    3. 공급자–품목 연결을 생성한 뒤 모든 공급자가 한 품목 이상, 모든 품목이 한 공급자 이상을 갖도록 보정한다.
    4. 공급 원시값을 만든 후 품목별 총공급/총최대수요가 시나리오 비율에 맞도록 스케일링한다.
    5. 기준가격 주변에서 WTP/WTA를 별도로 만들고 지역별 배송비와 초기 이력을 부여한다.

    `Código Item Compra`는 개별 조달 품목 행 ID이며 SKU가 아니다. 정규화된 설명도 탐색적
    **임시 품목군**일 뿐 동일 SKU 확정값이 아니다. 같은 조달 건의 동시출현 역시
    All-or-Nothing 주문의 증거가 아니다.
    '''),
    code(r'''
    # smoke 설정을 읽어 설계표의 현재 구현값을 확인한다.
    from src.config import load_config
    config = load_config("configs/smoke.json")
    pd.Series(config, name="smoke 설정")
    '''),
    md(r'''
    ## 시나리오 그리드와 아직 고정하지 않는 값

    기본 실험은 공급 부족·균형·풍부와 가격분산 Low·Medium·High의 교차설계를 사용한다.
    WTP/WTA 프리미엄, 공급용량, 배송비, 잔존함수 계수, AON 여부는 ComprasNet의 직접 관측값으로
    채우지 않는다. 05 노트북에서 반복거래와 공급자 수가 충분한 상품 품목군 후보를 찾은 뒤
    기간과 품목군을 확정해야 수량·단가 후보분포를 보정할 수 있다.
    '''),
])


write("03_comprasnet_raw_check.ipynb", [
    md(r'''
    # 03. ComprasNet 원본 구조·품질 진단

    세 원본 CSV를 수정하지 않고 구조와 품질만 점검한다. `Participantes.csv`는 약 2GB이므로
    표본과 청크를 사용한다. 이 노트북은 processed 파일을 만들지 않으며, 표본 기반 결과에는
    반드시 그 범위를 표시한다.
    '''),
    code(common_setup),
    code(r'''
    # 원본 경로와 읽기 규칙을 고정하고 누락 파일은 임의 데이터 없이 중단한다.
    import csv
    import os
    import pandas as pd
    import numpy as np
    from IPython.display import display

    RAW_DIR = PROJECT_ROOT / "data" / "raw" / "comprasnet"
    RAW_PATHS = {
        "auctions": RAW_DIR / "Licitações.csv",
        "items": RAW_DIR / "Itens.csv",
        "participants": RAW_DIR / "Participantes.csv",
    }
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in RAW_PATHS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("필수 ComprasNet 원본 파일이 없습니다: " + ", ".join(missing))
    READ_OPTIONS = {"sep": ";", "encoding": "cp1252", "decimal": ",", "dtype": str}
    pd.DataFrame([
        {"dataset": name, "path": str(path.relative_to(PROJECT_ROOT)), "size_gib": path.stat().st_size / 2**30}
        for name, path in RAW_PATHS.items()
    ])
    '''),
    code(r'''
    # cp1252 디코딩과 세미콜론 구분자 여부를 첫 줄에서 확인한다.
    format_checks = []
    for name, path in RAW_PATHS.items():
        first_line = path.open("r", encoding="cp1252", newline="").readline()
        columns = next(csv.reader([first_line], delimiter=";"))
        format_checks.append({
            "dataset": name,
            "cp1252_decode": True,
            "semicolon_count": first_line.count(";"),
            "column_count": len(columns),
            "first_columns": columns[:4],
        })
    pd.DataFrame(format_checks)
    '''),
    code(r'''
    # 작은 표본만 읽어 컬럼, 표본 행, dtype, 결측과 중복을 진단한다.
    SAMPLE_ROWS = {"auctions": 50_000, "items": 100_000, "participants": 100_000}
    samples = {
        name: pd.read_csv(path, nrows=SAMPLE_ROWS[name], low_memory=False, **READ_OPTIONS)
        for name, path in RAW_PATHS.items()
    }
    for name, frame in samples.items():
        print(f"\n[{name}] 표본 {len(frame):,}행 / {len(frame.columns)}열")
        display(pd.DataFrame({"column": frame.columns, "dtype": frame.dtypes.astype(str).values,
                              "missing_rate": frame.isna().mean().values}))
        display(frame.head(3))
        print("표본 완전중복 행:", int(frame.duplicated().sum()))
    '''),
    code(r'''
    # 날짜·상태·수량·금액 이상치를 표본 범위에서 확인한다.
    def brazil_number(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series.astype("string").str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce")

    auctions = samples["auctions"]
    items = samples["items"]
    date_summary = []
    for column in ["Data Resultado Compra", "Data Abertura"]:
        parsed = pd.to_datetime(auctions[column], dayfirst=True, errors="coerce")
        date_summary.append({"column": column, "min": parsed.min(), "max": parsed.max(), "invalid_rate": parsed.isna().mean()})
    display(pd.DataFrame(date_summary))
    display(auctions["Situação Licitação"].value_counts(dropna=False).head(20).rename("표본 건수"))
    quantity = brazil_number(items["Quantidade Item"])
    value = brazil_number(items["Valor Item"])
    pd.Series({
        "item_sample_rows": len(items), "quantity_le_zero": int((quantity <= 0).sum()),
        "value_le_zero": int((value <= 0).sum()), "quantity_parse_fail": int(quantity.isna().sum()),
        "value_parse_fail": int(value.isna().sum()),
    })
    '''),
    code(r'''
    # 식별코드 형식과 표본 키 결합 가능성을 확인한다.
    def digit_profile(series: pd.Series) -> dict:
        values = series.dropna().astype("string")
        lengths = values.str.len()
        return {"non_null": len(values), "digit_only_rate": values.str.fullmatch(r"\d+").mean(),
                "min_length": lengths.min(), "max_length": lengths.max(), "leading_zero_rate": values.str.startswith("0").mean()}

    id_checks = pd.DataFrame([
        {"field": "item_code_items", **digit_profile(items["Código Item Compra"])},
        {"field": "winner_cnpj", **digit_profile(items["Código Vencedor"])},
        {"field": "item_code_participants", **digit_profile(samples["participants"]["Código Item Compra"])},
        {"field": "participant_cnpj", **digit_profile(samples["participants"]["Código Participante"])},
    ])
    display(id_checks)
    item_keys = set(items["Código Item Compra"].dropna())
    participant_keys = samples["participants"]["Código Item Compra"].dropna()
    auction_key_cols = ["Número Licitação", "Código UG", "Código Modalidade Compra", "Número Processo"]
    auction_keys = set(map(tuple, auctions[auction_key_cols].fillna("").astype(str).to_numpy()))
    item_auction_keys = list(map(tuple, items[auction_key_cols].fillna("").astype(str).to_numpy()))
    pd.Series({
        "participant_item_join_rate_sample": participant_keys.isin(item_keys).mean(),
        "item_auction_composite_join_rate_sample": np.mean([key in auction_keys for key in item_auction_keys]),
    })
    '''),
    code(r'''
    # 설명 키워드로 상품·서비스 혼재 정도를 탐색한다(공식 분류가 아닌 대리변수).
    description = items["Descrição"].fillna("").str.upper()
    service_pattern = r"SERVI|MANUTEN|INSTALA|LOCA|CONTRATA|CONSULT|TREINAMENTO|TELEFON|VIGILANC|SEGURO|LIMPEZA|TRANSPORTE|AGENCIAMENTO|ASSINATURA"
    service_proxy = description.str.contains(service_pattern, regex=True)
    pd.Series({"service_keyword_proxy_rate": service_proxy.mean(),
               "goods_or_unclassified_proxy_rate": (~service_proxy).mean(),
               "note": "키워드 기반 대리분류이며 공식 상품/서비스 구분이 아님"})
    '''),
    code(r'''
    # 참여자 파일을 메모리에 올리지 않고 제한된 청크 수로 추가 검사한다.
    PARTICIPANT_CHUNKS_TO_SCAN = 4
    CHUNK_SIZE = 250_000
    usecols = ["Código Item Compra", "Código Participante", "Flag Vencedor"]
    chunk_stats = []
    for chunk_number, chunk in enumerate(pd.read_csv(RAW_PATHS["participants"], usecols=usecols,
                                                       chunksize=CHUNK_SIZE, low_memory=False, **READ_OPTIONS), start=1):
        chunk_stats.append({
            "chunk": chunk_number, "rows": len(chunk), "missing_supplier_rate": chunk["Código Participante"].isna().mean(),
            "duplicate_rate_within_chunk": chunk.duplicated().mean(),
            "winner_rate": chunk["Flag Vencedor"].astype("string").str.upper().eq("SIM").mean(),
        })
        if chunk_number >= PARTICIPANT_CHUNKS_TO_SCAN:
            break
    print(f"참여자 파일 앞쪽 {sum(x['rows'] for x in chunk_stats):,}행만 청크 진단했습니다. 전체 통계가 아닙니다.")
    pd.DataFrame(chunk_stats)
    '''),
    md(r'''
    ## 진단 범위의 한계

    이 노트북의 중복률, 결측률, 결합률, 상품/서비스 비율은 명시된 표본 범위의 진단치다.
    전체 참여자 파일을 한 번에 적재하지 않았다. 전체 행 처리는 04에서 청크 단위로 수행하며,
    원본 파일은 읽기만 한다.
    '''),
])


write("04_comprasnet_preprocessing.ipynb", [
    md(r'''
    # 04. ComprasNet 연구 분석용 전처리

    원본을 보존한 채 필요한 컬럼만 읽고 영문 snake_case 스키마, 품질 플래그, 안전한 식별자를 만든다.
    `Participantes.csv`는 청크 처리해 partitioned Parquet으로 저장한다. 설명 기반 `item_group`은
    임시 품목군이며 SKU 확정값이 아니고, 동시출현은 All-or-Nothing의 증거가 아니다.
    '''),
    code(common_setup),
    code(r'''
    # 경로·패키지·공통 변환 함수를 준비하고 필수 원본 누락 시 중단한다.
    import hashlib
    import re
    import unicodedata
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from IPython.display import display

    RAW_DIR = PROJECT_ROOT / "data" / "raw" / "comprasnet"
    PROCESSED = PROJECT_ROOT / "data" / "processed" / "comprasnet"
    paths = {"auctions": RAW_DIR / "Licitações.csv", "items": RAW_DIR / "Itens.csv", "participants": RAW_DIR / "Participantes.csv"}
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("필수 ComprasNet 원본 파일이 없습니다: " + ", ".join(missing))
    PROCESSED.mkdir(parents=True, exist_ok=True)
    PARTICIPANTS_OUT = PROCESSED / "participants"
    EVENTS_OUT = PROCESSED / "supplier_item_events"
    PARTICIPANTS_OUT.mkdir(parents=True, exist_ok=True)
    EVENTS_OUT.mkdir(parents=True, exist_ok=True)
    READ = {"sep": ";", "encoding": "cp1252", "decimal": ",", "dtype": str, "low_memory": False}

    def clean_code(series):
        return series.astype("string").str.replace(r"\D", "", regex=True).replace("", pd.NA)
    def brazil_number(series):
        return pd.to_numeric(series.astype("string").str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce")
    def normalize_description(value):
        if pd.isna(value): return ""
        text = unicodedata.normalize("NFKD", str(value).upper()).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^A-Z0-9]+", " ", text).strip()
    def stable_group(value):
        return "G_" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:12] if value else pd.NA
    def auction_id(frame):
        return ("A_" + clean_code(frame["ug_code"]).fillna("NA") + "_" + clean_code(frame["purchase_modality_code"]).fillna("NA")
                + "_" + clean_code(frame["purchase_number"]).fillna("NA") + "_" + clean_code(frame["process_number"]).fillna("NA"))
    '''),
    code(r'''
    # 조달 건 파일에서 필요한 컬럼만 읽고 날짜·금액·상태 플래그와 auction_id를 만든다.
    auction_columns = ["Número Licitação", "Código UG", "Código Modalidade Compra", "Número Processo", "Objeto",
                       "Situação Licitação", "UF", "Município", "Data Resultado Compra", "Data Abertura", "Valor Licitação"]
    auction_names = {"Número Licitação": "purchase_number", "Código UG": "ug_code", "Código Modalidade Compra": "purchase_modality_code",
                     "Número Processo": "process_number", "Objeto": "object_text", "Situação Licitação": "auction_status", "UF": "state",
                     "Município": "municipality", "Data Resultado Compra": "result_date", "Data Abertura": "opening_date", "Valor Licitação": "auction_total_value"}
    auctions = pd.read_csv(paths["auctions"], usecols=auction_columns, **READ).rename(columns=auction_names)
    auctions["auction_id"] = auction_id(auctions)
    for column in ["result_date", "opening_date"]:
        auctions[column] = pd.to_datetime(auctions[column], dayfirst=True, errors="coerce")
    auctions["auction_total_value"] = brazil_number(auctions["auction_total_value"])
    auctions["state"] = auctions["state"].astype("string").str.upper().str.strip()
    auctions["period"] = auctions["result_date"].dt.to_period("M").astype("string")
    auctions["flag_invalid_date"] = auctions["result_date"].isna()
    auctions["flag_invalid_region"] = ~auctions["state"].fillna("").str.fullmatch(r"[A-Z]{2}")
    auctions["flag_nonpositive_value"] = auctions["auction_total_value"].le(0) | auctions["auction_total_value"].isna()
    valid_status = auctions["auction_status"].fillna("").str.upper().str.contains("PUBLIC|HOMOLOG|ENCERR|RESULT", regex=True)
    auctions["flag_abnormal_status"] = ~valid_status
    auctions["is_valid_analysis_sample"] = ~auctions[["flag_invalid_date", "flag_invalid_region", "flag_nonpositive_value"]].any(axis=1)
    auctions = auctions.sort_values("result_date").drop_duplicates("auction_id", keep="last")
    auctions.to_parquet(PROCESSED / "auctions.parquet", index=False)
    display(auctions.head(3))
    print("auctions:", len(auctions), "valid:", int(auctions["is_valid_analysis_sample"].sum()))
    '''),
    code(r'''
    # 품목 파일을 정제하고 개별 행 ID와 설명 기반 임시 품목군을 분리한다.
    item_columns = ["Número Licitação", "Código UG", "Código Modalidade Compra", "Número Processo", "Código Item Compra",
                    "Descrição", "Quantidade Item", "Valor Item", "Código Vencedor"]
    item_names = {"Número Licitação": "purchase_number", "Código UG": "ug_code", "Código Modalidade Compra": "purchase_modality_code",
                  "Número Processo": "process_number", "Código Item Compra": "purchase_item_code", "Descrição": "item_description",
                  "Quantidade Item": "item_quantity", "Valor Item": "item_total_value", "Código Vencedor": "winner_code"}
    items = pd.read_csv(paths["items"], usecols=item_columns, **READ).rename(columns=item_names)
    items["purchase_item_code"] = clean_code(items["purchase_item_code"])
    items["winner_code"] = clean_code(items["winner_code"])
    items["auction_id"] = auction_id(items)
    items["item_id"] = "I_" + items["purchase_item_code"].fillna("MISSING")
    items["item_description_normalized"] = items["item_description"].map(normalize_description)
    items["item_group"] = items["item_description_normalized"].map(stable_group).astype("string")
    extracted = items["purchase_item_code"].str.extract(r"(?P<procurement_year>(?:19|20)\d{2})(?P<item_sequence>\d{5})$")
    items[["procurement_year", "item_sequence"]] = extracted
    items["item_quantity"] = brazil_number(items["item_quantity"])
    items["item_total_value"] = brazil_number(items["item_total_value"])
    items["unit_price"] = items["item_total_value"].div(items["item_quantity"].where(items["item_quantity"].gt(0)))
    auction_lookup = auctions[["auction_id", "result_date", "opening_date", "period", "state", "auction_status"]]
    items = items.merge(auction_lookup, on="auction_id", how="left", validate="many_to_one")
    items["flag_nonpositive_quantity"] = items["item_quantity"].le(0) | items["item_quantity"].isna()
    items["flag_nonpositive_value"] = items["item_total_value"].le(0) | items["item_total_value"].isna()
    items["flag_invalid_item_code"] = items["purchase_item_code"].isna() | extracted["procurement_year"].isna()
    items["flag_unmatched_auction"] = items["result_date"].isna()
    items["flag_duplicate"] = items.duplicated("purchase_item_code", keep="first")
    items["is_valid_analysis_sample"] = ~items[["flag_nonpositive_quantity", "flag_nonpositive_value", "flag_invalid_item_code", "flag_unmatched_auction", "flag_duplicate"]].any(axis=1)
    items.to_parquet(PROCESSED / "items.parquet", index=False)
    bundles = (items.loc[items["is_valid_analysis_sample"], ["auction_id", "item_group"]].drop_duplicates()
               .groupby("auction_id")["item_group"].agg(list).rename("item_groups").reset_index())
    bundles["item_group_count"] = bundles["item_groups"].str.len()
    bundles.to_parquet(PROCESSED / "auction_item_bundles.parquet", index=False)
    display(items.head(3))
    print("items:", len(items), "valid:", int(items["is_valid_analysis_sample"].sum()))
    '''),
    code(r'''
    # 참여자 2GB 파일을 청크로 읽어 공급자 이력과 품목 이벤트를 partitioned Parquet으로 저장한다.
    participant_columns = ["Número Licitação", "Código UG", "Código Modalidade Compra", "Número Processo", "Código Item Compra",
                           "Código Participante", "Nome Participante", "Flag Vencedor"]
    participant_names = {"Número Licitação": "purchase_number", "Código UG": "ug_code", "Código Modalidade Compra": "purchase_modality_code",
                         "Número Processo": "process_number", "Código Item Compra": "purchase_item_code", "Código Participante": "supplier_code",
                         "Nome Participante": "supplier_name", "Flag Vencedor": "winner_flag_raw"}
    item_lookup = items[["purchase_item_code", "auction_id", "item_id", "item_group", "result_date", "period"]].drop_duplicates("purchase_item_code")
    chunk_manifest = []
    CHUNK_SIZE = 250_000
    reader = pd.read_csv(paths["participants"], usecols=participant_columns, chunksize=CHUNK_SIZE, **READ)
    for chunk_number, chunk in enumerate(reader):
        chunk = chunk.rename(columns=participant_names)
        chunk["purchase_item_code"] = clean_code(chunk["purchase_item_code"])
        chunk["supplier_id"] = clean_code(chunk["supplier_code"])
        chunk["auction_id_raw"] = auction_id(chunk)
        chunk["is_winner"] = chunk["winner_flag_raw"].astype("string").str.upper().str.strip().eq("SIM")
        chunk = chunk.merge(item_lookup, on="purchase_item_code", how="left", validate="many_to_one")
        chunk["auction_id"] = chunk["auction_id"].fillna(chunk["auction_id_raw"])
        chunk["period"] = chunk["period"].fillna("unknown").astype(str)
        chunk["flag_invalid_supplier"] = chunk["supplier_id"].isna()
        chunk["flag_unmatched_item"] = chunk["item_id"].isna()
        key_text = chunk[["auction_id", "purchase_item_code", "supplier_id"]].fillna("").astype(str).agg("|".join, axis=1)
        chunk["event_id"] = key_text.map(lambda x: hashlib.sha1(x.encode("utf-8")).hexdigest())
        chunk["flag_duplicate_within_chunk"] = chunk.duplicated("event_id", keep="first")
        chunk["is_valid_analysis_sample"] = ~chunk[["flag_invalid_supplier", "flag_unmatched_item", "flag_duplicate_within_chunk"]].any(axis=1)
        participant_out = chunk[["event_id", "auction_id", "purchase_item_code", "item_id", "item_group", "supplier_id", "supplier_name",
                                 "is_winner", "result_date", "period", "flag_invalid_supplier", "flag_unmatched_item",
                                 "flag_duplicate_within_chunk", "is_valid_analysis_sample"]]
        event_out = participant_out.loc[participant_out["is_valid_analysis_sample"],
                                        ["event_id", "auction_id", "item_id", "item_group", "supplier_id", "is_winner", "result_date", "period"]]
        pq.write_to_dataset(pa.Table.from_pandas(participant_out, preserve_index=False), root_path=str(PARTICIPANTS_OUT),
                            partition_cols=["period"], basename_template=f"part-{chunk_number:05d}-{{i}}.parquet")
        pq.write_to_dataset(pa.Table.from_pandas(event_out, preserve_index=False), root_path=str(EVENTS_OUT),
                            partition_cols=["period"], basename_template=f"part-{chunk_number:05d}-{{i}}.parquet")
        chunk_manifest.append({"chunk": chunk_number, "rows": len(chunk), "valid_rows": len(event_out),
                               "unmatched_items": int(chunk["flag_unmatched_item"].sum()),
                               "duplicates_within_chunk": int(chunk["flag_duplicate_within_chunk"].sum())})
        if (chunk_number + 1) % 10 == 0:
            print(f"{chunk_number + 1}개 청크 처리 완료")
    manifest = pd.DataFrame(chunk_manifest)
    manifest.to_csv(PROCESSED / "preprocessing_manifest.csv", index=False, encoding="utf-8-sig")
    display(manifest.tail())
    print("전체 참여 행:", f"{manifest['rows'].sum():,}", "유효 이벤트:", f"{manifest['valid_rows'].sum():,}")
    '''),
    md(r'''
    ## 산출물과 해석 주의

    `auctions.parquet`, `items.parquet`, `participants/`, `supplier_item_events/`를 생성한다.
    `Valor Item`은 총 품목금액이며 `unit_price = item_total_value / item_quantity`이다.
    `item_id`는 조달 품목 행 ID, `item_group`은 설명 기반 탐색용 그룹이다. 전처리는 원본 행을
    삭제하지 않고 플래그와 `is_valid_analysis_sample`을 제공한다. 청크 경계를 넘는 동일 이벤트는
    `event_id`로 식별되며 분석 단계에서 전역 중복 제거한다.
    '''),
])


write("05_comprasnet_distribution_analysis.ipynb", [
    md(r'''
    # 05. ComprasNet 보정 분포·공급자 구조 분석

    04의 processed Parquet만 사용해 합성 시뮬레이션 보정 후보를 만든다. 직접 관측값,
    계산 대리변수, 별도 시나리오 값을 구분한다. 관측된 재등장은 진정한 잔존·이탈과 같지 않으며,
    기간 중 적합한 입찰기회가 없었을 수도 있다.
    '''),
    code(common_setup),
    code(r'''
    # processed 입력과 출력 경로를 확인하고 필요한 파일이 없으면 중단한다.
    import json
    import itertools
    import math
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import dask.dataframe as dd
    import networkx as nx
    from scipy import stats
    from IPython.display import display

    PROCESSED = PROJECT_ROOT / "data" / "processed" / "comprasnet"
    FIGURES = PROJECT_ROOT / "outputs" / "figures" / "comprasnet"
    FIGURES.mkdir(parents=True, exist_ok=True)
    required = [PROCESSED / "auctions.parquet", PROCESSED / "items.parquet", PROCESSED / "supplier_item_events"]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("04 노트북의 processed 산출물이 없습니다: " + ", ".join(missing))
    auctions = pd.read_parquet(PROCESSED / "auctions.parquet")
    items = pd.read_parquet(PROCESSED / "items.parquet")
    items_valid = items.loc[items["is_valid_analysis_sample"]].copy()
    events = dd.read_parquet(PROCESSED / "supplier_item_events", engine="pyarrow")
    events = events.drop_duplicates(subset=["event_id"])
    print("auctions", len(auctions), "items", len(items), "valid items", len(items_valid), "event partitions", events.npartitions)
    '''),
    code(r'''
    # 기간별 조달 건수와 조달 건별 임시 품목군 수를 계산하고 저장한다.
    period_auctions = (auctions.loc[auctions["is_valid_analysis_sample"]].groupby("period")["auction_id"].nunique()
                       .rename("auction_count").reset_index().sort_values("period"))
    items_per_auction = (items_valid.groupby("auction_id")["item_group"].nunique().rename("item_group_count").reset_index())
    period_auctions.to_csv(PROCESSED / "summary_period_auctions.csv", index=False, encoding="utf-8-sig")
    items_per_auction.describe().to_csv(PROCESSED / "summary_items_per_auction.csv", encoding="utf-8-sig")
    ax = period_auctions.plot(x="period", y="auction_count", figsize=(12, 4), legend=False, title="기간별 조달 건수")
    ax.tick_params(axis="x", rotation=90); plt.tight_layout(); plt.savefig(FIGURES / "period_auction_counts.png", dpi=150); plt.show()
    display(period_auctions.head())
    display(items_per_auction.describe())
    '''),
    code(r'''
    # 조달 건 내 임시 품목군 조합과 자주 함께 등장하는 쌍을 계산한다.
    bundle_groups = items_valid[["auction_id", "item_group"]].drop_duplicates().groupby("auction_id")["item_group"].agg(list)
    pair_counts = {}
    skipped_large_bundles = 0
    for groups in bundle_groups:
        unique_groups = sorted(set(groups))
        if len(unique_groups) > 30:
            skipped_large_bundles += 1
            continue
        for pair in itertools.combinations(unique_groups, 2):
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
    cooccurrence = pd.DataFrame([(a, b, count) for (a, b), count in pair_counts.items()],
                                columns=["item_group_a", "item_group_b", "cooccurrence_count"]).sort_values("cooccurrence_count", ascending=False)
    cooccurrence.head(1000).to_csv(PROCESSED / "summary_item_cooccurrence.csv", index=False, encoding="utf-8-sig")
    print("조합폭발 방지를 위해 제외한 30개 초과 묶음:", skipped_large_bundles)
    display(cooccurrence.head(20))
    '''),
    code(r'''
    # 품목군별 수량·총금액·단가와 참여 공급자 수를 집계한다.
    item_base = (items_valid.groupby("item_group").agg(
        item_rows=("item_id", "nunique"), auctions=("auction_id", "nunique"),
        quantity_median=("item_quantity", "median"), quantity_mean=("item_quantity", "mean"),
        total_value_median=("item_total_value", "median"), unit_price_median=("unit_price", "median"),
        description_example=("item_description", "first"),
    ).reset_index())
    suppliers_per_item = (events.groupby("item_group")["supplier_id"].nunique().compute().rename("supplier_count").reset_index())
    item_summary = item_base.merge(suppliers_per_item, on="item_group", how="left")
    item_summary.to_csv(PROCESSED / "summary_item_groups.csv", index=False, encoding="utf-8-sig")
    display(item_summary.sort_values(["auctions", "supplier_count"], ascending=False).head(20))
    '''),
    code(r'''
    # 공급자별 참여·낙찰, 품목 포트폴리오와 낙찰률을 계산한다.
    supplier_participations = events.groupby("supplier_id").size().compute().rename("participation_count")
    supplier_wins = events[events["is_winner"]].groupby("supplier_id").size().compute().rename("win_count")
    supplier_portfolio = events.groupby("supplier_id")["item_group"].nunique().compute().rename("item_group_count")
    supplier_summary = pd.concat([supplier_participations, supplier_wins, supplier_portfolio], axis=1).fillna(0).reset_index()
    supplier_summary["win_rate"] = supplier_summary["win_count"] / supplier_summary["participation_count"]
    supplier_summary.to_csv(PROCESSED / "summary_suppliers.csv", index=False, encoding="utf-8-sig")
    multi_item_suppliers = supplier_summary.sort_values(["item_group_count", "participation_count"], ascending=False).head(1000)
    multi_item_suppliers.to_csv(PROCESSED / "summary_multi_item_suppliers.csv", index=False, encoding="utf-8-sig")
    display(supplier_summary.describe())
    display(multi_item_suppliers.head(20))
    '''),
    code(r'''
    # 공급자–품목 연결 빈도로 HHI와 이분 네트워크 기본 통계를 계산한다.
    edge_counts = events.groupby(["item_group", "supplier_id"]).size().compute().rename("event_count").reset_index()
    edge_counts["item_total_events"] = edge_counts.groupby("item_group")["event_count"].transform("sum")
    edge_counts["share"] = edge_counts["event_count"] / edge_counts["item_total_events"]
    hhi = edge_counts.groupby("item_group")["share"].apply(lambda value: float((value ** 2).sum())).rename("supplier_hhi").reset_index()
    item_summary = item_summary.merge(hhi, on="item_group", how="left")
    item_summary.to_csv(PROCESSED / "summary_item_groups.csv", index=False, encoding="utf-8-sig")
    rare_items = item_summary.query("supplier_count <= 3").sort_values(["supplier_count", "auctions"], ascending=[True, False])
    rare_items.to_csv(PROCESSED / "summary_rare_item_candidates.csv", index=False, encoding="utf-8-sig")
    network_stats = {
        "supplier_nodes": int(edge_counts["supplier_id"].nunique()), "item_group_nodes": int(edge_counts["item_group"].nunique()),
        "edges": int(len(edge_counts)), "network_density": float(len(edge_counts) / max(1, edge_counts["supplier_id"].nunique() * edge_counts["item_group"].nunique())),
        "mean_supplier_degree": float(edge_counts.groupby("supplier_id")["item_group"].nunique().mean()),
        "mean_item_degree": float(edge_counts.groupby("item_group")["supplier_id"].nunique().mean()),
    }
    display(pd.Series(network_stats))
    display(rare_items.head(20))
    '''),
    code(r'''
    # 월별 공급자 재등장률과 반복 참여 간격을 계산한다. 이는 잔존률이 아닌 관측 대리변수다.
    monthly_presence = events[["supplier_id", "period"]].drop_duplicates().compute()
    monthly_presence = monthly_presence[monthly_presence["period"].astype(str).str.fullmatch(r"\d{4}-\d{2}")]
    monthly_presence["period"] = monthly_presence["period"].astype("string")
monthly_presence["period_dt"] = pd.to_datetime(monthly_presence["period"] + "-01")
    period_sets = {period: set(group["supplier_id"]) for period, group in monthly_presence.groupby("period_dt")}
    reappearance_rows = []
    periods = sorted(period_sets)
    for previous, current in zip(periods, periods[1:]):
        previous_set, current_set = period_sets[previous], period_sets[current]
        reappearance_rows.append({"previous_period": previous, "period": current, "previous_suppliers": len(previous_set),
                                  "reappearing_suppliers": len(previous_set & current_set),
                                  "reappearance_rate": len(previous_set & current_set) / max(1, len(previous_set))})
    reappearance = pd.DataFrame(reappearance_rows)
    reappearance.to_csv(PROCESSED / "summary_supplier_reappearance.csv", index=False, encoding="utf-8-sig")
    supplier_dates = events[["supplier_id", "result_date"]].dropna().drop_duplicates().compute()
    supplier_dates["result_date"] = pd.to_datetime(supplier_dates["result_date"])
    supplier_dates = supplier_dates.sort_values(["supplier_id", "result_date"])
    supplier_dates["repeat_gap_days"] = supplier_dates.groupby("supplier_id")["result_date"].diff().dt.days
    gap_summary = supplier_dates["repeat_gap_days"].dropna().describe()
    display(reappearance.head())
    display(gap_summary)
    '''),
    code(r'''
    # 반복거래와 공급자 수가 충분한 상품형 품목군 후보만 분포 적합 대상으로 고른다.
    service_pattern = r"SERVI|MANUTEN|INSTALA|LOCA|CONTRATA|CONSULT|TREINAMENTO|TELEFON|VIGILANC|SEGURO|LIMPEZA|TRANSPORTE|AGENCIAMENTO|ASSINATURA"
    candidates = item_summary.query("auctions >= 100 and supplier_count >= 10").copy()
    candidates["service_keyword_proxy"] = candidates["description_example"].fillna("").str.upper().str.contains(service_pattern, regex=True)
    candidates = candidates.loc[~candidates["service_keyword_proxy"]].sort_values(["auctions", "supplier_count"], ascending=False)
    candidates.head(50).to_csv(PROCESSED / "summary_distribution_candidates.csv", index=False, encoding="utf-8-sig")
    display(candidates.head(20))

    def fit_positive(values, group, variable):
        values = pd.Series(values).replace([np.inf, -np.inf], np.nan).dropna()
        values = values[values > 0].to_numpy()
        rows = []
        if len(values) < 50 or np.unique(values).size < 10:
            return rows
        for distribution_name, distribution in [("gamma", stats.gamma), ("lognormal", stats.lognorm)]:
            params = distribution.fit(values, floc=0)
            log_likelihood = float(np.sum(distribution.logpdf(values, *params)))
            rows.append({"item_group": group, "variable": variable, "distribution": distribution_name,
                         "n": len(values), "aic": 2 * len(params) - 2 * log_likelihood, "parameters": repr(tuple(float(x) for x in params))})
        return rows

    fit_rows = []
    for group in candidates.head(5)["item_group"]:
        group_rows = items_valid.loc[items_valid["item_group"].eq(group)]
        fit_rows += fit_positive(group_rows["item_quantity"], group, "item_quantity")
        fit_rows += fit_positive(group_rows["unit_price"], group, "unit_price")
    distribution_fits = pd.DataFrame(fit_rows)
    if not distribution_fits.empty:
        distribution_fits.to_csv(PROCESSED / "summary_distribution_fits.csv", index=False, encoding="utf-8-sig")
    display(distribution_fits)
    '''),
    code(r'''
    # 핵심 그래프와 보정 요약 JSON을 저장한다.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    items_per_auction["item_group_count"].clip(upper=20).hist(ax=axes[0], bins=20)
    axes[0].set_title("조달 건별 임시 품목군 수(20에서 절단)")
    supplier_summary["item_group_count"].clip(upper=supplier_summary["item_group_count"].quantile(.99)).hist(ax=axes[1], bins=30)
    axes[1].set_title("공급자별 품목군 커버리지(99% 절단)")
    plt.tight_layout(); plt.savefig(FIGURES / "bundle_and_supplier_coverage.png", dpi=150); plt.show()

    interpretation = pd.DataFrame([
        ("직접 관측", "조달일, 품목 행, 수량, 총금액, 참여·낙찰 표시, 공급자 ID"),
        ("계산 대리변수", "임시 품목군, 단가, 반복참여 간격, 재등장률, 포트폴리오, HHI"),
        ("별도 시나리오", "WTP, WTA, 공급용량, 배송비, 인센티브 반응, All-or-Nothing"),
    ], columns=["구분", "값"])
    display(interpretation)
    calibration_summary = {
        "seed": SEED,
        "observed": {"auction_rows": int(len(auctions)), "valid_item_rows": int(len(items_valid)),
                     "period_min": str(auctions["result_date"].min()), "period_max": str(auctions["result_date"].max())},
        "proxies": {**network_stats, "median_items_per_auction": float(items_per_auction["item_group_count"].median()),
                    "median_repeat_gap_days": None if pd.isna(gap_summary.get("50%")) else float(gap_summary["50%"]),
                    "candidate_item_groups": candidates.head(20)["item_group"].tolist()},
        "scenario_only": ["wtp", "wta", "capacity", "delivery_cost", "incentive_response", "all_or_nothing"],
        "limitations": ["item_group은 설명 기반 임시 그룹이며 SKU가 아니다.", "동시출현은 All-or-Nothing의 증거가 아니다.",
                        "재등장은 잔존과 동일하지 않으며 입찰기회 부재를 구분할 수 없다.", "분포 적합은 충분한 상품형 후보에만 제한했다."],
    }
    with (PROCESSED / "calibration_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(calibration_summary, handle, ensure_ascii=False, indent=2)
    print("저장:", PROCESSED / "calibration_summary.json")
    '''),
])


write("02_generated_data_check.ipynb", [
    md(r'''
    # 02. 합성 데이터 생성·검증

    `generator.py`가 smoke 설정을 구조대로 구현하는지 검사한다. 모든 조건은 개별 메시지로 출력하고,
    실패가 있으면 마지막 셀에서 실패 조건을 명시한 예외를 발생시킨다. 동일 seed의 결정론도 확인한다.
    '''),
    code(common_setup),
    code(r'''
    # 기존 생성기·검증기를 import해 smoke 인스턴스를 생성하고 저장한다.
    import json
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from IPython.display import display
    from src.config import load_config
    from src.generator import generate_instance, save_instance
    from src.validation import validate_instance

    config = load_config("configs/smoke.json")
    instance = generate_instance(config)
    output_path = save_instance(instance, "data/generated/smoke/generated_instance.json")
    print("생성 파일:", output_path.relative_to(PROJECT_ROOT))
    '''),
    code(r'''
    # 구매·공급 관계를 표 형태로 만들어 수량, 가격, 커버리지 검증에 사용한다.
    buyer_rows = [{"buyer_id": b.buyer_id, "sku_id": sku, "min_qty": item.min_qty, "max_qty": item.max_qty,
                   "wtp": item.wtp, "delivery_cost": b.delivery_cost}
                  for b in instance.buyers.values() for sku, item in b.items.items()]
    seller_rows = [{"seller_id": s.seller_id, "sku_id": sku, "capacity": item.capacity, "wta": item.wta}
                   for s in instance.sellers.values() for sku, item in s.items.items()]
    buyers_df, sellers_df = pd.DataFrame(buyer_rows), pd.DataFrame(seller_rows)
    count_summary = pd.Series({"buyers": instance.num_buyers, "sellers": instance.num_sellers, "skus": instance.num_skus,
                               "buyer_item_rows": len(buyers_df), "seller_item_rows": len(sellers_df)})
    display(count_summary)
    display(buyers_df.describe(include="all"))
    display(sellers_df.describe(include="all"))
    '''),
    code(r'''
    # 요구된 검증 조건을 각각 평가하고 실패 메시지를 구체적으로 남긴다.
    checks = {
        "configured_counts": (instance.num_buyers == config["num_buyers"] and instance.num_sellers == config["num_sellers"] and instance.num_skus == config["num_skus"], "설정과 실제 구매자·공급자·품목 수가 다릅니다."),
        "buyer_item_counts": (buyers_df.groupby("buyer_id")["sku_id"].nunique().between(1, instance.num_skus).all(), "구매자별 주문 품목 수가 허용범위를 벗어납니다."),
        "seller_item_counts": (sellers_df.groupby("seller_id")["sku_id"].nunique().between(1, instance.num_skus).all(), "공급자별 취급 품목 수가 허용범위를 벗어납니다."),
        "every_seller_has_item": (set(sellers_df["seller_id"]) == set(instance.seller_ids), "취급 품목이 없는 공급자가 있습니다."),
        "every_item_has_seller": (set(sellers_df["sku_id"]) == set(instance.sku_ids), "공급자가 없는 품목이 있습니다."),
        "min_le_max": ((buyers_df["min_qty"] <= buyers_df["max_qty"]).all(), "최소주문량이 최대주문량보다 큰 행이 있습니다."),
        "nonnegative_quantities": ((buyers_df[["min_qty", "max_qty"]].ge(0).all().all() and sellers_df["capacity"].ge(0).all()), "음수 수요 또는 공급량이 있습니다."),
        "nonnegative_prices_costs": ((buyers_df[["wtp", "delivery_cost"]].ge(0).all().all() and sellers_df["wta"].ge(0).all()), "음수 가격 또는 배송비가 있습니다."),
        "finite_wtp_wta": (np.isfinite(buyers_df["wtp"]).all() and np.isfinite(sellers_df["wta"]).all(), "WTP/WTA에 무한대 또는 결측이 있습니다."),
    }
    valid_triples = buyers_df[["buyer_id", "sku_id"]].merge(sellers_df[["seller_id", "sku_id"]], on="sku_id")
    checks["enough_tradable_triples"] = (len(valid_triples) >= instance.num_buyers, f"거래 가능 조합 {len(valid_triples)}개가 구매자 수보다 적습니다.")
    second = generate_instance(config)
    checks["same_seed_reproducible"] = (instance.to_dict() == second.to_dict(), "동일 seed에서 다른 인스턴스가 생성됐습니다.")
    library_validation = validate_instance(instance)
    checks["validation_py"] = (library_validation["valid"], "validation.py 실패: " + "; ".join(library_validation["failures"]))
    results = pd.DataFrame([{"check": name, "passed": bool(result), "failure_message": "" if result else message}
                            for name, (result, message) in checks.items()])
    display(results)
    print("거래 가능한 buyer–seller–item 조합:", len(valid_triples))
    '''),
    code(r'''
    # 수량, 가격, 주문 품목 수, 공급자 커버리지의 간단한 그래프를 그린다.
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    buyers_df["max_qty"].hist(ax=axes[0, 0]); axes[0, 0].set_title("최대 주문수량")
    sellers_df["capacity"].hist(ax=axes[0, 1]); axes[0, 1].set_title("공급 가능 수량")
    pd.concat([buyers_df["wtp"].rename("WTP"), sellers_df["wta"].rename("WTA")], axis=1).plot.hist(alpha=.6, ax=axes[1, 0]); axes[1, 0].set_title("WTP와 WTA")
    sellers_df.groupby("seller_id")["sku_id"].nunique().plot.bar(ax=axes[1, 1]); axes[1, 1].set_title("공급자별 품목 커버리지")
    plt.tight_layout(); plt.show()
    display(buyers_df.groupby("buyer_id")["sku_id"].nunique().describe().rename("구매자별 주문 품목 수"))
    display(sellers_df.groupby("seller_id")["sku_id"].nunique().describe().rename("공급자별 취급 품목 수"))
    '''),
    code(r'''
    # 하나라도 실패하면 조건과 메시지를 모아 명확히 중단한다.
    failures = results.loc[~results["passed"], ["check", "failure_message"]]
    if not failures.empty:
        detail = "\n".join(f"- {row.check}: {row.failure_message}" for row in failures.itertuples())
        raise AssertionError("합성 인스턴스 검증 실패:\n" + detail)
    print(f"모든 {len(results)}개 검증을 통과했습니다. validation.py 결과:", library_validation)
    '''),
])


print("생성 완료:", ", ".join(path.name for path in sorted(NOTEBOOKS.glob("0[1-5]_*.ipynb"))))
