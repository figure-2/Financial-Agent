# -*- coding: utf-8 -*-
"""
媛쒖씤蹂?Risk Tolerance瑜?怨좊젮??留ㅻℓ ?⑦꽩 ?꾪뿕 ?뚮┝ 湲곕뒫
Personalized Trading Pattern Risk Alert (PTPRA)
"""

# --- 1. ?꾩닔 ?쇱씠釉뚮윭由??꾪룷??---
import os
import re
import json
import requests
import time
import traceback
import difflib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from io import BytesIO
from zoneinfo import ZoneInfo

from langgraph.graph import StateGraph, END
from .state import AgentState

from bs4 import BeautifulSoup, NavigableString
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from PIL import Image

from .utils import load_config, create_shareable_url

KST = ZoneInfo("Asia/Seoul")
config = load_config()

# prompt_load
with open(config["task5"]["prompt_paths"]["extract_mydata"], 'r', encoding='utf-8') as f:
    prompt_extract_mydata = f.read()

with open(config["task5"]["prompt_paths"]["extract_paragraph"], 'r', encoding='utf-8') as f:
    prompt_extract_paragraph = f.read()

with open(config["task5"]["prompt_paths"]["summarize_reason"], 'r', encoding='utf-8') as f:
    prompt_summarize_reason = f.read()

def _find_best_matching_chunk(llm_output: str, original_text: str, threshold: float = 0.7) -> str | None:
    """
    LLM???앹꽦???띿뒪?몄? 媛???좎궗??遺遺꾩쓣 ?먮낯 ?띿뒪?몄뿉??李얠뒿?덈떎.
    臾몄옣 ?⑥쐞 諛??곗냽????臾몄옣 ?⑥쐞濡?鍮꾧탳?섏뿬 ?뺥솗?꾨? ?믪엯?덈떎.
    """
    # 1. ?먮낯 ?띿뒪?몃? 臾몄옣 ?⑥쐞濡?遺꾨━?섍퀬, 媛?臾몄옣??留덉묠?쒕? ?ㅼ떆 遺숈뿬以?    #    (split?쇰줈 ?명빐 ?щ씪吏?留덉묠?쒕? 蹂듭썝?댁빞 ?뺥솗??鍮꾧탳 媛??
    sentences = [s.strip() for s in original_text.split('.') if s.strip()]
    
    # 2. 鍮꾧탳???띿뒪???⑹뼱由?chunk) 由ъ뒪???앹꽦
    chunks_to_check = []
    # 2-1. 媛쒕퀎 臾몄옣 異붽?
    chunks_to_check.extend(sentences)
    # 2-2. ?곗냽????臾몄옣???⑹퀜??異붽? (??湲?留ㅼ묶???꾪빐)
    if len(sentences) > 1:
        for i in range(len(sentences) - 1):
            chunks_to_check.append(f"{sentences[i]}. {sentences[i+1]}".strip())

    if not chunks_to_check:
        return None

    best_match = ""
    max_similarity_ratio = 0.0
    matcher = difflib.SequenceMatcher(None, llm_output.strip())

    # 3. ?앹꽦??紐⑤뱺 chunk? ?좎궗??鍮꾧탳
    for chunk in chunks_to_check:
        # 留덉묠?쒓? ?녿뒗 ?먮낯 臾몄옣???덉쓣 ???덉쑝誘濡?chunk?먮룄 留덉묠?쒕? 遺숈뿬 理쒖쥌 鍮꾧탳
        # ?? " ...?쇨퀬 ?덈떎" ? " ...?쇨퀬 ?덈떎." 鍮꾧탳
        matcher.set_seq2(f"{chunk}.")
        # 留덉묠?쒕? ?쒖쇅?섍퀬??鍮꾧탳
        ratio_with_period = matcher.ratio()

        matcher.set_seq2(chunk)
        ratio_without_period = matcher.ratio()

        # ??寃쎌슦 以????믪? ?좎궗???먯닔瑜??ъ슜
        similarity_ratio = max(ratio_with_period, ratio_without_period)

        if similarity_ratio > max_similarity_ratio:
            max_similarity_ratio = similarity_ratio
            best_match = chunk

    # 4. ?꾧퀎媛믪쓣 ?섎뒗 寃쎌슦?먮쭔 理쒖쥌 寃곌낵濡??몄젙?섍퀬, 留덉묠?쒕? 遺숈뿬??諛섑솚
    if max_similarity_ratio >= threshold:
        return f"{best_match}."
    else:
        return None
    
