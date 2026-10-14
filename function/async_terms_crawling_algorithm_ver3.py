from selenium import webdriver #selenium 웹드라이버 사용
from selenium.webdriver.common.keys import Keys #selenium으로 키 조작을 위한 import
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait #기다리는 기능
from selenium.webdriver.support import expected_conditions as EC #기다리는 조건
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup as bs
import time
import re
import pickle
import pandas as pd
import os
import json
import requests
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor
import kss

def return_terms(c_name,url,keyword):
    """
    찾은 경우(state = True) 키워드에 포함되는 약관만 출력
    못찾은 경우 (state = False) 못찾았다 
    """
    # df, 기업이름, 상태를 출력
    df, c_name, state = crawling_algorithm(c_name,url)

    
    # 약관을 찾아서 긁어온 경우
    if state:
        cl_df = []

    # 키워드가 포함된 약관만 찾아서
        for _,row in df.iterrows():
            find = False
            for word in keyword:
                if word in row['sentence']:
                    find = True
                    break

        # 해당 키워드가 존재하면 포함
            if find == True:
                cl_df.append(row)


        # 키워드가 존재하는 약관만 포함한 dataframe을 출력
        return pd.DataFrame(cl_df) 
    
    # 약관 못찾았으면 None 출력
    else:
        return None



async def async_crawling(c_name_url_tuple):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=5) as executor:
        #비동기로 각 사업체에 대한 수집을 수행
        result = await asyncio.gather(*[loop.run_in_executor(executor,crawling_algorithm,c_name,url) for c_name, url in c_name_url_tuple])
    
    return result # [5개씩 출력]



def crawling_algorithm(c_name,url):
    #driver 초기 설정---------------
        options=Options()                                          #옵션 설정 준비
        options.add_argument('--headless')                       #headless 옵션
        options.add_argument("--blink-settings=imagesEnabled=false") #이미지 로딩 제거
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(options=options)                 #option 넣어주고 드라이버 실행

        try:
            driver,state = to_terms_v2(driver,url) #페이지로 이동, 약관으로 이동하지 못할시 None을 출력해 Error를 일으킴
            if state == False:
                raise ValueError("의도적으로 발생한 에러입니다.")
            
            sentence_box = []
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                sentence_box  += sep_sentence(driver)
            
            df_sentence = pd.DataFrame({'sentence':sentence_box})

            while len(driver.window_handles) != 1:  #새 창이 열리는 경우가 있음 예외처리 필요
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            driver.quit()
            return df_sentence,c_name,True
            
        except Exception as e:
            driver.quit()
            return None,c_name,False



def to_terms(driver,url:str):
    """
    메인 페이지에 접속해 약관 페이지로 이동
    """
    
    # 메인 페이지 로딩--------------
    driver.get(url)

    driver = scroll_down(driver)

    #현재 창 개수 저장
    cur_window_cnt = len(driver.window_handles)

    #약관으로 들어가기--------------
    xpath = "//*[contains(text(),'약관')]" #이거 안되면 small 태그 검색 해봐야 함
    obj_gui = driver.find_elements(By.XPATH,xpath)

    #약관을 못찾은 경우-------------
    if obj_gui == []:
        # frame이 존재하는지 확인하고, 넘어가서 obj를 찾아보기
        time.sleep(1)
        frames = driver.find_elements(By.TAG_NAME, "frame")
        frames += driver.find_elements(By.TAG_NAME,'iframe')

        #frame이 존재하는 경우
        if frames != []:
            driver,obj_gui = frame_iter(driver,frames)

        #frame도 존재하지 않는 경우
        else:
            return driver, False


    #약관 찾은 경우-----------------
    for x in obj_gui[::-1]:
        try:
            driver.execute_script("arguments[0].click();", x)
        except:
            pass
    time.sleep(1)

    while len(driver.window_handles) != cur_window_cnt:  #새 창이 열리는 경우가 있음 예외처리 필요
        time.sleep(1)
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    
    return driver, True



