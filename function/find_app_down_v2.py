from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
import time




class app_finder():
    def __init__(self):
        #driver 초기 설정---------------
        options=Options()                                          #옵션 설정 준비
        options.add_argument('--headless')                       #headless 옵션
        options.add_argument("--blink-settings=imagesEnabled=false") #이미지 로딩 제거
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)                 #option 넣어주고 드라이버 실행

    def finding(self,c_name,url):
        start_time = time.time()

        if 'play.google.com/store/apps' in url:
            return c_name, 'download_url'

        if not url.startswith(("http://","https://")):
            url = 'https://'+ url
        self.driver,find_it = find_href(self.driver,url)

        if find_it:
            return c_name, 'download_url'
        else:
            self.driver,find_it =  find_img_and_button(self.driver,url)
            if time.time() - start_time > 300:  # 300초 = 5분
                return c_name, 'not_download_url'
            

            if find_it:
                return c_name, 'download_url'
            
            else:
                return c_name, 'not_download_url'
    
    def reset_driver(self):
                #driver 초기 설정---------------
        options=Options()                                          #옵션 설정 준비
        options.add_argument('--headless')                       #headless 옵션
        options.add_argument("--blink-settings=imagesEnabled=false") #이미지 로딩 제거
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)                 #option 넣어주고 드라이버 실행






def find_href(driver,url):
    

    # URL로 이동
    driver.get(url)


    frames = driver.find_elements(By.TAG_NAME,'iframe')
    frames += driver.find_elements(By.TAG_NAME,'frame')

    driver,hrefs = frame_iter_find_href(driver,frames)

    find_it = False

    for url in hrefs:
        if 'play.google.com/store/apps' in url:
            find_it = True  
            break
        
        # 현재 드라이버에서 모든 창 핸들을 가져옴
    all_windows = driver.window_handles

    # 현재 활성화된 창의 핸들을 가져옴
    current_window = driver.current_window_handle

    # 모든 창을 순회하며, 현재 창이 아닌 경우 닫기
    for window in all_windows:
        if window != current_window:
            driver.switch_to.window(window)
            driver.close()

    # 마지막으로 현재 창으로 포커스를 다시 이동
    driver.switch_to.window(current_window)

    return driver, find_it
# # 모든 태그에서 href 속성 검색


# elements_with_href = driver.find_elements(By.XPATH, "//*[@href]")

# # href 속성 출력
# for element in elements_with_href:
#     href = element.get_attribute("href")
#     print(href)

# # 브라우저 닫기
# driver.quit()

def frame_iter_find_href(driver,frames):
    """
    frame을 순환하며 href를 찾아내는 함수
    """
    hrefs = []
    
    # 메인 frame에서 url을 찾아내는 함수
    elements_with_href = driver.find_elements(By.XPATH, "//*[@href]")
    for element in elements_with_href:
        try:
            href = element.get_attribute("href")
        except:
            href = None
                
        hrefs.append(href)    

    # frame을 순환하며 url을 찾는 함수
    if frames:
        for frame in frames:    # frame 순환
            #frame 전환
            driver.switch_to.frame(frame)   
            time.sleep(1)

            # href 찾기
            elements_with_href = driver.find_elements(By.XPATH, "//*[@href]")

            for element in elements_with_href:

                try:
                    href = element.get_attribute("href")
                except:
                    href = None
                    
                hrefs.append(href)
            
            driver.switch_to.default_content()
    

    return driver, hrefs







def find_img_and_button(driver,url):


    # 웹페이지 로드
    driver.get(url)

    # 페이지가 완전히 로드되도록 대기
    time.sleep(3)

    find_it = False

    # frame 찾기
    frames = driver.find_elements(By.TAG_NAME,'iframe') + driver.find_elements(By.TAG_NAME,'frame')


    # 구글 플레이스토어 버튼 찾기
    button_set = driver.find_elements(By.TAG_NAME, "button")
    img_set = driver.find_elements(By.TAG_NAME,'img')

    # 버튼, 이미지 전체 길이 저장
    len_url = len(button_set+img_set)

    # 모든 버튼, 이미지에 대해 반복
    driver, find_it = find_download_url(driver,len_url,url)

    if find_it == True:
        return driver, find_it

    # frame 순환
    if frames: # frame이 존재할 경우

        # frame 순환
        for x in range(len(frames)):    #frame 수만큼
            driver.get(url)             # driver url로 전환
            frames = driver.find_elements(By.TAG_NAME,'iframe') + driver.find_elements(By.TAG_NAME,'frame') #frame 찾기
            if x < len(frames):
                driver.switch_to.frame(frames[x])   #frame 전환
            else:
                break

            # 구글 플레이스토어 버튼 찾기
            button_set = driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME,'img')
    
            len_url = len(button_set)

            # frame 내부 순환
            for i in range(len_url):    # 버튼 숫자만큼 반복

                # 이전 부분으로 돌아가기(새로고침으로 찾아줘야 함)
                driver.get(url)         # 새로고침
                subframes = driver.find_elements(By.TAG_NAME,'iframe') + driver.find_elements(By.TAG_NAME,'frame') # 프레임 다시 찾기
                driver.switch_to.frame(subframes[x])                # 이동했던 프레임으로 다시 이동                             
                time.sleep(2)                                       # 기다리기


                # 버튼 찾아 클릭하기
                buttons = driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME,'img')    # 버튼 찾기
                #버튼 클릭
                if i < len(buttons):
                    driver.execute_script("arguments[0].click();", buttons[i])
                    try:
                        # 경고창이 나타났는지 확인
                        alert = driver.switch_to.alert
                        alert.accept()  # 경고창 닫기
                    except :
                        # 경고창이 없으면 넘어감
                        pass
                else:
                    break                                    
                windows = driver.window_handles

                # 앱 다운 페이지인지 확인하기
                if len(windows) > 1:
                    driver.switch_to.window(windows[-1]) # 새로운 창으로 이동

                current_url = driver.current_url
                if current_url and 'play.google.com/store' in current_url:
                    find_it = True
                    break

                driver.close()
                driver.switch_to.window(windows[0])
                current_url = driver.current_url

                if current_url and 'play.google.com/store' in current_url:
                    print(current_url)
                    find_it = True
                    break
            
            if find_it:
                return driver, find_it

            driver.switch_to.default_content()
        
        return driver, find_it


def find_download_url(driver,len_url,url):
    for i in range(len_url):
        driver.get(url) # connect url
        time.sleep(2)
        buttons = driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME,'img') # find all button, url we have to find it because it's renewed when we connect url 
        driver.execute_script("arguments[0].click();", buttons[i])   # click button

        try:
            # 경고창이 나타났는지 확인
            alert = driver.switch_to.alert
            alert.accept()  # 경고창 닫기
        except :
            # 경고창이 없으면 넘어감
            pass
        windows = driver.window_handles                              # save window count
        if len(windows) > 1:                                         # if new window open
            driver.switch_to.window(windows[-1]) # 새로운 창으로 이동
        
        current_url = driver.current_url                         # get new window's url
        if current_url and 'play.google.com/store' in current_url:               # if current url is download page
            find_it = True
            return driver, True                             # return driver and find_it, which is True
    
    return driver,False