def _extract_json_from_llm_response(response_text: str) -> Optional[Dict[str, Any]]:
    """
    LLM ?묐떟?먯꽌 泥?踰덉㎏濡?諛쒓껄?섎뒗 ?좏슚??JSON 媛앹껜瑜??덉젙?곸쑝濡?異붿텧?⑸땲??
    - ```json ... ``` 肄붾뱶 釉붾줉???곗꽑?곸쑝濡??뚯떛?⑸땲??
    - 臾몄옄??媛??대????댁뒪耳?댄봽?섏? ?딆? ?곕뵲?댄몴(")媛 ?ы븿??寃쎌슦?먮룄 蹂듦뎄瑜??쒕룄?⑸땲??
    """
    # 1. ```json ... ``` 肄붾뱶 釉붾줉 ?곗꽑 ?뚯떛
    match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if match:
        json_str = match.group(1)
        # 留덊겕?ㅼ슫 釉붾줉 ?덉쓽 JSON??源⑥죱?????덉쑝誘濡??꾨옒??蹂듦뎄 濡쒖쭅???듦낵?쒗궡
        response_text = json_str

    try:
        # 2. 愿꾪샇 ?띿쓣 ?댁슜??泥?踰덉㎏ JSON 媛앹껜濡?異붿젙?섎뒗 遺遺?異붿텧
        start_index = response_text.find('{')
        if start_index == -1:
            return None

        brace_count = 1
        i = start_index + 1
        while i < len(response_text) and brace_count > 0:
            char = response_text[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            i += 1

        if brace_count != 0:
            return None # 吏앹씠 留욌뒗 愿꾪샇瑜?李얠? 紐삵븿

        json_str_slice = response_text[start_index:i]

        # 3. ?쒖? ?뚯꽌濡?癒쇱? ?쒕룄 (媛??醫뗭? 耳?댁뒪)
        try:
            return json.loads(json_str_slice)
        except json.JSONDecodeError:
            # 4. ?뚯떛 ?ㅽ뙣 ?? 臾몄옄??媛??대????곗샂?쒕쭔 蹂듦뎄
            repaired_json = ""
            in_string_value = False
            i = 0
            while i < len(json_str_slice):
                char = json_str_slice[i]
                repaired_json += char

                # 肄쒕줎 ?ㅼ뿉 ?곗샂?쒓? ?ㅻ㈃, 臾몄옄??"媛????쒖옉??寃껋쑝濡?媛꾩＜
                # (??遺遺꾩씠???ㅻⅨ 援ъ“??嫄대뱶由ъ? ?딄린 ?꾪븿)
                if not in_string_value and char == ':' and i + 1 < len(json_str_slice):
                    next_char_index = i + 1
                    # 肄쒕줎 ?ㅼ쓽 怨듬갚 臾댁떆
                    while json_str_slice[next_char_index].isspace():
                        repaired_json += json_str_slice[next_char_index]
                        next_char_index += 1

                    if json_str_slice[next_char_index] == '"':
                        repaired_json += json_str_slice[next_char_index]
                        in_string_value = True
                        i = next_char_index

                # 臾몄옄??媛??대?瑜??쒗쉶?섎ŉ ?댁뒪耳?댄봽?섏? ?딆? ?곗샂?쒕? 李얠븘 蹂듦뎄
                elif in_string_value and char == '"':
                    if json_str_slice[i-1] != '\\': # ?대? ?댁뒪耳?댄봽??寃쎌슦???쒖쇅
                        # ???곗샂?쒓? 臾몄옄?댁쓣 ?ル뒗 寃껋씤吏 ?뺤씤
                        # (?ㅼ뿉 ?쇳몴???ル뒗 愿꾪샇媛 ?ㅻ㈃ ?ル뒗 ?곗샂?쒕줈 媛꾩＜)
                        peek_index = i + 1
                        while peek_index < len(json_str_slice) and json_str_slice[peek_index].isspace():
                            peek_index += 1

                        if peek_index < len(json_str_slice) and json_str_slice[peek_index] in [',', '}', ']']:
                             in_string_value = False # 臾몄옄??媛?醫낅즺
                        else:
                            # ?ル뒗 ?곗샂?쒓? ?꾨땲?쇰㈃, ?댁슜臾??곗샂?쒖씠誘濡??댁뒪耳?댄봽
                            repaired_json = repaired_json[:-1] + '\\"'

                i += 1

            # 蹂듦뎄??臾몄옄?대줈 理쒖쥌 ?뚯떛
            return json.loads(repaired_json)

    except (json.JSONDecodeError, IndexError):
        return None
    except Exception:
        return None

def highlight_and_capture_cropped(url: str, search_text: str, padding: int = 400) -> Optional[Image.Image]:
    """
    [理쒖쥌 ?꾩꽦?? ?뚯씠??BeautifulSoup)??HTML??吏곸젒 遺꾩꽍?섍퀬 ?섏젙????
    洹?寃곌낵瑜?釉뚮씪?곗?????뼱?뚯슦??媛???뺤떎???섏씠?쇱씠??諛⑹떇?낅땲??
    """

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument("window-size=1920,1080")
    chrome_options.add_argument("lang=ko_KR")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    driver = None
    try:
        # ------------------------------------------------------------------
        # 1. 釉뚮씪?곗??먯꽌 湲곗궗 蹂몃Ц???먮낯 HTML 肄붾뱶瑜?媛?몄샃?덈떎.
        # ------------------------------------------------------------------
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        article_selector = '#dic_area, #newsct_article, div.article_body_content'
        try:
            article_element = driver.find_element(By.CSS_SELECTOR, article_selector)
            original_html = article_element.get_attribute('innerHTML')
        except:
            print("  - ?ㅻ쪟: 湲곗궗 蹂몃Ц ?곸뿭??李얠? 紐삵뻽?듬땲??")
            return None

        # ------------------------------------------------------------------
        # 2. ?뚯씠??BeautifulSoup)??HTML???뺣? 遺꾩꽍?섍퀬 <mark> ?쒓렇瑜??쎌엯?⑸땲??
        # ------------------------------------------------------------------
        soup = BeautifulSoup(original_html, 'html.parser')

        # ?뺢퇋???⑥닔: 鍮꾧탳瑜??꾪빐 怨듬갚怨??쇰? ?뱀닔臾몄옄瑜??쒓굅
        def normalize_text(text):
            return re.sub(r'[\s"?쒋앪섃?', '', text)

        clean_search_text = normalize_text(search_text)

        # 紐⑤뱺 ?띿뒪???몃뱶瑜?李얠븘?? 洹??댁슜???⑹튇 ?꾩껜 ?띿뒪?몃? 留뚮벊?덈떎.
        all_text_nodes = soup.find_all(string=True)
        full_text = "".join(all_text_nodes)
        clean_full_text = normalize_text(full_text)

        # ?꾩껜 ?띿뒪?몄뿉??李얠쑝?ㅻ뒗 臾몄옣???쒖옉 ?꾩튂瑜?李얠뒿?덈떎.
        start_index = clean_full_text.find(clean_search_text)

        if start_index == -1:
            print(f"  - 寃쎄퀬: ?뚯씠??遺꾩꽍 ?④퀎?먯꽌 ?띿뒪??'{search_text}'瑜?李얠? 紐삵뻽?듬땲??")
            # ?섏씠?쇱씠???놁씠 ?ㅽ겕由곗꺑 罹≪쿂
            png = driver.get_screenshot_as_png()
            return Image.open(BytesIO(png))

        end_index = start_index + len(clean_search_text)

        # ?쒖옉/醫낅즺 ?꾩튂瑜??댁슜???ㅼ젣 ?섏씠?쇱씠?낇븷 ?띿뒪???몃뱶?ㅼ쓣 李얠뒿?덈떎.
        char_count = 0
        nodes_to_highlight = []
        for node in all_text_nodes:
            node_text_clean = normalize_text(node.string)
            node_len_clean = len(node_text_clean)

            # ?꾩옱 ?몃뱶媛 ?섏씠?쇱씠??踰붿쐞???ы븿?섎뒗吏 ?뺤씤
            if char_count < end_index and char_count + node_len_clean > start_index:
                nodes_to_highlight.append(node)

            char_count += node_len_clean
            if char_count >= end_index:
                break

        # 李얠? ?몃뱶?ㅼ쓣 <mark> ?쒓렇濡?媛먯떥以띾땲??
        for node in nodes_to_highlight:
            if isinstance(node, NavigableString) and node.parent.name != 'script':
                mark_tag = soup.new_tag("mark", style="background-color: yellow; color: black;")
                mark_tag.string = node.string
                node.replace_with(mark_tag)

        # ?섏젙??HTML 肄붾뱶瑜?臾몄옄?대줈 ?ㅼ떆 媛?몄샃?덈떎.
        highlighted_html = str(soup)

        # ------------------------------------------------------------------
        # 3. 釉뚮씪?곗????섏젙??HTML 肄붾뱶瑜???뼱?뚯썎?덈떎.
        # ------------------------------------------------------------------
        # Lazy Loading 泥섎━ 諛??고듃 二쇱엯
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        driver.execute_script("window.scrollTo(0, 0);")
        driver.execute_script("""
            var style = document.createElement('style');
            style.innerHTML = `@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
                               * { font-family: 'Noto Sans KR', '留묒? 怨좊뵓', sans-serif !important; }`;
            document.head.appendChild(style);
        """)

        WebDriverWait(driver, 10).until(
            # 諛붽묑履쎌? ()濡?媛먯떥怨? ?먮컮?ㅽ겕由쏀듃 臾몄옄?댁? ""? ''瑜??욎뼱 ?ъ슜
            lambda d: d.execute_script("return document.fonts.check('1em \"Noto Sans KR\"')")
        )

        # ?먮컮?ㅽ겕由쏀듃???댁젣 怨꾩궛 ?놁씠, ?섏젙??HTML??'??뼱?곕뒗' ??븷留??⑸땲??
        driver.execute_script(f"""
            const articleBody = document.querySelector('{article_selector}');
            if (articleBody) {{
                articleBody.innerHTML = arguments[0];
                const mark = articleBody.querySelector('mark');
                if (mark) {{
                    mark.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                }}
            }}
        """, highlighted_html)

        # ------------------------------------------------------------------
        # 4. ?ㅽ겕由곗꺑??李띻퀬 ?대?吏瑜??섎씪?낅땲??
        # ------------------------------------------------------------------
        time.sleep(2) # ?뚮뜑留??湲?
        # mark ?쒓렇???꾩튂瑜?釉뚮씪?곗??먯꽌 吏곸젒 怨꾩궛
        rect_script = """
        const mark = document.querySelector('mark');
        if (!mark) return null;
        const rect = mark.getBoundingClientRect();
        return { top: rect.top + window.scrollY, bottom: rect.bottom + window.scrollY };
        """
        rect = driver.execute_script(rect_script)

        if not rect:
             raise Exception("?섏씠?쇱씠?낆? ?깃났?덉쑝?? ?붾㈃ ?꾩튂瑜?怨꾩궛?????놁뒿?덈떎.")

        total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
        driver.set_window_size(1920, total_height)
        time.sleep(1)
        png = driver.get_screenshot_as_png()
        full_screenshot = Image.open(BytesIO(png))

        top = max(0, int(rect['top'] - padding))
        bottom = min(full_screenshot.height, int(rect['bottom'] + padding))

        cropped_image = full_screenshot.crop((0, top, full_screenshot.width, bottom))
        print("  - ?좎젙???댁뒪 湲곗궗 以?留ㅻℓ??洹쇰낯 ?먯씤???대떦?섎뒗 ?듭떖 臾몄옣???섏씠?쇱씠?낇븯??듬땲??")
        return cropped_image

    except Exception as e:
        print(f"\nERROR: highlight_and_capture_cropped 泥섎━ 以??ш컖???ㅻ쪟 諛쒖깮: {e}")
        traceback.print_exc()
        # ?ㅻ쪟 諛쒖깮 ??鍮꾩긽?⑹쑝濡??꾩껜 ?섏씠吏 罹≪쿂
        if driver:
            try:
                return Image.open(BytesIO(driver.get_screenshot_as_png()))
            except:
                return None
        return None
    finally:
        if driver:
            driver.quit()

# --- ?먯씠?꾪듃 ?몃뱶 ?⑥닔??---
def extract_transactions(state: AgentState) -> Dict[str, Any]:
    print("\n[PTPRA Agent] 1. ?ъ슜???낅젰?먯꽌 留ㅻℓ 湲곕줉 異붿텧 以?..")
    user_input = state["query"]
    transaction_records = []
    json_start = user_input.find('[')
    json_end = user_input.rfind(']')
    if json_start != -1 and json_end != -1 and json_end > json_start:
        json_str = user_input[json_start : json_end + 1]
        try:
            parsed_data = json.loads(json_str)
            for record in parsed_data:
                transaction_records.append({
                    "time": datetime.strptime(record["?좎쭨"], "%Y-%m-%d"),
                    "type": record["嫄곕옒?좏삎"],
                    "stock_name": record["醫낅ぉ"],
                    "price": record["媛寃?],
                    "quantity": record["?섎웾"]
                })
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            state["error"] = f"留ㅻℓ 湲곕줉 JSON ?뚯떛 以??ㅻ쪟 諛쒖깮: {e}"
            return state
    if not transaction_records:
        state["error"] = "?좏슚??留ㅻℓ 湲곕줉??異붿텧?????놁뒿?덈떎."
    else:
        state["transaction_records"] = sorted(transaction_records, key=lambda x: x['time'])
        print(f"  - {len(transaction_records)}媛쒖쓽 留ㅻℓ 湲곕줉 異붿텧 ?꾨즺.")
    return state

def extract_mydata(state: AgentState) -> Dict[str, Any]:
    print("\n[PTPRA Agent] 2. ?ъ슜???낅젰?먯꽌 留덉씠?곗씠??異붿텧 以?..")
    user_input = state["query"]
    llm = state["llm"]
    system_msg = "?뱀떊? 二쇱뼱吏??띿뒪?몄뿉???ъ슜?먯쓽 湲덉쑖 愿??媛쒖씤?뺣낫瑜??뺥솗??異붿텧?섏뿬 JSON ?뺤떇?쇰줈 援ъ“?뷀븯???꾨Ц媛?낅땲??"
    prompt = prompt_extract_mydata.format(user_input=user_input)
    try:
        response = llm.invoke(prompt, system_message=system_msg)
        my_data = _extract_json_from_llm_response(response)
        if not my_data or my_data.get('age') is None or my_data.get('investment_profile') is None or my_data.get('total_financial_assets') is None:
            state["error"] = "媛쒖씤??遺꾩꽍???꾩슂??留덉씠?곗씠???ъ옄 ?깊뼢, ?섏씠, 珥?湲덉쑖?먯궛) ?뺣낫媛 遺議깊빀?덈떎."
            return state
        state["my_data"] = my_data
        print(f"  - 留덉씠?곗씠??異붿텧 ?꾨즺: {my_data}")
    except Exception as e:
        state["error"] = f"留덉씠?곗씠??異붿텧 以?LLM ?몄텧 ?ㅻ쪟 諛쒖깮: {e}"
    return state

def analyze_risk_patterns(state: AgentState) -> Dict[str, Any]:
    print("\n[PTPRA Agent] 3. 媛쒖씤?붾맂 ?꾪뿕 湲곗? ?곸슜 諛??⑦꽩 遺꾩꽍 以?..")
    transactions = state["transaction_records"]
    my_data = state["my_data"]
    holdings = {}
    for trade in transactions:
        stock_name = trade['stock_name']
        qty = trade['quantity']
        price = trade['price']
        trade_value = qty * price
        if trade['type'] == '留ㅼ닔':
            if stock_name not in holdings:
                holdings[stock_name] = {'quantity': 0, 'value': 0}
            holdings[stock_name]['quantity'] += qty
            holdings[stock_name]['value'] += trade_value
        elif trade['type'] == '留ㅻ룄':
            if stock_name in holdings:
                holdings[stock_name]['quantity'] -= qty
                holdings[stock_name]['value'] -= trade_value
                if holdings[stock_name]['quantity'] <= 0:
                    del holdings[stock_name]
        if stock_name in holdings:
            holdings[stock_name]['last_trade'] = trade
    final_portfolio_value = sum(h['value'] for h in holdings.values())
    if final_portfolio_value <= 0:
        state["final_alert_message"] = "紐⑤뱺 醫낅ぉ??留ㅻ룄?섏뼱 遺꾩꽍???꾩옱 蹂댁쑀 ?ы듃?대━?ㅺ? ?놁뒿?덈떎."
        return state
    age = my_data['age']
    profile = my_data['investment_profile']
    if 20 <= age < 40: lifecycle_coeff = 0.30
    elif 40 <= age < 60: lifecycle_coeff = 0.20
    else: lifecycle_coeff = 0.10
    profile_map = {"?덉젙??: 0.20, "?덉젙異붽뎄??: 0.40, "?꾪뿕以묐┰??: 0.60, "?곴레?ъ옄??: 0.80, "怨듦꺽?ъ옄??: 0.90}
    equity_limit_ratio = profile_map.get(profile, 0.60)
    personalized_threshold = equity_limit_ratio * lifecycle_coeff
    print(f"  - 媛쒖씤?붾맂 ?⑥씪 醫낅ぉ 理쒕? 鍮꾩쨷 ?꾧퀎移? {personalized_threshold:.2%}")
    riskiest_stock = None
    max_concentration = 0
    for name, holding_info in holdings.items():
        concentration = holding_info['value'] / final_portfolio_value
        if concentration > personalized_threshold and concentration > max_concentration:
            max_concentration = concentration
            riskiest_stock = name
    state['preprocessed_data'] = {'holdings': holdings, 'final_portfolio_value': final_portfolio_value}
    if riskiest_stock:
        risk_pattern = {
            "risk_category": "吏묒쨷 ?ъ옄 ?꾪뿕",
            "stock_name": riskiest_stock,
            "concentration": max_concentration,
            "description": f"'{riskiest_stock}' 醫낅ぉ??鍮꾩쨷??{max_concentration:.2%}濡? 怨좉컼?섏쓽 ?꾨줈???섏씠: {age}?? ?깊뼢: {profile})???곕Ⅸ 沅뚯옣 ?쒕룄 {personalized_threshold:.2%}瑜?珥덇낵???곹솴?낅땲??",
            "recommendation": "?뱀젙 醫낅ぉ?????怨쇰룄???ъ옄???대떦 醫낅ぉ??媛寃?蹂?숈뿉 ?ы듃?대━???꾩껜媛 ?ш쾶 ?붾뱾由????덉뒿?덈떎. 遺꾩궛 ?ъ옄瑜??듯빐 ?덉젙?깆쓣 ?믪씠??寃껋쓣 怨좊젮?대낫?몄슂."
        }
        trigger_trade = holdings[riskiest_stock]['last_trade']
        state["identified_risk_pattern"] = risk_pattern
        state["triggering_trade_info"] = trigger_trade
        stock_name = trigger_trade['stock_name']
        causal_keywords = ["?ㅼ쟻", "怨꾩빟", "?좎젣??, "紐⑺몴二쇨?", "而⑥꽱?쒖뒪", "?꾨쭩"]
        search_queries = [f"{stock_name} {keyword}" for keyword in causal_keywords]
        search_queries.append(f"{stock_name} 二쇨?")
        state["search_queries"] = search_queries
        print(f"  - 理쒖쥌 ?ы듃?대━??遺꾩꽍 寃곌낵, '{riskiest_stock}'?먯꽌 吏묒쨷 ?ъ옄 ?꾪뿕 媛먯?.")
    else:
        print("  - 理쒖쥌 ?ы듃?대━??遺꾩꽍 寃곌낵, 媛쒖씤??湲곗???珥덇낵?섎뒗 ?ш컖???꾪뿕 ?⑦꽩? 諛쒓껄?섏? ?딆븯?듬땲??")
        state["final_alert_message"] = "留ㅻℓ 湲곕줉??遺꾩꽍??寃곌낵, 怨좉컼?섏쓽 ?ъ옄 ?깊뼢怨??섏씠瑜?怨좊젮?덉쓣 ???밸퀎???곕젮?섎뒗 ?꾪뿕 ?⑦꽩? 諛쒓껄?섏? ?딆븯?듬땲?? ?덉젙?곸씤 ?ъ옄瑜??댁뼱媛怨?怨꾩떗?덈떎."
    return state

def verify_analysis_results(state: AgentState) -> Dict[str, Any]:
    if not state.get("identified_risk_pattern"):
        state['is_verified'] = True
        return state
    print("\n[PTPRA Agent] 4. 遺꾩꽍 寃곌낵 寃利?以?..")
    risk_pattern = state["identified_risk_pattern"]
    holdings = state['preprocessed_data']['holdings']
    final_portfolio_value = state['preprocessed_data']['final_portfolio_value']
    stock_name_to_verify = risk_pattern['stock_name']
    reported_concentration = risk_pattern['concentration']
    actual_value = holdings.get(stock_name_to_verify, {}).get('value', 0)
    actual_concentration = actual_value / final_portfolio_value if final_portfolio_value > 0 else 0
    if round(reported_concentration, 4) == round(actual_concentration, 4):
        print(f"  - ??寃利??깃났: 蹂닿퀬??鍮꾩쨷({reported_concentration:.2%})???ㅼ젣 鍮꾩쨷({actual_concentration:.2%})怨??쇱튂?⑸땲??")
        state['is_verified'] = True
    else:
        error_message = f"寃利??ㅽ뙣: 蹂닿퀬??'{stock_name_to_verify}' 鍮꾩쨷({reported_concentration:.2%})???ㅼ젣 怨꾩궛??鍮꾩쨷({actual_concentration:.2%})怨??ㅻ쫭?덈떎."
        print(f"  - ??{error_message}")
        state['error'] = error_message
        state['is_verified'] = False
    return state

def search_korean_documents(state: AgentState) -> Dict[str, Any]:
    """
    ?ㅼ씠踰??댁뒪 API瑜??ъ슜???먯씤 異붿젙???꾪븳 臾몄꽌瑜?寃?됲븯怨?
    留ㅻℓ???댁쟾 ?댁뒪瑜??곗꽑?곸쑝濡??꾪꽣留곹빀?덈떎.
    """
    if not state.get("search_queries"):
        return state

    print(f"\n[PTPRA Agent] 5. ?먯씤 異붿젙???꾪븳 ?댁뒪 寃??諛??꾪꽣留?以?..")
    
    # --- API ?ㅼ젙 ---
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    
    all_results = []
    seen_urls = set()

    for query in state["search_queries"]:
        url = f"https://openapi.naver.com/v1/search/news.json?query={requests.utils.quote(query)}&display=10&sort=sim"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data and "items" in data:
                for item in data["items"]:
                    link = item.get("link", "")
                    # Naver ?댁뒪 留곹겕留??ы븿?섍퀬, 以묐났 URL ?쒓굅
                    if "n.news.naver.com" not in link or link in seen_urls:
                        continue
                    
                    pub_date_str = item.get("pubDate")
                    pub_date = None
                    if pub_date_str:
                        try:
                            # ?쒓컙? ?뺣낫瑜??ы븿?섏뿬 datetime 媛앹껜濡?蹂???? ?쒓컙? ?뺣낫 ?쒓굅 (naive datetime?쇰줈 ?듭씪)
                            dt_object = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                            pub_date = dt_object.replace(tzinfo=None)
                        except ValueError:
                            pass # ?좎쭨 ?뚯떛 ?ㅽ뙣 ??None ?좎?
                    
                    result = {
                        "query": query,
                        "snippet": BeautifulSoup(item.get("description", ""), 'html.parser').get_text(),
                        "source_title": BeautifulSoup(item.get("title", ""), 'html.parser').get_text(),
                        "url": link,
                        "pub_date": pub_date
                    }
                    all_results.append(result)
                    seen_urls.add(result["url"])
        except Exception as e:
            # ?ㅽ뙣?섎뜑?쇰룄 ?ㅻⅨ 荑쇰━ 寃?됱? 怨꾩냽 吏꾪뻾
            print(f"  - 寃쎄퀬: '{query}' 寃??以??ㅻ쪟 諛쒖깮 - {e}")

    if not all_results:
        state["error"] = "愿???댁뒪瑜?李얠쓣 ???놁뒿?덈떎."
        return state

    trade_date = state["triggering_trade_info"]['time']
    
    # 1. 留ㅼ닔??湲곗?(-7??~ ?뱀씪)?쇰줈 ?곗꽑 ?꾪꽣留?    start_date = trade_date - timedelta(days=7)
    end_date = trade_date
    filtered_results = [res for res in all_results if res["pub_date"] and (start_date <= res["pub_date"] <= end_date)]

    # 2. 吏?뺣맂 湲곌컙 ???댁뒪媛 ?놁쓣 寃쎌슦, ?泥?Fallback) 濡쒖쭅 ?ㅽ뻾
    if not filtered_results and all_results:
        print("  - 寃쎄퀬: 吏?뺣맂 湲곌컙 ???댁뒪媛 ?놁뒿?덈떎. 留ㅻℓ?쇨낵 媛??媛源뚯슫 '誘몃옒' ?댁뒪瑜??좏깮?⑸땲??")

        # 2-1. 留ㅻℓ??'?댁쟾'???꾩껜 怨쇨굅 湲곗궗 以?媛??媛源뚯슫 寃껋쓣 ?먯깋
        past_results = [res for res in all_results if res.get("pub_date") and res['pub_date'] <= trade_date]
        if past_results:
            closest_news = min(past_results, key=lambda x: trade_date - x['pub_date'])
            filtered_results = [closest_news]
        else:
            # 2-2. 怨쇨굅 湲곗궗媛 ?꾪? ?놁쓣 寃쎌슦?먮쭔 '誘몃옒' 湲곗궗 以?媛??媛源뚯슫 寃껋쓣 ?먯깋
            future_results = [res for res in all_results if res.get("pub_date") and res['pub_date'] > trade_date]
            if future_results:
                closest_news = min(future_results, key=lambda x: x['pub_date'] - trade_date)
                filtered_results = [closest_news]
                # 理쒖쥌 由ы룷?몄뿉 ???쒓퀎?먯쓣 紐낆떆?????덈룄濡??곹깭??湲곕줉
                state["analysis_limitation"] = "留ㅻℓ ?쒖젏 ?댁쟾??吏곸젒?곸씤 ?먯씤 ?댁뒪瑜?李얠? 紐삵빐, ?쒖젏怨?媛??媛源뚯슫 理쒖떊 ?댁뒪瑜?湲곕컲?쇰줈 遺꾩꽍?덉뒿?덈떎."

    state["search_results_korean"] = filtered_results
    if not filtered_results:
        state["error"] = "留ㅻℓ ?쒖젏怨??곌????믪? ?댁뒪瑜?理쒖쥌?곸쑝濡?李얠쓣 ???놁뒿?덈떎."
        
    return state

# --- [?좉퇋] ?댁뒪 湲곗궗 ?먮Ц ?ㅽ겕?섑븨 ?⑥닔 ---
# [?섏젙 ?? get_full_text_from_url ?⑥닔 (Selenium ?ъ슜)
def get_full_text_from_url(url: str) -> Optional[str]:
    """
    [理쒖쥌 ?섏젙?? Selenium???ъ슜?섏뿬 釉뚮씪?곗?媛 ?뚮뜑留곹븳 理쒖쥌 ?띿뒪?몃? 異붿텧?⑸땲??
    ?대줈???섏씠?쇱씠???쒖젏???띿뒪?몄? 100% ?쇨??깆쓣 蹂댁옣?⑸땲??
    """
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        # ?섏씠吏 濡쒕뵫??異⑸텇??湲곕떎由쎈땲??
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # 湲곗궗 蹂몃Ц???좏깮?⑸땲??
        article_selector = '#dic_area, #newsct_article, div.article_body_content'

        # ?먮컮?ㅽ겕由쏀듃瑜??ㅽ뻾?섏뿬 釉뚮씪?곗?媛 蹂대뒗 洹몃?濡쒖쓽 ?띿뒪??.innerText)瑜?媛?몄샃?덈떎.
        # .innerText??以꾨컮轅? 怨듬갚 ?깆쓣 媛???뺥솗?섍쾶 泥섎━?댁쨳?덈떎.
        script = f"return document.querySelector('{article_selector}').innerText;"
        full_text = driver.execute_script(script)

        if full_text:
            # ?щ윭 媛쒖쓽 怨듬갚???섎굹濡??⑹튂??理쒖쥌 ?뺣━ ?묒뾽
            normalized_text = re.sub(r'\s+', ' ', full_text).strip()
            print(f"  - [2?④퀎 遺꾩꽍 ?꾨즺]. Selenium?쇰줈 ?ㅽ겕?섑븨 ?깃났: {len(normalized_text)}???띿뒪???뺣낫.")
            return normalized_text
        else:
            print("  - 寃쎄퀬: ?댁뒪 蹂몃Ц 而⑦뀗痢??곸뿭??李얠? 紐삵뻽?듬땲??")
            return None

    except Exception as e:
        print(f"  - ?ㅻ쪟: Selenium 湲곕컲 ?댁뒪 ?먮Ц ?ㅽ겕?섑븨 以??ㅻ쪟 諛쒖깮 ({e})")
        # traceback.print_exc() # ?붾쾭源????ъ슜
        return None
    finally:
        if driver:
            driver.quit()

def analyze_and_extract_from_news(state: AgentState) -> Dict[str, Any]:
    """
    [?섏젙??踰꾩쟾]
    媛??愿?⑥꽦 ?믪? ?댁뒪瑜??좎젙?섍퀬, 洹??댁뒪 ?먮Ц?먯꽌 '?듭떖 臾몄옣???ы븿?섎뒗 臾몃떒 ?꾩껜'瑜?異붿텧?⑸땲??
    """
    if not state.get("search_results_korean"):
        return state

    llm = state["llm"]

    age = state["my_data"]["age"]
    investment_profile = state["my_data"]["investment_profile"]
    trade_time = state["triggering_trade_info"]['time'].strftime('%Y??%m??%d??)
    stock_name = state["triggering_trade_info"]['stock_name']
    type = state["triggering_trade_info"]['type']
    
    search_results = state["search_results_korean"]

    # === 1?④퀎: 媛??愿?⑥꽦 ?믪? ?댁뒪 湲곗궗 URL怨?'洹쇰낯 ?먯씤' ?붿빟 ===
    print("\n[PTPRA Agent] 6a. 留ㅻℓ ?먯씤 異붿젙 (1/3) - 理쒖쟻 ?댁뒪 湲곗궗 ?좎젙 以?..")

    search_summary = ""
    for i, res in enumerate(search_results):
        search_summary += f"{i+1}. ?쒕ぉ: {res['source_title']}\n   ?댁슜: {res['snippet']}\n   寃뚯떆?? {res['pub_date']}\n   URL: {res['url']}\n\n"

    system_msg_step1 = "?뱀떊? 湲덉쑖 ?좊꼸由ъ뒪?몄엯?덈떎. 二쇱뼱吏??뺣낫瑜?諛뷀깢?쇰줈, ?뱀젙 ?ъ옄 寃곗젙??媛???좊젰??'洹쇰낯 ?먯씤'??李얠븘?대뒗 ?꾨Т瑜?諛쏆븯?듬땲??"
    prompt_step1 = prompt_summarize_reason.format(age=age,
                                                  investment_profile=investment_profile,
                                                  trade_time=trade_time,
                                                  stock_name=stock_name,
                                                  type=type,
                                                  search_summary=search_summary,
                                                )

    try:
        response_step1 = llm.invoke(prompt_step1, system_message=system_msg_step1)
        analysis_result_step1 = _extract_json_from_llm_response(response_step1)

        if not (analysis_result_step1 and analysis_result_step1.get("selected_url") and analysis_result_step1.get("reason_summary")):
            state["error"] = f"?댁뒪 遺꾩꽍 1?④퀎(?좎젙) LLM ?묐떟 ?뚯떛 ?ㅽ뙣: {response_step1[:500]}..."
            return state

        selected_url = analysis_result_step1["selected_url"]
        reason_summary = analysis_result_step1["reason_summary"]
        state["selected_document_url"] = selected_url
        state["news_analysis_result"] = analysis_result_step1
        print(f"  - [1?④퀎 遺꾩꽍 ?꾨즺]. ?좏깮??URL: {selected_url}")

    except Exception as e:
        state["error"] = f"?댁뒪 遺꾩꽍 1?④퀎(?좎젙) 以?LLM ?몄텧 ?ㅻ쪟: {e}"
        return state

    # === 2?④퀎: ?좏깮??URL?먯꽌 ?댁뒪 ?먮Ц ?꾩껜 ?ㅽ겕?섑븨 ===
    print("\n[PTPRA Agent] 6b. 留ㅻℓ ?먯씤 異붿젙 (2/3) - ?댁뒪 ?먮Ц ?뺣낫 以?..")
    full_text = get_full_text_from_url(selected_url)
    if not full_text:
        state["error"] = f"?좏깮???댁뒪 湲곗궗({selected_url})???먮Ц??媛?몄삤?????ㅽ뙣?덉뒿?덈떎."
        return state

    # === 3?④퀎: ?듭떖 臾몄옣???ы븿?섎뒗 '臾몃떒 ?꾩껜' 異붿텧 ===
    print("\n[PTPRA Agent] 6c. 留ㅻℓ ?먯씤 異붿젙 (3/3) - ?듭떖 臾몃떒 異붿텧 以?..")

    system_msg_step2 = "?뱀떊? 二쇱뼱吏?湲?먯꽌 ?뱀젙 ?뺣낫? 媛??愿??源딆? 遺遺꾩쓣 **蹂寃??놁씠 洹몃?濡?* 李얠븘?대뒗, ?뺥솗?깆씠 留ㅼ슦 ?믪? AI?낅땲??"
    prompt_step2 = prompt_extract_paragraph.format(reason_summary=reason_summary, full_text=full_text)

    try:
        # 1. LLM???몄텧?섏뿬 愿??源딆? 遺遺꾩뿉 ???'?⑥꽌' ?띿뒪?몃? ?살쓬
        response_step2 = llm.invoke(prompt_step2, system_message=system_msg_step2)
        analysis_result_step2 = _extract_json_from_llm_response(response_step2)

        if not (analysis_result_step2 and analysis_result_step2.get("containing_paragraph")):
            state["error"] = f"?댁뒪 遺꾩꽍 3?④퀎(臾몃떒 異붿텧) LLM ?묐떟 ?뚯떛 ?ㅽ뙣: {response_step2[:500]}..."
            return state

        # 2. LLM??異붿텧???띿뒪?몃? ?먮낯?먯꽌 李얘린 ?꾪븳 '?⑥꽌'濡??ъ슜
        llm_extracted_clue = analysis_result_step2["containing_paragraph"]

        # 3. '?⑥꽌'? ?먮낯 ?띿뒪??full_text)瑜?鍮꾧탳?섏뿬 媛???좎궗??'?먮낯 臾몄옣'??李얠쓬
        verified_paragraph = _find_best_matching_chunk(
            llm_output=llm_extracted_clue,
            original_text=full_text
        )
        state["extracted_important_sentence"] = verified_paragraph
        state["news_analysis_result"]["extracted_sentence"] = verified_paragraph
        print(f"  - [3?④퀎 遺꾩꽍 ?꾨즺]. 諛쒖톸???먮Ц 臾몄옣: {verified_paragraph}")

    except Exception as e:
        state["error"] = f"?댁뒪 遺꾩꽍 3?④퀎(臾몃떒 異붿텧) 以??ㅻ쪟 諛쒖깮: {e}"
        return state

    return state

def capture_highlighted_image(state: AgentState) -> Dict[str, Any]:
    if not state.get("selected_document_url") or not state.get("extracted_important_sentence"):
        return state
    print("\n[PTPRA Agent] 7. ?댁뒪 ?먮Ц ?섏씠?쇱씠??諛?罹≪쿂 以?..")
    url = state["selected_document_url"]
    sentence = state["extracted_important_sentence"]

    captured_image = highlight_and_capture_cropped(url, sentence)
    
    if captured_image:
        # ?곹깭?먯꽌 run_id 媛?몄삤湲?(?놁쓣 寃쎌슦瑜??鍮꾪빐 uuid ?ъ슜)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        # ?뚯씪紐낆쑝濡?遺?곹빀??臾몄옄 ?쒓굅 ?먮뒗 蹂寃?        safe_filename = re.sub(r'[\\/*?:"<>|()]', '', str(run_id))
        # 'results/task5' ?붾젆?좊━媛 ?놁쑝硫??앹꽦
        output_dir = "results/task5"
        os.makedirs(output_dir, exist_ok=True)
        image_path = os.path.join(output_dir, f"{safe_filename}.png")

        captured_image.save(image_path)
        state["screenshot_image_path"] = image_path
    else:
        print("  - 寃쎄퀬: ?대?吏 罹≪쿂???ㅽ뙣?덉뒿?덈떎. ?띿뒪???묐떟留??앹꽦?⑸땲??")
        state["screenshot_image_path"] = None
    return state

def generate_final_response(state: AgentState) -> Dict[str, Any]:
    if state.get("final_alert_message"):
        print("\n[PTPRA Agent] 8. 理쒖쥌 ?묐떟 ?앹꽦 以?(?꾪뿕 ?놁쓬)...")
        return state
    print("\n[PTPRA Agent] 8. 理쒖쥌 ?묐떟 硫붿떆吏 ?앹꽦 以?..")
    if state.get("error"):
        state["final_alert_message"] = f"二꾩넚?⑸땲?? ?붿껌 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎: {state['error']}"
        return state
    trade = state["triggering_trade_info"]
    risk = state["identified_risk_pattern"]
    news_analysis = state["news_analysis_result"]
    part1_recognition = f"理쒓렐 **{trade['time'].strftime('%Y??%m??%d??)}**??吏꾪뻾?섏떊 **'{trade['stock_name']}' {trade['type']}** 湲곕줉???뺤씤?덉뒿?덈떎."
    part2_reason_empathy = ""
    if news_analysis and news_analysis.get('reason_summary') and news_analysis.get('extracted_sentence'):
        part2_reason_empathy = f"怨좉컼?섏쓽 ?대윭??寃곗젙? ?꾨쭏??**'{news_analysis['reason_summary']}'** 愿???뚯떇 ?뚮Ц?댁뿀??寃껋쑝濡??앷컖?⑸땲?? ?뱀떆 ?댁뒪?먯꽌??'{news_analysis['extracted_sentence']}'?쇰ŉ 湲띿젙?곸씤 ?꾨쭩???대넃?섏짛."
    part3_risk_alert = f"?섏?留?怨좉컼?섏쓽 ?꾨줈???섏씠: {state['my_data']['age']}?? ?깊뼢: {state['my_data']['investment_profile']})??湲곗??쇰줈 遺꾩꽍??寃곌낵, ?꾩옱 **'{risk['risk_category']}'** ?곹깭???대떦?⑸땲?? {risk['description']}"
    part4_future_warning = f"?대윭??吏묒쨷 ?ъ옄 ?⑦꽩??吏?띾맆 寃쎌슦, ?대떦 醫낅ぉ???묒? 蹂?숈꽦?먮룄 ?꾩껜 ?먯궛???ш쾶 ?곹뼢??諛쏆쓣 ???덉쑝硫? ?덉긽移?紐삵븳 ?섎씫 ?????먯떎濡??댁뼱吏??꾪뿕???덉뒿?덈떎. {risk['recommendation']}"
    final_message_parts = [part1_recognition, part2_reason_empathy, part3_risk_alert, part4_future_warning]
    if state.get("screenshot_image_path"):
        final_message_parts.append(f"\n**李멸퀬 ?댁뒪 湲곗궗???듭떖 ?댁슜:**")
        final_message_parts.append(f"![媛뺤“???대?吏]({state['screenshot_image_path']})")
        if state.get("selected_document_url"):
            final_message_parts.append(f"?먮낯 ?먮즺: {state['selected_document_url']}")
    state["result"] = "\n\n".join(filter(None, final_message_parts))
    return state

def handle_error(state: AgentState) -> Dict[str, Any]:
    print(f"\n[PTPRA Agent] ?ㅻ쪟 諛쒖깮: {state.get('error', '?????녿뒗 ?ㅻ쪟')}")
    state["final_alert_message"] = f"?ㅻ쪟媛 諛쒖깮?섏뿬 ?붿껌???꾨즺?????놁뒿?덈떎: {state.get('error', '?????녿뒗 ?ㅻ쪟')}. ?ㅼ떆 ?쒕룄?댁＜?몄슂."
    return state

def generate_final_response(state: AgentState) -> Dict[str, Any]:
    if state.get("final_alert_message"):
        print("\n[PTPRA Agent] 8. 理쒖쥌 ?묐떟 ?앹꽦 以?(?꾪뿕 ?놁쓬)...")
        return state
    print("\n[PTPRA Agent] 8. 理쒖쥌 ?묐떟 硫붿떆吏 ?앹꽦 以?..")
    if state.get("error"):
        state["final_alert_message"] = f"二꾩넚?⑸땲?? ?붿껌 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎: {state['error']}"
        return state
    trade = state["triggering_trade_info"]
    risk = state["identified_risk_pattern"]
    news_analysis = state["news_analysis_result"]
    part1_recognition = f"理쒓렐 **{trade['time'].strftime('%Y??%m??%d??)}**??吏꾪뻾?섏떊 **'{trade['stock_name']}' {trade['type']}** 湲곕줉???뺤씤?덉뒿?덈떎."
    part2_reason_empathy = ""
    if news_analysis and news_analysis.get('reason_summary') and news_analysis.get('extracted_sentence'):
        part2_reason_empathy = f"怨좉컼?섏쓽 ?대윭??寃곗젙? ?꾨쭏??**'{news_analysis['reason_summary']}'** 愿???뚯떇 ?뚮Ц?댁뿀??寃껋쑝濡??앷컖?⑸땲?? ?뱀떆 ?댁뒪?먯꽌??'{news_analysis['extracted_sentence']}'?쇰ŉ 湲띿젙?곸씤 ?꾨쭩???대넃?섏짛."
    part3_risk_alert = f"?섏?留?怨좉컼?섏쓽 ?꾨줈???섏씠: {state['my_data']['age']}?? ?깊뼢: {state['my_data']['investment_profile']})??湲곗??쇰줈 遺꾩꽍??寃곌낵, ?꾩옱 **'{risk['risk_category']}'** ?곹깭???대떦?⑸땲?? {risk['description']}"
    part4_future_warning = f"?대윭??吏묒쨷 ?ъ옄 ?⑦꽩??吏?띾맆 寃쎌슦, ?대떦 醫낅ぉ???묒? 蹂?숈꽦?먮룄 ?꾩껜 ?먯궛???ш쾶 ?곹뼢??諛쏆쓣 ???덉쑝硫? ?덉긽移?紐삵븳 ?섎씫 ?????먯떎濡??댁뼱吏??꾪뿕???덉뒿?덈떎. {risk['recommendation']}"
    final_message_parts = [part1_recognition, part2_reason_empathy, part3_risk_alert, part4_future_warning]
    if state.get("screenshot_image_path"):
        image_url = create_shareable_url(state["screenshot_image_path"], host_ip=config['host_ip'], port=config['port'])
        if image_url:
            final_message_parts.append(f"\n?섏씠?쇱씠???대?吏: {image_url}")
    if state.get("selected_document_url"):
        final_message_parts.append(f"?먮낯 ?댁뒪: {state['selected_document_url']}")
    state["result"] = "\n".join(filter(None, final_message_parts))
    return state


# --- 4. PTPRA ?쒕툕洹몃옒??鍮뚮뜑 ---

def task5_graph():
    """媛쒖씤蹂?留ㅻℓ ?⑦꽩 ?꾪뿕 ?뚮┝(PTPRA)???꾪븳 ?쒕툕洹몃옒?꾨? 鍮뚮뱶?섍퀬 而댄뙆?쇳빀?덈떎."""
    workflow = StateGraph(AgentState)
    

    workflow.add_node("extract_transactions", extract_transactions)
    workflow.add_node("extract_mydata", extract_mydata)
    workflow.add_node("analyze_risk_patterns", analyze_risk_patterns)
    workflow.add_node("verify_analysis_results", verify_analysis_results)
    workflow.add_node("search_korean_documents", search_korean_documents)
    workflow.add_node("analyze_and_extract_from_news", analyze_and_extract_from_news)
    workflow.add_node("capture_highlighted_image", capture_highlighted_image)
    workflow.add_node("generate_final_response", generate_final_response)
    workflow.add_node("handle_error", handle_error)
    workflow.set_entry_point("extract_transactions")
    workflow.add_edge("extract_transactions", "extract_mydata")
    workflow.add_edge("extract_mydata", "analyze_risk_patterns")
    workflow.add_edge("analyze_risk_patterns", "verify_analysis_results")

    workflow.set_entry_point("extract_transactions")

    def after_verification(state: AgentState) -> Dict[str, Any]:
        if not state.get('is_verified', False): return "handle_error"
        if state.get("search_queries"): return "search_korean_documents"
        else: return "generate_final_response"

    workflow.add_conditional_edges(
        "verify_analysis_results",
        after_verification,
        {"search_korean_documents": "search_korean_documents", "generate_final_response": "generate_final_response", "handle_error": "handle_error"}
    )
    # [?섏젙] ?ｌ? ?곌껐 蹂寃?    workflow.add_edge("search_korean_documents", "analyze_and_extract_from_news")
    workflow.add_edge("analyze_and_extract_from_news", "capture_highlighted_image")
    workflow.add_edge("capture_highlighted_image", "generate_final_response")
    workflow.add_edge("generate_final_response", END)
    workflow.add_edge("handle_error", END)
    
    return workflow.compile()
