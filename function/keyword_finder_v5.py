# 사업자 검색 추가

from selenium import webdriver #selenium 웹드라이버 사용
from selenium.webdriver.common.keys import Keys #selenium으로 키 조작을 위한 import
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait #기다리는 기능
from selenium.webdriver.support import expected_conditions as EC #기다리는 조건
from bs4 import BeautifulSoup as bs
import time
import re
import pickle
import pandas as pd
import os
import json
import pytesseract
import cv2 
import requests
import numpy as np
#-----------------------------------------------------------------------------------


class keyword_finder():

    def __init__(self,keyword_dict,platform_dict,cate):
        """
        초기 설정
        """

        # 키워드
        with open(keyword_dict, 'rb') as f:
            self.loaded_dict = pickle.load(f)

        self.cate = cate
        # 플랫폼   
        if self.cate == 202:
            with open(platform_dict,'rb') as f:
                self.platform = pickle.load(f)
        else:
            self.platform = None

        # 드라이버
        options = Options()
        options.add_argument('--headless')                       #headless 옵션
        options.add_argument("--blink-settings=imagesEnabled=false") #이미지 로딩 제거
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)

    


    def main_processer(self,c_name, url):
        """
        페이지 분류 : 통신판매중개자 / 입점형태 / 통신판매업자 / 확인필요 (통신판매업자와 확인필요는 약관탐색 돌려야 함) // 201, not-201
        오류 : URL 없음 / 정보 없음 / 오류 
        """

        # 드라이버는 하나만 떠 있도록
        # if len(self.driver.window_handles) != 1: #10개에 한번씩 메인 윈도우 외에 다른 창이 떠 있는지 검사
        #     self.driver = maintain_only_main(self.driver) #떠 있으면 이 작업 실행
        self.loaded_dict['사업자등록번호'] = [
                                                    r'사업자등록번호\d{10}',
                                                    r'사업자등록번호안내\d{10}',
                                                    r'bizno\d{10}',
                                                    r'no\d{10}',
                                                    r'사업자번호\d{10}',
                                                    r'\|\d{10}\|',
                                                    r'사업자등록\d{10}',
                                                    r'LICENSE\d{10}',
                                                    r'BN\d{10}',
                                                    r'number\d{10}',
                                                    r'사업자등록자번호\d{10}'
                                                ]
        self.driver.quit()
        self.reset_driver()

        # 초기 dictonary 설정
        ori_dict = dict(zip(['사업체명']+list(self.loaded_dict.keys())+['특이사항']+['홈페이지'],
                            [c_name]+['X']*len(self.loaded_dict)+["URL없음"]+[url]))
        
        #------------------------- 통신판매중개자 search -------------------------#
        # url 없을 경우 예외처리
        if url == None:
            return None,'URL 없음',None

        # 예기치 못한 오류가 발생할 경우 예외처리
        try:
            if not url.startswith(("http://","https://")):
                url = 'https://'+ url
            html = crawling_data(url,self.driver)

            # html을 제대로 가져오지 못한 경우
            if html == None:
                return ori_dict['사업자등록번호'],'정보 없음',None
            
            # 키워드 search
            bizno_dict,_ = keyword_find({'사업자등록번호':[
                                                    r'사업자등록번호\d{10}',
                                                    r'사업자등록번호안내\d{10}',
                                                    r'bizno\d{10}',
                                                    r'no\d{10}',
                                                    r'사업자번호\d{10}',
                                                    r'\|\d{10}\|',
                                                    r'사업자등록\d{10}',
                                                    r'LICENSE\d{10}',
                                                    r'BN\d{10}',
                                                    r'number\d{10}',
                                                    r'사업자등록자번호\d{10}'
                                                ]},self.platform,ori_dict,html,None)

            ori_dict['사업자등록번호'] = bizno_dict['사업자등록번호']
            ori_dict,find_word = keyword_find_by_java(self.loaded_dict,self.platform,ori_dict,self.driver,self.cate)
            

            # 정보를 긁어오지 못한 경우 ocr을 진행
            if (self.cate == 202 and ori_dict['사업자등록번호'] == 'X') or (self.cate==201 and ori_dict['201']=='X'):
                ocr_text = search_in_ocr(self.driver)
                ori_dict,find_word = keyword_find(self.loaded_dict,self.platform,ori_dict,ocr_text,self.cate)
                

        except Exception as e:
            print("에러 종류:", type(e).__name__)  # 에러 이름 출력
            print("에러 메시지:", e)              # 에러 메시지 출력
            return None, '오류', None

        if self.cate == 202: 
            #------------------- 제대로 수집이 완료 된 경우 분류 진행 --------------------#
            if ori_dict['통신판매중개자'] == 'O' or ori_dict['입점'] == 'O' or ori_dict['당사자']=='O' or ori_dict['거래에대한 책임'] =="O":
                return ori_dict['사업자등록번호'],'202',find_word
            elif ori_dict['특이사항'] =='입점형태':
                return ori_dict['사업자등록번호'],'입점형태',None
            elif ori_dict['통신판매업'] == 'O':
                return ori_dict['사업자등록번호'],'통신판매업자',find_word
            else:
                return ori_dict['사업자등록번호'],'확인필요',None
        
        if self.cate == 201:
            if ori_dict['201'] == "O":
                return ori_dict['사업자등록번호'],'201',find_word
            else:
                return ori_dict['사업자등록번호'],'not-201',None
        
        if self.cate ==203:
            if ori_dict['203'] =="O":
                return ori_dict['사업자등록번호'],'203',find_word
            else:
                return ori_dict['사업자등록번호'],'not-203',None




    def reset_driver(self):
        #driver 초기 설정---------------
        options=Options()                                          #옵션 설정 준비
        options.add_argument('--headless')                       #headless 옵션
        options.add_argument("--blink-settings=imagesEnabled=false") #이미지 로딩 제거
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)                 #option 넣어주고 드라이버 실행