def to_terms_v2(driver,url:str):
    """
    메인 페이지에 접속해 약관 페이지로 이동
    """
    
    # 메인 페이지 로딩--------------
    driver.get(url)

    driver = scroll_down(driver)
    

    #약관으로 들어가기--------------
    try:
        # 페이지 로딩 대기
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))  # 페이지가 로드될 때까지 대기
        )

        # JavaScript로 "약관" 텍스트가 포함된 요소 찾기
        script = """
        var results = [];

        // 메인 문서에서 '약관' 포함된 요소 찾기
        var elements = document.querySelectorAll('*');
        elements.forEach(el => {
            if (el.innerText && el.innerText.includes('약관')) {
                results.push(el);  // DOM 요소 저장
            }
        });

        // 모든 iframe 찾기
        var iframes = document.querySelectorAll('iframe');
        for (var i = 0; i < iframes.length; i++) {
            var iframe = iframes[i];
            try {
                var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                if (iframeDoc) {
                    var iframeElements = iframeDoc.querySelectorAll('*');
                    iframeElements.forEach(el => {
                        if (el.innerText && el.innerText.includes('약관')) {
                            results.push(el);  // iframe 내 요소 추가
                        }
                    });
                }
            } catch (e) {
                console.warn('CORS로 인해 접근 불가한 iframe 발견:', iframe.src);
            }
        }

        return results;  // 메인 문서와 iframe 내 '약관' 포함 요소 반환
        """
        elements = driver.execute_script(script)  # JavaScript 실행
        
        # 반환된 요소 리스트 처리
        if elements:
            for index, element in enumerate(reversed(elements)):
                # 초기 창과 URL 정보 저장
                original_window = driver.current_window_handle

                # driver.execute_script("arguments[0].scrollIntoView(true);", element)  # 요소로 스크롤
                driver.execute_script("arguments[0].setAttribute('target', '_blank'); arguments[0].click();", element) # 새창에서 열기

                time.sleep(3)
                driver.switch_to.window(original_window)
                # if len(current_handles) > len(initial_handles):
                #     new_window_handle = list(set(current_handles) - set(initial_handles))[0]  # 새 창 핸들 찾기
                #     driver.switch_to.window(new_window_handle)  # 새 창으로 이동

            # 원래 창 닫기
            driver.close()


                
            return driver, True
        
        else:
            return driver, False

    except Exception as e:
        return driver, False


def frame_iter(driver,frames):
    """
    frame이 존재하는 페이지의 경우 frame을 순환하며 약관을 찾아내는 함수
    """
    for frame in frames:    # frame 순환
        try:
            #frame 전환
            driver.switch_to.frame(frame)   

            # 약관 검색
            xpath = "//*[contains(text(),'약관')]"  
            obj_gui = driver.find_elements(By.XPATH,xpath)

            # 약관 찾은 경우
            if obj_gui != []:
                break

            # 못찾은 경우 원래 content로 전환
            else:
                driver.switch_to.default_content()
        
        # frame 전환 실패한 경우
        except NoSuchElementException:
            pass
    
    return driver, obj_gui



def sep_sentence(driver):
    """
    text를 받아와 문장 분할에 적합하게 만드는 함수

    """
    # frame이 여러개인지 찾고
    frames = driver.find_elements(By.TAG_NAME, "frame")
    # 첫번째 페이지에서 text를 가져옴
    result =text_seperator(driver)
    
    # frame이 여러개일 경우
    if frames != []:
        for frame in frames:
            #frame 전환 후
            driver.switch_to_frame(frame)
            #result에 text를 저장하고
            result += text_seperator(driver)
            #원래 frame으로 전환
            driver.switch_to_default_content()
    
    # 문장인지 검색하고 
    sentence_box = []

    for sentence in result:
        sentence_box += kss.split_sentences(sentence)
    # df = pd.DataFrame({"sentence":sentence_box})
    return sentence_box


def text_seperator(driver):
    html = driver.page_source
    soup = bs(html)
    text = soup.get_text()

    text = re.sub(r'[^가-힣\s]', '', text)
    text = re.sub(r'\n', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    result = kss.split_sentences(text)
        
    return result 




def scroll_down(driver):
    #스크롤 내리기-------------------
    wait = WebDriverWait(driver, 10)                                            #waiting 설정, 최대 10초 기다리기
    try: driver.execute_script("return document.body.scrollHeight")
    except:  driver.refresh()
    before = 0                                                                   #초기값 설정
    after = 100
    start_time = time.time()
    while before != after:  #스크롤 내리기 이전과 이후가 다를 경우
        before = driver.execute_script("return document.body.scrollHeight")      #before을 업데이트
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")   #스크롤을 내리고
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")        #로딩이 다 될때까지 반복
        time.sleep(1)
        after = driver.execute_script("return document.body.scrollHeight")
        end_time = time.time()
        if end_time-start_time >=150: break
    
    return driver