#필요 함수
def return_info(df):
    """
    input: dataframe
    process: 데이터프레임에서 필요한 열을 가져와, 하나의 행씩 반환해줌
    output: 열을 반환하는 객체 [회사명,홈페이지1,..]
    """
    #필요한 정보를 담은 행을 반환하기----------------
    df = df.loc[:,['사업체명','홈페이지']].reset_index(drop=True) #필요한 열만 가져오기 
    for i in range(len(df)):                     #df 길이 만큼 반복해서
        yield df.loc[i].dropna().values.tolist() #[회사이름, 홈페이지1,2.. 개수만큼] 리스트 반환



def crawling_data(url,driver):
    """
    input: url
    process: 셀레니움을 활용해 해당 홈페이지의 스크롤을 내려 모든 값을 확인, 이를 text로 반환함
    output: 해당 홈페이지의 html
    """

    #홈페이지 접속-------------------
    try: 
        driver.get(url)      #원하는 페이지로 연결 (나중에 엑셀의 홈페이지 열을 긁어오게 해야함)
    except:                  #url이 제대로 되어있지 않을 경우
        return None          #none 반환
    
    time.sleep(1)            #오류방지 기다리기

    # #팝업창 닫기---------------------.
    # main = driver.window_handles       #현재 떠있는 모든 창 불러오기
    # for p in main:                     #페이지 별로 반복
    #     if p != main[0]:               #메인 페이지가 아닌 경우
    #         driver.switch_to.window(p) #해당 페이지로 가서
    #         driver.close()             #페이지 종료


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
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))        #로딩이 다 될때까지 반복
        time.sleep(2)
        after = driver.execute_script("return document.body.scrollHeight")
        end_time = time.time()
        if end_time-start_time >=150: break
    #html soup로 파싱하기------------
    html = driver.page_source      #홈페이지의 현재 html을 가져오기
    soup = bs(html,'html.parser')  #파싱하기
    soup_to_text = soup.get_text() #텍스트로 바꾸기



    # iframe 순환----------

    # frame 찾기
    frames = driver.find_elements(By.TAG_NAME,'iframe')
    frames += driver.find_elements(By.TAG_NAME,'frame')

    if frames:
        for frame in frames:    # frame 순환
            #frame 전환
            driver.switch_to.frame(frame)   
            time.sleep(1)

            #html soup로 파싱하기------------
            html = driver.page_source      #홈페이지의 현재 html을 가져오기
            soup = bs(html,'html.parser')  #파싱하기
            soup_to_text += soup.get_text() #텍스트로 바꿔서 더하기
            

            driver.switch_to.default_content()

    #최종 반환----------

    return soup_to_text        

def keyword_find(keyword_dict,platform,ori_dict,soup_to_text,cate):
    """
    input: 키워드/검색어, 채워야할 정보, 검색할 텍스트
    process: 각 키워드 별로 텍스트에서 검색어를 검색 정보를 채움
    output: [키워드1:X, 키워드2:O ...]
    """
    find_word = ''
    if cate == 202 and platform_finder(ori_dict,platform) == True: #해당 홈페이지가 입점 형태라면
        ori_dict['통신판매업'] = 'O'
        ori_dict['특이사항'] ='입점형태'
        return ori_dict
    
    for keyword,comp_exp in list(keyword_dict.items()):
        soup_to_text = re.sub(r'[^a-zA-Z0-9가-힣]', '',soup_to_text)
        if ori_dict[keyword] != "X": break              #이미 차있는 상태라면 건너 뜀
        iskey = [] ; len_of_com = len(comp_exp) ; fn = 0
        while not iskey and len_of_com>0: #키워드 검색 결과가 있거나, search_list의 모든 값을 검색했으면 멈춤
            iskey = re.findall(comp_exp[fn],soup_to_text)
            fn+=1
            len_of_com-=1
        if keyword=='사업자등록번호' and iskey: ori_dict[keyword] = re.sub(r'[^0-9]', '', iskey[0]) ; continue
        if iskey: ori_dict[keyword] ='O'; find_word = comp_exp[fn-1] #키 값이 존재하면 O를 삽입
        if ori_dict != '확인필요': ori_dict['특이사항'] = 'X'  #제대로 검색이 되었다면 특이사항을 X로 놓음
    return ori_dict , find_word # 찾아진 단어를 같이 반환      



def keyword_find_by_java(keyword_dict, platform, ori_dict,driver,cate):
    find_word = ''
    if cate == 202 and platform_finder(ori_dict,platform) == True: #해당 홈페이지가 입점 형태라면
        ori_dict['통신판매업'] = 'O'
        ori_dict['특이사항'] ='입점형태'
        return ori_dict
    
    for keyword,comp_exp in list(keyword_dict.items()):
        for word in comp_exp:
            if ori_dict[keyword] != "X": break
    
                # 페이지 내에서 텍스트가 로드되기를 기다림

            if search_keyword_by_java(driver,word)>0:
                    ori_dict[keyword] = 'O'
                    ori_dict['특이사항'] = 'X'
                    find_word = word
    return ori_dict, find_word # 찾아진 단어를 같이 반환


def search_keyword_by_java(driver,keyword):
    script =f"""
            const results = [];
            
            // 메인 문서에서 '{keyword}' 포함된 요소 찾기
            const elements = document.querySelectorAll('*');
            elements.forEach(el => {{
                if (el.innerText && el.innerText.includes('{keyword}')) {{
                    results.push(el.outerHTML);
                }}
            }});

            // 모든 iframe 찾기
            const iframes = document.querySelectorAll('iframe');
            for (const iframe of iframes) {{
                try {{
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

                    if (iframeDoc) {{
                        const iframeElements = iframeDoc.querySelectorAll('*');
                        iframeElements.forEach(el => {{
                            if (el.innerText && el.innerText.includes('{keyword}')) {{
                                results.push(el.outerHTML);
                            }}
                        }});
                    }}
                }} catch (e) {{
                    // CORS로 인해 접근 불가한 경우
                    console.warn('접근 불가한 iframe 발견:', iframe.src);
                }}
            }}

            return results;
        """
    elements_with_keyword = driver.execute_script(script)
    
    return len(elements_with_keyword)





#사업자 등록 번호가 없는 경우------------------------
#OCR    
def search_in_ocr(driver):
    img_list = driver.find_elements(by=By.TAG_NAME,value='img') #이미지 태그에서 정보 가져와서
    img_url=[url for url in [element.get_attribute('src') for element in img_list] if url and (('png' in url) or ('jpg' in url))][-20:] #png, jpg만 담기(뒤에 20개)

    ocr_text =""
    for img in img_url:
        try:
            response = requests.get(img,headers={"User-Agent": "Mozilla/5.0"}) #이미지 불러와서
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8) #변환하고
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR) #변환해서
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) #변환하고
            ocr_text += pytesseract.image_to_string(gray, lang='kor') #텍스트로 더하기
        except:
            continue
    return ocr_text

#창 여러개 떠 있을 때 없애는 함수
def maintain_only_main(driver):
    main_window = driver.current_window_handle #매인을 확인
    for dv in driver.window_handles: #전체 윈도우 가져오기
        if dv != main_window:
            driver.switch_to.window(dv)
            driver.close()
    
    driver.switch_to.window(main_window)
    return driver

def platform_finder(ori_dict,platform):

    for i in platform['platform']:#각각 검색해서
        pp = re.findall(i,ori_dict['홈페이지']) #홈페이지가 입점해있는 곳인지 검색
        if pp != []: #입점해 있다면
            return True
    
    return False













